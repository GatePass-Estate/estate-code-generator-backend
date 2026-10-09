"""Unit tests for provision_access and post-expiry access row.

Covers:
  - SubscriptionService.provision_access_subscription() happy path
  - provision_access_subscription() idempotency (returns existing sub)
  - provision_access_subscription() access tier not seeded
  - ExpiryService._expire_one() creates access row and marks paid row expired
  - _expire_one() sets over_cap_locked when active users exceed access cap
  - _expire_one() rolls back if access row creation fails
  - _expire_subscriptions() skips expiry entirely when access tier not seeded
  - _expire_subscriptions() isolates per-estate failures
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import sys
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

# Stub gatepass_notify before any app module tries to import it.
# fire_notify is async, so use AsyncMock.
_notify_stub = MagicMock()
_notify_stub.fire_notify = AsyncMock()
if "gatepass_notify" not in sys.modules:
    sys.modules["gatepass_notify"] = _notify_stub

from app.services.expiry_service import ExpiryService  # noqa: E402
from app.services.subscription_service import SubscriptionService  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────


ACCESS_TIER: dict[str, Any] = {
    "id": "tier-access",
    "slug": "access",
    "display_order": 0,
    "is_custom": False,
    "included_ai_features": [],
    "entitlements": {"max_active_users": 3},
}


def _make_sub(**overrides: Any) -> dict:
    base: dict[str, Any] = {
        "id": "sub-1",
        "estate_id": "estate-1",
        "tier_id": "tier-sentinel",
        "status": "active",
        "auto_renew": True,
        "pending_tier_slug": None,
        "pending_covered_users": None,
        "covered_users": 10,
        "period_start": "2026-01-01T00:00:00+00:00",
        "period_end": "2026-01-31T00:00:00+00:00",
        "paystack_subscription_code": None,
        "pre_expiry_notified": False,
        "entitlements": None,
        "over_cap_locked": False,
    }
    return {**base, **overrides}


class FakeRepo:
    """Minimal async-fake for DbRevenueRepository."""

    def __init__(
        self,
        *,
        active_sub: dict | None = None,
        subscriptions: list[dict] | None = None,
        tiers_by_slug: dict[str, dict] | None = None,
        active_user_count: int = 0,
        create_raises: bool = False,
    ) -> None:
        self._active_sub = active_sub
        self._subscriptions = subscriptions or (
            [active_sub] if active_sub else []
        )
        self._tiers_by_slug = tiers_by_slug or {}
        self._active_user_count = active_user_count
        self._create_raises = create_raises
        self.update_calls: list[tuple[str, dict]] = []
        self.create_calls: list[dict] = []
        self.delete_calls: list[str] = []

    async def get_active_subscription(self, _estate_id: str) -> dict | None:
        return self._active_sub

    async def list_estate_subscriptions(self, _estate_id: str) -> list[dict]:
        return list(self._subscriptions)

    async def get_tier_by_slug(self, slug: str) -> dict | None:
        return self._tiers_by_slug.get(slug)

    async def get_tier_by_id(self, tier_id: str) -> dict | None:
        for t in self._tiers_by_slug.values():
            if str(t.get("id")) == str(tier_id):
                return t
        return None

    async def get_estate_active_user_count(self, _estate_id: str) -> int:
        return self._active_user_count

    async def update_estate_subscription(
        self, sub_id: str, payload: dict
    ) -> dict:
        self.update_calls.append((sub_id, payload))
        for s in self._subscriptions:
            if str(s["id"]) == str(sub_id):
                s.update(payload)
                return s
        return payload

    async def create_estate_subscription(self, payload: dict) -> dict:
        if self._create_raises:
            raise RuntimeError("db-service unavailable")
        created = {"id": "sub-new", **payload}
        self.create_calls.append(created)
        self._subscriptions.append(created)
        self._active_sub = created
        return created

    async def delete_estate_subscription(self, sub_id: str) -> None:
        self.delete_calls.append(sub_id)
        self._subscriptions = [
            s for s in self._subscriptions if str(s["id"]) != str(sub_id)
        ]

    async def search_subscriptions(
        self, *, statuses: list[str], period_end_before: str
    ) -> list[dict]:
        cutoff = datetime.fromisoformat(period_end_before)
        results = []
        for s in self._subscriptions:
            if (s.get("status") or "").lower() not in statuses:
                continue
            pe = s.get("period_end")
            if pe:
                pe_dt = datetime.fromisoformat(str(pe).replace("Z", "+00:00"))
                if pe_dt < cutoff:
                    results.append(s)
        return results

    async def search_ai_grants(self, **kwargs: Any) -> list[dict]:
        return []

    async def search_stale_ai_grants(self, **kwargs: Any) -> list[dict]:
        return []

    async def search_subscriptions_pre_expiry(
        self, **kwargs: Any
    ) -> list[dict]:
        return []

    async def search_ai_grants_pre_expiry(self, **kwargs: Any) -> list[dict]:
        return []


# ── provision_access_subscription tests ──────────────────────────────────


class TestProvisionAccessSubscription:
    @pytest.mark.asyncio
    async def test_creates_access_row_when_none_exists(self):
        repo = FakeRepo(tiers_by_slug={"access": ACCESS_TIER})
        svc = SubscriptionService(repo, paystack_client=None)

        result = await svc.provision_access_subscription("estate-1")

        assert result["tier_id"] == "tier-access"
        assert result["status"] == "active"
        assert result["auto_renew"] is False
        assert result["covered_users"] == 3
        assert result["period_end"] is None
        assert len(repo.create_calls) == 1

    @pytest.mark.asyncio
    async def test_idempotent_returns_existing(self):
        existing = _make_sub(status="active")
        repo = FakeRepo(
            active_sub=existing,
            tiers_by_slug={"access": ACCESS_TIER},
        )
        svc = SubscriptionService(repo, paystack_client=None)

        result = await svc.provision_access_subscription("estate-1")

        assert result["id"] == existing["id"]
        assert len(repo.create_calls) == 0

    @pytest.mark.asyncio
    async def test_raises_when_access_tier_not_seeded(self):
        repo = FakeRepo(tiers_by_slug={})
        svc = SubscriptionService(repo, paystack_client=None)

        with pytest.raises(HTTPException) as exc:
            await svc.provision_access_subscription("estate-1")
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_dedup_guard_deletes_ours_when_duplicate_detected(self):
        """Simulate TOCTOU race: another row appears between
        check and create."""
        # Start with no active sub (get_active_subscription returns None)
        repo = FakeRepo(tiers_by_slug={"access": ACCESS_TIER})
        svc = SubscriptionService(repo, paystack_client=None)

        # Simulate a race: after create, inject a pre-existing active row
        # into the subscriptions list
        original_create = repo.create_estate_subscription

        async def create_and_inject_duplicate(payload: dict) -> dict:
            result = await original_create(payload)
            # Inject a row that looks like another concurrent call created it
            rival = {
                "id": "sub-rival",
                "status": "active",
                **{k: v for k, v in payload.items() if k != "id"},
            }
            repo._subscriptions.append(rival)
            return result

        repo.create_estate_subscription = create_and_inject_duplicate

        result = await svc.provision_access_subscription("estate-1")

        assert result["id"] == "sub-rival"
        assert "sub-new" in repo.delete_calls


# ── ExpiryService._expire_one tests ─────────────────────────────────────


class TestExpireOne:
    @pytest.mark.asyncio
    async def test_expire_one_creates_access_row_and_marks_expired(self):
        sub = _make_sub(status="active")
        repo = FakeRepo(
            subscriptions=[sub],
            active_user_count=2,
        )
        svc = ExpiryService(repo, paystack=AsyncMock())

        await svc._expire_one(sub, ACCESS_TIER, max_users=3)

        # Original sub marked expired
        assert sub["status"] == "expired"
        # New access row created
        assert len(repo.create_calls) == 1
        access_row = repo.create_calls[0]
        assert access_row["tier_id"] == "tier-access"
        assert access_row["status"] == "active"
        assert access_row["over_cap_locked"] is False

    @pytest.mark.asyncio
    async def test_expire_one_sets_over_cap_locked_when_over_limit(self):
        sub = _make_sub(status="active")
        repo = FakeRepo(
            subscriptions=[sub],
            active_user_count=5,
        )
        svc = ExpiryService(repo, paystack=AsyncMock())

        await svc._expire_one(sub, ACCESS_TIER, max_users=3)

        access_row = repo.create_calls[0]
        assert access_row["over_cap_locked"] is True

    @pytest.mark.asyncio
    async def test_expire_one_rollback_on_create_failure(self):
        sub = _make_sub(status="active")
        repo = FakeRepo(
            subscriptions=[sub],
            active_user_count=2,
            create_raises=True,
        )
        svc = ExpiryService(repo, paystack=AsyncMock())

        with pytest.raises(RuntimeError):
            await svc._expire_one(sub, ACCESS_TIER, max_users=3)

        # Status should have been rolled back to "active"
        restore_calls = [
            (sid, p)
            for sid, p in repo.update_calls
            if p.get("status") == "active"
        ]
        assert restore_calls, "Expected rollback to restore active status"


# ── ExpiryService._expire_subscriptions tests ───────────────────────────


class TestExpireSubscriptions:
    @pytest.mark.asyncio
    async def test_skips_entirely_when_access_tier_not_seeded(self):
        expired_sub = _make_sub(
            status="active",
            period_end=(
                datetime.now(tz=timezone.utc) - timedelta(days=30)
            ).isoformat(),
        )
        repo = FakeRepo(
            subscriptions=[expired_sub],
            tiers_by_slug={},  # no access tier
        )
        svc = ExpiryService(repo, paystack=AsyncMock())

        count = await svc._expire_subscriptions()

        assert count == 0
        # Sub should NOT have been expired
        assert expired_sub["status"] == "active"

    @pytest.mark.asyncio
    async def test_isolates_per_estate_failures(self):
        """One estate's failure should not prevent expiring others."""
        now = datetime.now(tz=timezone.utc)
        past = (now - timedelta(days=30)).isoformat()

        sub_ok = _make_sub(
            id="sub-ok",
            estate_id="estate-ok",
            status="active",
            period_end=past,
        )
        sub_bad = _make_sub(
            id="sub-bad",
            estate_id="estate-bad",
            status="active",
            period_end=past,
        )

        repo = FakeRepo(
            subscriptions=[sub_ok, sub_bad],
            tiers_by_slug={"access": ACCESS_TIER},
            active_user_count=1,
        )
        svc = ExpiryService(repo, paystack=AsyncMock())

        # Make the first _expire_one fail, second succeed
        call_count = 0
        original_expire = svc._expire_one

        async def flaky_expire(sub, access_tier, max_users):
            nonlocal call_count
            call_count += 1
            if str(sub["id"]) == "sub-bad":
                raise RuntimeError("simulated failure")
            return await original_expire(sub, access_tier, max_users)

        svc._expire_one = flaky_expire

        count = await svc._expire_subscriptions()

        # sub-ok should have been expired, sub-bad skipped
        assert count == 1
        assert sub_ok["status"] == "expired"
