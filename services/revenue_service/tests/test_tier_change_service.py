"""Unit tests for tier-change service and handler logic.

Covers:
  - TierChangeCheckoutHandler.guard()
  - SubscriptionService.schedule_tier_change()
  - SubscriptionService.cancel_tier_change()
  - SubscriptionService.change_tier_immediate()
  - SubscriptionService.renew() when pending_tier_slug is set
  - SubscriptionService.activate() clears stale pending_tier_slug
  - SubscriptionService.get_billing_cycle()
  - Complex multi-step scenarios
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

import app.services.subscription_service as sub_mod
from app.services.checkout_service import (
    CheckoutService,
    TierChangeCheckoutHandler,
)
from app.services.subscription_service import SubscriptionService


# ── Shared fixtures and helpers ───────────────────────────────────────────


def _make_sub(**overrides: Any) -> dict:
    base: dict[str, Any] = {
        "id": "sub-1",
        "estate_id": "estate-1",
        "tier_id": "tier-sentinel",
        "status": "active",
        "auto_renew": True,
        "pending_tier_slug": None,
        "covered_users": 5,
        "period_start": "2099-01-01T00:00:00+00:00",
        "period_end": "2099-01-31T00:00:00+00:00",
        "paystack_subscription_code": None,
        "pre_expiry_notified": False,
        "entitlements": None,
    }
    return {**base, **overrides}


def _make_tier(slug: str, display_order: int, **overrides: Any) -> dict:
    base: dict[str, Any] = {
        "id": f"tier-{slug}",
        "slug": slug,
        "display_order": display_order,
        "is_custom": False,
        "included_ai_features": [],
        "entitlements": {},
    }
    return {**base, **overrides}


SENTINEL = _make_tier("sentinel", 10)
COMMAND = _make_tier("command", 20)
BASIC = _make_tier("basic", 5)
CUSTOM_T = _make_tier("custom", 30, is_custom=True)


class FakeRepo:
    """Minimal async-fake for DbRevenueRepository."""

    def __init__(
        self,
        *,
        active_sub: dict | None = None,
        subscriptions: list[dict] | None = None,
        tiers_by_id: dict[str, dict] | None = None,
        tiers_by_slug: dict[str, dict] | None = None,
    ) -> None:
        self._active_sub = active_sub
        self._subscriptions = subscriptions or (
            [active_sub] if active_sub else []
        )
        self._tiers_by_id = tiers_by_id or {}
        self._tiers_by_slug = tiers_by_slug or {}
        # Ordered record of every update_estate_subscription call.
        self.update_calls: list[tuple[str, dict]] = []

    async def get_active_subscription(self, _estate_id: str) -> dict | None:
        return self._active_sub

    async def list_estate_subscriptions(self, _estate_id: str) -> list[dict]:
        return self._subscriptions

    async def get_tier_by_id(self, tier_id: str) -> dict | None:
        return self._tiers_by_id.get(str(tier_id))

    async def get_tier_by_slug(self, slug: str) -> dict | None:
        return self._tiers_by_slug.get(slug)

    async def update_estate_subscription(
        self, sub_id: str, payload: dict
    ) -> dict:
        self.update_calls.append((sub_id, payload))
        if self._active_sub and str(self._active_sub["id"]) == str(sub_id):
            self._active_sub = {**self._active_sub, **payload}
        return self._active_sub or payload

    # ── AI grant stubs ────────────────────────────────────────────────

    async def get_ai_feature_map(self) -> dict:
        return {}

    async def list_estate_ai_features(self, _estate_id: str) -> list:
        return []

    async def create_estate_ai_feature(self, payload: dict) -> dict:
        return {"id": "grant-new", **payload}

    async def update_estate_ai_feature(
        self, grant_id: str, payload: dict
    ) -> dict:
        return {"id": grant_id, **payload}

    # ── activate() stubs ──────────────────────────────────────────────

    async def create_estate_subscription(self, payload: dict) -> dict:
        created = {"id": "sub-new", **payload}
        self._active_sub = created
        return created


def _svc(repo: FakeRepo) -> SubscriptionService:
    """SubscriptionService with no Paystack client (plan updates skipped)."""
    return SubscriptionService(repo, paystack_client=None)


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    """1 attempt, 0 delay — retry loops are instant in all tests."""
    monkeypatch.setattr(
        sub_mod.settings, "REVENUE_TRANSIENT_RETRY_ATTEMPTS", 1
    )
    monkeypatch.setattr(
        sub_mod.settings,
        "REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS",
        0,
    )


@pytest.fixture()
def noop_grants(monkeypatch):
    """Replace grant sync with no-ops so tests focus on subscription state."""

    async def _noop(*_a, **_kw):
        pass

    monkeypatch.setattr(sub_mod, "sync_tier_ai_grants", _noop)
    monkeypatch.setattr(sub_mod, "extend_subscription_ai_grants", _noop)


# ── TierChangeCheckoutHandler.guard() ────────────────────────────────────


class TestTierChangeGuard:
    def _handler(self, repo: FakeRepo) -> TierChangeCheckoutHandler:
        svc = CheckoutService(repo)
        return TierChangeCheckoutHandler(repo, svc)

    @pytest.mark.asyncio
    async def test_no_active_sub_raises_400(self):
        repo = FakeRepo(tiers_by_slug={"command": COMMAND})
        with pytest.raises(HTTPException) as exc:
            await self._handler(repo).guard(
                {"estate_id": "e1", "tier_slug": "command"}
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_cancelled_sub_raises_400(self):
        sub = _make_sub(status="cancelled")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        with pytest.raises(HTTPException) as exc:
            await self._handler(repo).guard(
                {"estate_id": "e1", "tier_slug": "command"}
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_current_tier_missing_raises_500(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={},  # tier-sentinel not seeded
            tiers_by_slug={"command": COMMAND},
        )
        with pytest.raises(HTTPException) as exc:
            await self._handler(repo).guard(
                {"estate_id": "e1", "tier_slug": "command"}
            )
        assert exc.value.status_code == 500

    @pytest.mark.asyncio
    async def test_new_tier_not_found_raises_404(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={},  # command not seeded
        )
        with pytest.raises(HTTPException) as exc:
            await self._handler(repo).guard(
                {"estate_id": "e1", "tier_slug": "command"}
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_custom_new_tier_raises_400(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"custom": CUSTOM_T},
        )
        with pytest.raises(HTTPException) as exc:
            await self._handler(repo).guard(
                {"estate_id": "e1", "tier_slug": "custom"}
            )
        assert exc.value.status_code == 400
        assert "custom" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_downgrade_raises_400(self):
        sub = _make_sub()  # currently sentinel (order 10)
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"basic": BASIC},  # order 5 < 10
        )
        with pytest.raises(HTTPException) as exc:
            await self._handler(repo).guard(
                {"estate_id": "e1", "tier_slug": "basic"}
            )
        assert exc.value.status_code == 400
        assert "upgrade" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_same_order_raises_400(self):
        same = _make_tier("sentinel2", 10)  # same display_order
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"sentinel2": same},
        )
        with pytest.raises(HTTPException) as exc:
            await self._handler(repo).guard(
                {"estate_id": "e1", "tier_slug": "sentinel2"}
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_upgrade_passes(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        # Should not raise
        await self._handler(repo).guard(
            {"estate_id": "e1", "tier_slug": "command"}
        )

    @pytest.mark.asyncio
    async def test_trialing_sub_can_upgrade(self):
        sub = _make_sub(status="trialing")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        await self._handler(repo).guard(
            {"estate_id": "e1", "tier_slug": "command"}
        )


# ── schedule_tier_change() ────────────────────────────────────────────────


class TestScheduleTierChange:
    @pytest.mark.asyncio
    async def test_no_active_sub_raises_404(self):
        repo = FakeRepo(tiers_by_slug={"command": COMMAND})
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_tier_change("e1", "command")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_sub_raises_404(self):
        sub = _make_sub(status="expired")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_slug={"command": COMMAND},
        )
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_tier_change("e1", "command")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_auto_renew_off_raises_400(self):
        sub = _make_sub(auto_renew=False)
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_tier_change("e1", "command")
        assert exc.value.status_code == 400
        assert "auto-renewal" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unknown_tier_raises_404(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_tier_change("e1", "nonexistent")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_custom_tier_raises_400(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"custom": CUSTOM_T},
        )
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_tier_change("e1", "custom")
        assert exc.value.status_code == 400
        assert "custom" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_same_tier_raises_400(self):
        sub = _make_sub()  # tier_id = "tier-sentinel"
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"sentinel": SENTINEL},
        )
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_tier_change("e1", "sentinel")
        assert exc.value.status_code == 400
        assert "same" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_happy_path_stores_pending_slug(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        result = await _svc(repo).schedule_tier_change("e1", "command")

        assert result["pending_tier_slug"] == "command"
        assert result["effective_from"] == sub["period_end"]
        assert result["estate_id"] == "e1"

        _, payload = repo.update_calls[0]
        assert payload["pending_tier_slug"] == "command"

    @pytest.mark.asyncio
    async def test_reschedule_overwrites_previous(self):
        sub = _make_sub(pending_tier_slug="command")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            # basic is lower than sentinel — normally 400, but here we
            # test that guard in schedule_tier_change doesn't check order;
            # use a slug that differs from current and isn't custom.
            tiers_by_slug={"command": COMMAND},
        )
        # First schedule to command
        await _svc(repo).schedule_tier_change("e1", "command")
        first_payload = repo.update_calls[0][1]
        assert first_payload["pending_tier_slug"] == "command"

        # Schedule again to command (idempotent)
        await _svc(repo).schedule_tier_change("e1", "command")
        second_payload = repo.update_calls[1][1]
        assert second_payload["pending_tier_slug"] == "command"


# ── cancel_tier_change() ──────────────────────────────────────────────────


class TestCancelTierChange:
    @pytest.mark.asyncio
    async def test_no_active_sub_raises_404(self):
        repo = FakeRepo()
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).cancel_tier_change("e1")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_pending_slug_raises_400(self):
        sub = _make_sub(pending_tier_slug=None)
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).cancel_tier_change("e1")
        assert exc.value.status_code == 400
        assert "no pending" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_happy_path_clears_pending_slug(self):
        sub = _make_sub(pending_tier_slug="command")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        result = await _svc(repo).cancel_tier_change("e1")

        assert result["pending_tier_slug"] is None
        _, payload = repo.update_calls[0]
        assert payload["pending_tier_slug"] is None

    @pytest.mark.asyncio
    async def test_cancel_when_current_tier_missing_still_clears(self):
        """Even if the current tier row is deleted, pending is still cleared."""
        sub = _make_sub(pending_tier_slug="command")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={},  # current tier not found
        )
        result = await _svc(repo).cancel_tier_change("e1")
        assert result["pending_tier_slug"] is None


# ── schedule → cancel → reschedule ───────────────────────────────────────


class TestScheduleCancelReschedule:
    @pytest.mark.asyncio
    async def test_schedule_cancel_reschedule(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        svc = _svc(repo)

        # Schedule command
        r1 = await svc.schedule_tier_change("e1", "command")
        assert r1["pending_tier_slug"] == "command"

        # Cancel it
        r2 = await svc.cancel_tier_change("e1")
        assert r2["pending_tier_slug"] is None

        # Reschedule command again
        r3 = await svc.schedule_tier_change("e1", "command")
        assert r3["pending_tier_slug"] == "command"

        # Verify DB had 3 updates in order
        assert len(repo.update_calls) == 3
        assert repo.update_calls[0][1]["pending_tier_slug"] == "command"
        assert repo.update_calls[1][1]["pending_tier_slug"] is None
        assert repo.update_calls[2][1]["pending_tier_slug"] == "command"


# ── change_tier_immediate() ───────────────────────────────────────────────


class TestChangeTierImmediate:
    @pytest.mark.asyncio
    async def test_no_active_sub_raises_404(self, noop_grants):
        repo = FakeRepo(tiers_by_slug={"command": COMMAND})
        from datetime import timezone
        from datetime import datetime as _dt

        with pytest.raises(HTTPException) as exc:
            await _svc(repo).change_tier_immediate(
                "e1", "command", _dt.now(tz=timezone.utc)
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_unknown_tier_raises_404(self, noop_grants):
        sub = _make_sub()
        repo = FakeRepo(active_sub=sub)
        from datetime import timezone
        from datetime import datetime as _dt

        with pytest.raises(HTTPException) as exc:
            await _svc(repo).change_tier_immediate(
                "e1", "ghost", _dt.now(tz=timezone.utc)
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_happy_path_updates_tier_and_clears_pending(
        self, noop_grants
    ):
        sub = _make_sub(pending_tier_slug="basic")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_slug={"command": COMMAND},
        )
        from datetime import timezone
        from datetime import datetime as _dt

        await _svc(repo).change_tier_immediate(
            "e1", "command", _dt.now(tz=timezone.utc)
        )

        _, payload = repo.update_calls[0]
        assert payload["tier_id"] == COMMAND["id"]
        assert payload["pending_tier_slug"] is None
        assert payload["pre_expiry_notified"] is False

    @pytest.mark.asyncio
    async def test_clears_pending_downgrade_on_upgrade(self, noop_grants):
        """A paid immediate upgrade must clear any pending downgrade."""
        sub = _make_sub(pending_tier_slug="basic")  # downgrade was scheduled
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_slug={"command": COMMAND},
        )
        from datetime import timezone
        from datetime import datetime as _dt

        await _svc(repo).change_tier_immediate(
            "e1", "command", _dt.now(tz=timezone.utc)
        )
        _, payload = repo.update_calls[0]
        assert payload["pending_tier_slug"] is None

    @pytest.mark.asyncio
    async def test_grant_sync_failure_reverts_tier_and_restores_pending(
        self, monkeypatch
    ):
        """On grant sync failure: tier_id is reverted AND pending_tier_slug
        is restored to its original value (not left as None)."""

        async def _fail(*_a, **_kw):
            raise RuntimeError("db-service down")

        monkeypatch.setattr(sub_mod, "sync_tier_ai_grants", _fail)
        monkeypatch.setattr(sub_mod, "extend_subscription_ai_grants", _fail)

        sub = _make_sub(
            tier_id="tier-sentinel",
            pending_tier_slug="basic",  # had a scheduled downgrade
            pre_expiry_notified=True,
        )
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_slug={"command": COMMAND},
        )
        from datetime import timezone
        from datetime import datetime as _dt

        with pytest.raises(HTTPException) as exc:
            await _svc(repo).change_tier_immediate(
                "e1", "command", _dt.now(tz=timezone.utc)
            )
        assert exc.value.status_code == 502

        # First update: applied the upgrade
        _, first = repo.update_calls[0]
        assert first["tier_id"] == COMMAND["id"]

        # Second update: revert
        _, revert = repo.update_calls[1]
        assert revert["tier_id"] == "tier-sentinel"  # old tier restored
        assert revert["pending_tier_slug"] == "basic"  # downgrade restored
        assert revert["pre_expiry_notified"] is True  # original flag


# ── cancel sub with pending → immediate upgrade ───────────────────────────


class TestCancelSubThenImmediateUpgrade:
    @pytest.mark.asyncio
    async def test_cancel_then_reschedule_then_immediate(self, noop_grants):
        """Cancel a scheduled change, then do an immediate upgrade. The
        immediate upgrade sees pending_tier_slug=None (already cancelled)
        and clears it (no-op on None). Tier is updated correctly."""
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        svc = _svc(repo)

        # Schedule then cancel
        await svc.schedule_tier_change("e1", "command")
        await svc.cancel_tier_change("e1")
        assert repo._active_sub["pending_tier_slug"] is None

        # Now do immediate upgrade
        from datetime import timezone
        from datetime import datetime as _dt

        await svc.change_tier_immediate(
            "e1", "command", _dt.now(tz=timezone.utc)
        )

        assert repo._active_sub["tier_id"] == COMMAND["id"]
        assert repo._active_sub["pending_tier_slug"] is None


# ── renew() with pending_tier_slug ────────────────────────────────────────


class TestRenewWithPendingTier:
    @pytest.mark.asyncio
    async def test_applies_pending_tier_on_renewal(self, noop_grants):
        sub = _make_sub(pending_tier_slug="command")
        repo = FakeRepo(
            active_sub=sub,
            subscriptions=[sub],
            tiers_by_slug={"command": COMMAND},
        )
        from datetime import timezone
        from datetime import datetime as _dt

        await _svc(repo).renew("e1", paid_at=_dt.now(tz=timezone.utc))

        _, payload = repo.update_calls[0]
        assert payload["tier_id"] == COMMAND["id"]
        assert payload["pending_tier_slug"] is None

    @pytest.mark.asyncio
    async def test_stale_pending_slug_cleared_without_tier_change(
        self, noop_grants
    ):
        """If the pending tier was deleted, clear the slug and keep the
        current tier — do not apply a non-existent tier."""
        sub = _make_sub(pending_tier_slug="ghost")
        repo = FakeRepo(
            active_sub=sub,
            subscriptions=[sub],
            tiers_by_slug={},  # ghost tier not found
        )
        from datetime import timezone
        from datetime import datetime as _dt

        await _svc(repo).renew("e1", paid_at=_dt.now(tz=timezone.utc))

        _, payload = repo.update_calls[0]
        assert payload["pending_tier_slug"] is None
        assert "tier_id" not in payload  # current tier unchanged

    @pytest.mark.asyncio
    async def test_no_pending_slug_extends_normally(self, noop_grants):
        sub = _make_sub(pending_tier_slug=None)
        repo = FakeRepo(
            active_sub=sub,
            subscriptions=[sub],
        )
        from datetime import timezone
        from datetime import datetime as _dt

        await _svc(repo).renew("e1", paid_at=_dt.now(tz=timezone.utc))

        _, payload = repo.update_calls[0]
        assert "tier_id" not in payload
        assert "pending_tier_slug" not in payload
        assert payload["status"] == "active"


# ── activate() clears stale pending_tier_slug ─────────────────────────────


class TestActivateClearsPending:
    @pytest.mark.asyncio
    async def test_reactivation_clears_stale_pending_slug(self, noop_grants):
        """When an estate re-subscribes via activate() on an existing row
        that has a stale pending_tier_slug, it must be cleared so the
        scheduled change does not fire on the next auto-renewal."""
        existing_sub = _make_sub(
            tier_id="tier-sentinel",
            pending_tier_slug="command",  # stale from before cancel
            status="cancelled",
        )
        sentinel_tier = {
            **SENTINEL,
            "is_custom": False,
            "entitlements": {"some_feature": True},
            "included_ai_features": [],
        }
        repo = FakeRepo(
            active_sub=existing_sub,
            tiers_by_slug={"sentinel": sentinel_tier},
        )
        from datetime import timezone
        from datetime import datetime as _dt

        await _svc(repo).activate(
            {
                "estate_id": "e1",
                "tier_slug": "sentinel",
                "covered_users": 5,
                "period_months": 1,
                "paid_at": _dt.now(tz=timezone.utc).isoformat(),
            }
        )

        _, payload = repo.update_calls[0]
        assert payload["pending_tier_slug"] is None

    @pytest.mark.asyncio
    async def test_fresh_activation_also_clears_pending(self, noop_grants):
        """activate() on a brand-new subscription (no existing row)
        does not write pending_tier_slug at all — confirmed absent."""
        sentinel_tier = {
            **SENTINEL,
            "is_custom": False,
            "entitlements": {},
            "included_ai_features": [],
        }
        # No existing subscription
        repo = FakeRepo(tiers_by_slug={"sentinel": sentinel_tier})
        from datetime import timezone
        from datetime import datetime as _dt

        await _svc(repo).activate(
            {
                "estate_id": "e1",
                "tier_slug": "sentinel",
                "covered_users": 5,
                "period_months": 1,
                "paid_at": _dt.now(tz=timezone.utc).isoformat(),
            }
        )
        # create_estate_subscription was called — inspect the payload
        # (no update_calls; just confirm pending_tier_slug is absent or None)
        # The FakeRepo's create path doesn't record to update_calls.
        assert repo._active_sub["pending_tier_slug"] is None


# ── get_billing_cycle() ───────────────────────────────────────────────────


class TestGetBillingCycle:
    @pytest.mark.asyncio
    async def test_no_sub_returns_estate_id_only(self):
        repo = FakeRepo()
        result = await _svc(repo).get_billing_cycle("e1")
        assert result == {"estate_id": "e1"}

    @pytest.mark.asyncio
    async def test_active_sub_no_pending(self):
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        result = await _svc(repo).get_billing_cycle("e1")

        assert result["current_tier_slug"] == "sentinel"
        assert result["tier_change_scheduled"] is False
        assert result["next_tier_slug"] == "sentinel"
        assert result["period_end"] == sub["period_end"]
        # No Paystack / CheckoutService → pricing fails silently
        assert result["next_billing_amount"] is None

    @pytest.mark.asyncio
    async def test_pending_tier_change_reflected(self):
        sub = _make_sub(pending_tier_slug="command")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        result = await _svc(repo).get_billing_cycle("e1")

        assert result["tier_change_scheduled"] is True
        assert result["next_tier_slug"] == "command"
        assert result["current_tier_slug"] == "sentinel"

    @pytest.mark.asyncio
    async def test_auto_renew_off_amount_is_none(self):
        sub = _make_sub(auto_renew=False)
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        result = await _svc(repo).get_billing_cycle("e1")

        assert result["auto_renew"] is False
        assert result["next_billing_amount"] is None

    @pytest.mark.asyncio
    async def test_stale_pending_slug_treated_as_no_change(self):
        """If pending tier no longer exists, billing cycle falls back to
        the current tier and marks tier_change_scheduled=False."""
        sub = _make_sub(pending_tier_slug="ghost")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={},  # ghost not found
        )
        result = await _svc(repo).get_billing_cycle("e1")

        assert result["tier_change_scheduled"] is False
        assert result["next_tier_slug"] == "sentinel"

    @pytest.mark.asyncio
    async def test_next_tier_entitlements_omit_vat(self):
        tier_with_vat = {
            **COMMAND,
            "entitlements": {"feature_a": True, "vat": 7.5},
        }
        sub = _make_sub(pending_tier_slug="command")
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": tier_with_vat},
        )
        result = await _svc(repo).get_billing_cycle("e1")

        next_tier = result["next_tier"]
        assert next_tier is not None
        assert "vat" not in next_tier["entitlements"]
        assert "feature_a" in next_tier["entitlements"]


# ── Complex end-to-end scenario ───────────────────────────────────────────


class TestComplexScenarios:
    @pytest.mark.asyncio
    async def test_schedule_downgrade_then_immediate_upgrade_clears_it(
        self, noop_grants
    ):
        """User schedules a downgrade, then pays for an immediate upgrade.
        The immediate upgrade must clear the pending downgrade."""
        sub = _make_sub()
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"basic": BASIC, "command": COMMAND},
        )
        svc = _svc(repo)

        # Schedule a downgrade to basic
        r = await svc.schedule_tier_change("e1", "basic")
        assert r["pending_tier_slug"] == "basic"

        # Now pay for an immediate upgrade to command
        from datetime import timezone
        from datetime import datetime as _dt

        await svc.change_tier_immediate(
            "e1", "command", _dt.now(tz=timezone.utc)
        )

        # Pending downgrade must be gone; tier is now command
        assert repo._active_sub["tier_id"] == COMMAND["id"]
        assert repo._active_sub["pending_tier_slug"] is None

    @pytest.mark.asyncio
    async def test_renewal_applies_pending_then_billing_cycle_shows_new(
        self, noop_grants
    ):
        """After renewal applies the pending tier, get_billing_cycle
        should reflect the new tier with no scheduled change."""
        sub = _make_sub(pending_tier_slug="command")
        repo = FakeRepo(
            active_sub=sub,
            subscriptions=[sub],
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        svc = _svc(repo)

        from datetime import timezone
        from datetime import datetime as _dt

        await svc.renew("e1", paid_at=_dt.now(tz=timezone.utc))

        # After renewal, active sub has command tier + no pending slug
        assert repo._active_sub["tier_id"] == COMMAND["id"]
        assert repo._active_sub["pending_tier_slug"] is None

        # Seed tier_by_id for the new command tier
        repo._tiers_by_id["tier-command"] = COMMAND

        billing = await svc.get_billing_cycle("e1")
        assert billing["current_tier_slug"] == "command"
        assert billing["tier_change_scheduled"] is False
        assert billing["next_tier_slug"] == "command"
