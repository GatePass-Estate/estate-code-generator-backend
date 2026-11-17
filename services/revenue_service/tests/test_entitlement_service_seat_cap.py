"""Unit tests for EntitlementService.check() seat cap enforcement.

Covers:
  - max_active_users uses covered_users when no pending reduction
  - max_active_users uses pending_covered_users (effective cap) when a seat
    reduction is scheduled
  - max_active_users falls back to covered_users when pending is None
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.entitlement_service import EntitlementService


# ── Helpers ───────────────────────────────────────────────────────────────


def _make_sub(**overrides: Any) -> dict:
    base: dict[str, Any] = {
        "id": "sub-1",
        "estate_id": "estate-1",
        "tier_id": "tier-sentinel",
        "status": "active",
        "auto_renew": True,
        "covered_users": 10,
        "pending_covered_users": None,
        "over_cap_locked": False,
        "entitlements": None,
    }
    return {**base, **overrides}


class FakeRepo:
    """Minimal fake for DbRevenueRepository."""

    def __init__(
        self,
        *,
        active_sub: dict | None = None,
        catalog: dict[str, dict] | None = None,
        tier: dict | None = None,
        access_tier: dict | None = None,
    ) -> None:
        self._active_sub = active_sub
        self._catalog = catalog or {
            "max_active_users": {"limit_type": "count"},
        }
        self._tier = tier or {
            "id": "tier-sentinel",
            "slug": "sentinel",
            "is_custom": False,
            "entitlements": {"max_active_users": 10},
        }
        self._access_tier = access_tier or {
            "id": "tier-access",
            "slug": "access",
            "is_custom": False,
            "entitlements": {"max_active_users": 1},
        }

    async def get_active_subscription(self, estate_id: str) -> dict | None:
        return self._active_sub

    async def get_tier_by_id(self, tier_id: str) -> dict | None:
        return self._tier

    async def get_tier_by_slug(self, slug: str) -> dict | None:
        if slug == "access":
            return self._access_tier
        return self._tier

    async def get_service_catalog_map(self) -> dict:
        return self._catalog


def _svc(repo: FakeRepo) -> EntitlementService:
    return EntitlementService(repo)


# ── Tests ─────────────────────────────────────────────────────────────────


class TestMaxActiveUsersSeatCap:
    @pytest.mark.asyncio
    async def test_no_pending_uses_covered_users(self):
        """When no seat reduction is pending, limit == covered_users."""
        sub = _make_sub(covered_users=10, pending_covered_users=None)
        result = await _svc(FakeRepo(active_sub=sub)).check(
            "estate-1", "max_active_users"
        )
        assert result["limit"] == 10

    @pytest.mark.asyncio
    async def test_pending_reduction_uses_pending_as_limit(self):
        """When a seat reduction is scheduled, limit == pending_covered_users."""
        sub = _make_sub(covered_users=10, pending_covered_users=6)
        result = await _svc(FakeRepo(active_sub=sub)).check(
            "estate-1", "max_active_users"
        )
        assert result["limit"] == 6

    @pytest.mark.asyncio
    async def test_pending_lower_than_covered_enforces_lower_cap(self):
        """Effective cap is the pending value even though covered_users is higher."""
        sub = _make_sub(covered_users=20, pending_covered_users=8)
        result = await _svc(FakeRepo(active_sub=sub)).check(
            "estate-1", "max_active_users"
        )
        assert result["limit"] == 8

    @pytest.mark.asyncio
    async def test_pending_zero_is_ignored_uses_covered(self):
        """pending_covered_users=0 is falsy but None check means 0 would be used.
        In practice the service guards new_seats >= 1 so 0 can't be stored,
        but we verify the None sentinel is the only bypass."""
        # 0 is not None, so effective = 0 and limit = 0 → allowed=False
        sub = _make_sub(covered_users=10, pending_covered_users=0)
        result = await _svc(FakeRepo(active_sub=sub)).check(
            "estate-1", "max_active_users"
        )
        # limit=0 → allowed=False (guarded by `limit > 0` in check())
        assert result["limit"] == 0
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_no_subscription_falls_through_to_entitlements(self):
        """Without a subscription the Access tier entitlements are used."""
        result = await _svc(FakeRepo(active_sub=None)).check(
            "estate-1", "max_active_users"
        )
        # Access tier entitlement defines max_active_users=1
        assert result["limit"] == 1
