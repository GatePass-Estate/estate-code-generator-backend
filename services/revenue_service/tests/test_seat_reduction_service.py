"""Unit tests for scheduled seat reduction service logic.

Covers:
  - SubscriptionService.get_seat_reduction_eligibility()
  - SubscriptionService.schedule_seat_reduction()
  - SubscriptionService.cancel_seat_reduction()
  - SubscriptionService.renew() when pending_covered_users is set
  - SubscriptionService.renew() when both pending_covered_users and
    pending_tier_slug are set simultaneously
  - SubscriptionService.activate() clears stale pending_covered_users
  - SubscriptionService.get_estate_subscription() effective_covered_users
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

import app.services.subscription_service as sub_mod
from app.services.subscription_service import SubscriptionService


# ── Helpers and fixtures ──────────────────────────────────────────────────


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


class FakeRepo:
    """Minimal async-fake for DbRevenueRepository."""

    def __init__(
        self,
        *,
        active_sub: dict | None = None,
        subscriptions: list[dict] | None = None,
        tiers_by_id: dict[str, dict] | None = None,
        tiers_by_slug: dict[str, dict] | None = None,
        active_user_count: int = 0,
    ) -> None:
        self._active_sub = active_sub
        self._subscriptions = subscriptions or (
            [active_sub] if active_sub else []
        )
        self._tiers_by_id = tiers_by_id or {}
        self._tiers_by_slug = tiers_by_slug or {}
        self._active_user_count = active_user_count
        self.update_calls: list[tuple[str, dict]] = []

    async def get_active_subscription(self, _estate_id: str) -> dict | None:
        return self._active_sub

    async def list_estate_subscriptions(self, _estate_id: str) -> list[dict]:
        return self._subscriptions

    async def get_tier_by_id(self, tier_id: str) -> dict | None:
        return self._tiers_by_id.get(str(tier_id))

    async def get_tier_by_slug(self, slug: str) -> dict | None:
        return self._tiers_by_slug.get(slug)

    async def get_estate_active_user_count(self, _estate_id: str) -> int:
        return self._active_user_count

    async def update_estate_subscription(
        self, sub_id: str, payload: dict
    ) -> dict:
        self.update_calls.append((sub_id, payload))
        if self._active_sub and str(self._active_sub["id"]) == str(sub_id):
            self._active_sub = {**self._active_sub, **payload}
        return self._active_sub or payload

    async def create_estate_subscription(self, payload: dict) -> dict:
        created = {"id": "sub-new", **payload}
        self._active_sub = created
        return created

    # AI grant stubs
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

    # Tier lookup stubs
    async def get_tier_price_by_slug(
        self, slug: str, country_code: str
    ) -> dict | None:
        return None


def _svc(repo: FakeRepo) -> SubscriptionService:
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


# ── get_seat_reduction_eligibility() ─────────────────────────────────────


class TestGetSeatReductionEligibility:
    @pytest.mark.asyncio
    async def test_no_active_sub_raises_404(self):
        repo = FakeRepo()
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).get_seat_reduction_eligibility("e1")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_sub_raises_404(self):
        sub = _make_sub(status="expired")
        repo = FakeRepo(active_sub=sub, active_user_count=3)
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).get_seat_reduction_eligibility("e1")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_can_reduce_when_seats_exceed_active_users(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=6)
        result = await _svc(repo).get_seat_reduction_eligibility("e1")
        assert result["can_reduce"] is True
        assert result["current_seats"] == 10
        assert result["active_users"] == 6
        assert result["min_allowed_seats"] == 6

    @pytest.mark.asyncio
    async def test_cannot_reduce_when_seats_equal_active_users(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=10)
        result = await _svc(repo).get_seat_reduction_eligibility("e1")
        assert result["can_reduce"] is False
        assert result["min_allowed_seats"] == 10

    @pytest.mark.asyncio
    async def test_cannot_reduce_when_active_users_exceed_seats(self):
        # Edge case: over-provisioned (should not happen but is safe)
        sub = _make_sub(covered_users=5)
        repo = FakeRepo(active_sub=sub, active_user_count=8)
        result = await _svc(repo).get_seat_reduction_eligibility("e1")
        assert result["can_reduce"] is False

    @pytest.mark.asyncio
    async def test_returns_all_expected_keys(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=4)
        result = await _svc(repo).get_seat_reduction_eligibility("e1")
        for key in (
            "estate_id",
            "can_reduce",
            "current_seats",
            "active_users",
            "min_allowed_seats",
        ):
            assert key in result, f"missing key: {key}"

    @pytest.mark.asyncio
    async def test_trialing_sub_is_eligible(self):
        sub = _make_sub(status="trialing", covered_users=8)
        repo = FakeRepo(active_sub=sub, active_user_count=3)
        result = await _svc(repo).get_seat_reduction_eligibility("e1")
        assert result["can_reduce"] is True


# ── schedule_seat_reduction() ────────────────────────────────────────────


class TestScheduleSeatReduction:
    @pytest.mark.asyncio
    async def test_no_active_sub_raises_404(self):
        repo = FakeRepo()
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_seat_reduction("e1", 5)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_expired_sub_raises_404(self):
        sub = _make_sub(status="expired")
        repo = FakeRepo(active_sub=sub, active_user_count=3)
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_seat_reduction("e1", 5)
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_zero_seats_raises_400(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=0)
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_seat_reduction("e1", 0)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_same_as_current_raises_400(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=5)
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_seat_reduction("e1", 10)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_more_than_current_raises_400(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=5)
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_seat_reduction("e1", 15)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_below_active_users_raises_400(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=8)
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).schedule_seat_reduction("e1", 7)
        assert exc.value.status_code == 400
        assert "active user count" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_happy_path_stores_pending_covered_users(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=6)
        result = await _svc(repo).schedule_seat_reduction("e1", 7)
        assert result["pending_covered_users"] == 7
        assert result["estate_id"] == "e1"
        # DB write happened
        assert len(repo.update_calls) == 1
        _sub_id, payload = repo.update_calls[0]
        assert payload["pending_covered_users"] == 7

    @pytest.mark.asyncio
    async def test_reduction_to_active_user_count_is_allowed(self):
        """Edge: reducing exactly to active_users is the minimum allowed."""
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=5)
        result = await _svc(repo).schedule_seat_reduction("e1", 5)
        assert result["pending_covered_users"] == 5

    @pytest.mark.asyncio
    async def test_returns_effective_from_period_end(self):
        sub = _make_sub(
            covered_users=10,
            period_end="2026-01-31T00:00:00+00:00",
        )
        repo = FakeRepo(active_sub=sub, active_user_count=3)
        result = await _svc(repo).schedule_seat_reduction("e1", 5)
        assert result["effective_from"] is not None
        assert "2026-01-31" in result["effective_from"]

    @pytest.mark.asyncio
    async def test_covered_users_not_changed_immediately(self):
        """schedule_seat_reduction must NOT change covered_users — only pending."""
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=4)
        await _svc(repo).schedule_seat_reduction("e1", 6)
        _sub_id, payload = repo.update_calls[0]
        assert "covered_users" not in payload

    @pytest.mark.asyncio
    async def test_trialing_sub_can_schedule_reduction(self):
        sub = _make_sub(status="trialing", covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=4)
        result = await _svc(repo).schedule_seat_reduction("e1", 6)
        assert result["pending_covered_users"] == 6


# ── cancel_seat_reduction() ──────────────────────────────────────────────


class TestCancelSeatReduction:
    @pytest.mark.asyncio
    async def test_no_active_sub_raises_404(self):
        repo = FakeRepo()
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).cancel_seat_reduction("e1")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_pending_reduction_raises_400(self):
        sub = _make_sub(pending_covered_users=None)
        repo = FakeRepo(active_sub=sub)
        with pytest.raises(HTTPException) as exc:
            await _svc(repo).cancel_seat_reduction("e1")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_happy_path_clears_pending_covered_users(self):
        sub = _make_sub(pending_covered_users=6)
        repo = FakeRepo(active_sub=sub)
        result = await _svc(repo).cancel_seat_reduction("e1")
        assert result["pending_covered_users"] is None
        _sub_id, payload = repo.update_calls[0]
        assert payload["pending_covered_users"] is None

    @pytest.mark.asyncio
    async def test_covered_users_unchanged_on_cancel(self):
        """Cancel must not alter covered_users."""
        sub = _make_sub(covered_users=10, pending_covered_users=6)
        repo = FakeRepo(active_sub=sub)
        await _svc(repo).cancel_seat_reduction("e1")
        _sub_id, payload = repo.update_calls[0]
        assert "covered_users" not in payload

    @pytest.mark.asyncio
    async def test_schedule_then_cancel_leaves_clean_state(self):
        sub = _make_sub(covered_users=10)
        repo = FakeRepo(active_sub=sub, active_user_count=4)
        await _svc(repo).schedule_seat_reduction("e1", 6)
        await _svc(repo).cancel_seat_reduction("e1")
        # After cancel, pending_covered_users is None on the in-memory sub
        assert repo._active_sub["pending_covered_users"] is None
        # covered_users is still 10
        assert repo._active_sub["covered_users"] == 10


# ── renew() applies pending_covered_users ────────────────────────────────


class TestRenewAppliesPendingSeats:
    @pytest.mark.asyncio
    async def test_renew_applies_pending_covered_users(
        self, noop_grants, monkeypatch
    ):
        sub = _make_sub(
            covered_users=10,
            pending_covered_users=7,
            period_end="2026-01-31T00:00:00+00:00",
        )
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        # Stub compute_period_end to avoid date arithmetic issues
        monkeypatch.setattr(
            sub_mod,
            "compute_period_end",
            lambda **kw: kw["paid_at"]
            + __import__("datetime").timedelta(days=30),
        )
        await _svc(repo).renew("estate-1")
        # Find the main update_payload call (the one that sets period_start)
        main_calls = [
            (sid, p) for sid, p in repo.update_calls if "covered_users" in p
        ]
        assert main_calls, "expected covered_users to be written in renew()"
        _sid, payload = main_calls[0]
        assert payload["covered_users"] == 7
        assert payload["pending_covered_users"] is None

    @pytest.mark.asyncio
    async def test_renew_without_pending_seats_leaves_covered_users_unchanged(
        self, noop_grants, monkeypatch
    ):
        sub = _make_sub(covered_users=10, pending_covered_users=None)
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        monkeypatch.setattr(
            sub_mod,
            "compute_period_end",
            lambda **kw: kw["paid_at"]
            + __import__("datetime").timedelta(days=30),
        )
        await _svc(repo).renew("estate-1")
        # If pending_covered_users appears in any write it must be None
        # (clearing an already-None field, not reducing seats).
        for _, p in repo.update_calls:
            if "pending_covered_users" in p:
                assert p["pending_covered_users"] is None

    @pytest.mark.asyncio
    async def test_renew_applies_both_pending_tier_and_pending_seats(
        self, noop_grants, monkeypatch
    ):
        """Both pending_tier_slug and pending_covered_users applied in one renew()."""
        sub = _make_sub(
            covered_users=10,
            pending_covered_users=6,
            pending_tier_slug="command",
            tier_id="tier-sentinel",
        )
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"command": COMMAND},
        )
        monkeypatch.setattr(
            sub_mod,
            "compute_period_end",
            lambda **kw: kw["paid_at"]
            + __import__("datetime").timedelta(days=30),
        )
        await _svc(repo).renew("estate-1")
        # The combined update must include both changes
        combined_writes = [
            p
            for _, p in repo.update_calls
            if "covered_users" in p and "tier_id" in p
        ]
        assert combined_writes, "expected a single update with both fields"
        payload = combined_writes[0]
        assert payload["covered_users"] == 6
        assert payload["pending_covered_users"] is None
        assert payload["tier_id"] == COMMAND["id"]
        assert payload["pending_tier_slug"] is None

    @pytest.mark.asyncio
    async def test_renew_rollback_includes_pending_covered_users(
        self, monkeypatch
    ):
        """On grant sync failure, pending_covered_users must be restored."""
        sub = _make_sub(
            covered_users=10,
            pending_covered_users=6,
        )
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        monkeypatch.setattr(
            sub_mod,
            "compute_period_end",
            lambda **kw: kw["paid_at"]
            + __import__("datetime").timedelta(days=30),
        )

        # Force grant sync to fail
        async def _fail(*_a, **_kw):
            raise RuntimeError("grant sync exploded")

        monkeypatch.setattr(sub_mod, "sync_tier_ai_grants", _fail)
        monkeypatch.setattr(sub_mod, "extend_subscription_ai_grants", _fail)

        with pytest.raises(HTTPException):
            await _svc(repo).renew("estate-1")

        # The rollback call must restore pending_covered_users=6
        rollback_calls = [
            p
            for _, p in repo.update_calls
            if "pending_covered_users" in p
            and p.get("pending_covered_users") == 6
        ]
        assert rollback_calls, "rollback must restore pending_covered_users=6"


# ── activate() clears pending_covered_users ──────────────────────────────


class TestActivateClearsPendingSeats:
    @pytest.mark.asyncio
    async def test_activate_clears_stale_pending_covered_users(
        self, noop_grants
    ):
        """Re-activating a subscription with stale pending_covered_users clears it."""
        existing_sub = _make_sub(
            covered_users=10, pending_covered_users=4, status="cancelled"
        )
        repo = FakeRepo(
            active_sub=existing_sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"sentinel": SENTINEL},
        )
        await _svc(repo).activate(
            {
                "estate_id": "estate-1",
                "tier_slug": "sentinel",
                "covered_users": 10,
                "period_months": 1,
            }
        )
        # The update payload for activate must set pending_covered_users=None
        activate_calls = [
            p for _, p in repo.update_calls if "pending_covered_users" in p
        ]
        assert (
            activate_calls
        ), "activate() must write pending_covered_users in its payload"
        assert activate_calls[0]["pending_covered_users"] is None

    @pytest.mark.asyncio
    async def test_activate_does_not_inherit_old_pending_seats(
        self, noop_grants
    ):
        """After activate(), new subscription must not have pending_covered_users."""
        existing_sub = _make_sub(
            covered_users=20, pending_covered_users=8, status="expired"
        )
        repo = FakeRepo(
            active_sub=existing_sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"sentinel": SENTINEL},
        )
        await _svc(repo).activate(
            {
                "estate_id": "estate-1",
                "tier_slug": "sentinel",
                "covered_users": 5,
                "period_months": 1,
            }
        )
        assert repo._active_sub.get("pending_covered_users") is None


# ── get_estate_subscription() effective_covered_users ────────────────────


class TestGetEstateSubscriptionEffectiveCoveredUsers:
    @pytest.mark.asyncio
    async def test_no_pending_uses_covered_users(self, monkeypatch):
        sub = _make_sub(covered_users=10, pending_covered_users=None)
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"access": _make_tier("access", 0)},
        )
        # Stub resolve_entitlements and omit_vat to avoid full context setup
        monkeypatch.setattr(
            sub_mod,
            "resolve_entitlements",
            lambda **kw: {},
        )
        monkeypatch.setattr(sub_mod, "omit_vat", lambda x: x)
        result = await _svc(repo).get_estate_subscription("estate-1")
        assert result["covered_users"] == 10
        assert result["pending_covered_users"] is None
        assert result["effective_covered_users"] == 10

    @pytest.mark.asyncio
    async def test_with_pending_uses_pending_as_effective(self, monkeypatch):
        sub = _make_sub(covered_users=10, pending_covered_users=6)
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
            tiers_by_slug={"access": _make_tier("access", 0)},
        )
        monkeypatch.setattr(
            sub_mod,
            "resolve_entitlements",
            lambda **kw: {},
        )
        monkeypatch.setattr(sub_mod, "omit_vat", lambda x: x)
        result = await _svc(repo).get_estate_subscription("estate-1")
        assert result["covered_users"] == 10
        assert result["pending_covered_users"] == 6
        assert result["effective_covered_users"] == 6

    @pytest.mark.asyncio
    async def test_no_subscription_returns_none_seat_fields(self, monkeypatch):
        repo = FakeRepo(
            tiers_by_slug={"access": _make_tier("access", 0)},
        )
        monkeypatch.setattr(
            sub_mod,
            "resolve_entitlements",
            lambda **kw: {},
        )
        monkeypatch.setattr(sub_mod, "omit_vat", lambda x: x)
        result = await _svc(repo).get_estate_subscription("estate-1")
        assert result["covered_users"] is None
        assert result["pending_covered_users"] is None
        assert result["effective_covered_users"] is None


# ── Combined scenarios ────────────────────────────────────────────────────


class TestCombinedSeatReductionScenarios:
    @pytest.mark.asyncio
    async def test_schedule_then_seat_add_then_renew_applies_pending(
        self, noop_grants, monkeypatch
    ):
        """Seat add after scheduling a reduction does not change pending_covered_users.
        At renewal, pending_covered_users wins regardless.
        """
        sub = _make_sub(covered_users=10, pending_covered_users=6)
        # Simulate that a seat_add already bumped covered_users to 13
        sub["covered_users"] = 13
        repo = FakeRepo(
            active_sub=sub,
            tiers_by_id={"tier-sentinel": SENTINEL},
        )
        monkeypatch.setattr(
            sub_mod,
            "compute_period_end",
            lambda **kw: kw["paid_at"]
            + __import__("datetime").timedelta(days=30),
        )
        await _svc(repo).renew("estate-1")
        seat_writes = [p for _, p in repo.update_calls if "covered_users" in p]
        assert seat_writes
        assert seat_writes[0]["covered_users"] == 6

    @pytest.mark.asyncio
    async def test_reschedule_overwrites_previous_pending(self):
        """Calling schedule_seat_reduction twice overwrites the first pending value."""
        sub = _make_sub(covered_users=20)
        repo = FakeRepo(active_sub=sub, active_user_count=5)
        await _svc(repo).schedule_seat_reduction("e1", 12)
        await _svc(repo).schedule_seat_reduction("e1", 8)
        assert repo._active_sub["pending_covered_users"] == 8

    @pytest.mark.asyncio
    async def test_cancel_after_reschedule_clears_latest_pending(self):
        sub = _make_sub(covered_users=20)
        repo = FakeRepo(active_sub=sub, active_user_count=5)
        await _svc(repo).schedule_seat_reduction("e1", 12)
        await _svc(repo).schedule_seat_reduction("e1", 8)
        result = await _svc(repo).cancel_seat_reduction("e1")
        assert result["pending_covered_users"] is None
        assert repo._active_sub["pending_covered_users"] is None

    @pytest.mark.asyncio
    async def test_schedule_reduction_then_cancel_then_reschedule(self):
        """Full cycle: schedule → cancel → reschedule all persist correctly."""
        sub = _make_sub(covered_users=20)
        repo = FakeRepo(active_sub=sub, active_user_count=5)
        await _svc(repo).schedule_seat_reduction("e1", 10)
        assert repo._active_sub["pending_covered_users"] == 10
        await _svc(repo).cancel_seat_reduction("e1")
        assert repo._active_sub["pending_covered_users"] is None
        await _svc(repo).schedule_seat_reduction("e1", 15)
        assert repo._active_sub["pending_covered_users"] == 15
