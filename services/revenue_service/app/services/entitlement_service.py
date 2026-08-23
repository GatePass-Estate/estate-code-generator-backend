"""Orchestrates entitlement and AI feature checks via db-service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.repositories.db_revenue import DbRevenueRepository
from app.services.entitlement_resolver import (
    ACTIVE_STATUSES,
    check_service_entitlement,
    resolve_entitlements,
)

logger = logging.getLogger(__name__)


class EntitlementService:
    """Business logic for estate entitlements and AI feature grants."""

    def __init__(self, repo: DbRevenueRepository):
        """
        Bind the db-service revenue repository.

        Args:
            repo: Repository used for catalog and subscription lookups.
        """
        self.repo = repo

    async def _load_context(self, estate_id: str) -> dict[str, Any]:
        """
        Load subscription, tier, and resolved entitlements for an estate.

        Resolves by estate subscription first. Loads the Access tier only
        when falling back (no subscription, inactive status, or missing tier).

        Args:
            estate_id: Estate UUID string.

        Returns:
            Context dict with subscription, tier, access_tier, entitlements.
            access_tier is None when the paid path was used.

        Raises:
            HTTPException: 500 if Access fallback is needed but not seeded.
        """
        subscription = await self.repo.get_active_subscription(estate_id)
        tier = None
        if subscription:
            tier = await self.repo.get_tier_by_id(str(subscription["tier_id"]))

        status = ((subscription or {}).get("status") or "").lower()
        needs_access_fallback = (
            not subscription or status not in ACTIVE_STATUSES or not tier
        )

        access_tier = None
        if needs_access_fallback:
            access_tier = await self.repo.get_tier_by_slug("access")
            if not access_tier:
                raise HTTPException(
                    status_code=500, detail="Access tier not seeded"
                )

        entitlements = resolve_entitlements(
            subscription=subscription,
            tier=tier,
            access_tier=access_tier,
        )
        return {
            "subscription": subscription,
            "tier": tier,
            "access_tier": access_tier,
            "entitlements": entitlements,
        }

    async def check(self, estate_id: str, service_key: str) -> dict[str, Any]:
        """
        Check whether an estate may use a catalog service_key.

        Args:
            estate_id: Estate UUID string.
            service_key: Service catalog key to evaluate.

        Returns:
            Entitlement check payload including allowed/limit metadata.

        Raises:
            HTTPException: 404 if service_key is unknown.
        """
        catalog = await self.repo.get_service_catalog_map()
        if service_key not in catalog:
            raise HTTPException(
                status_code=404, detail=f"Unknown service_key '{service_key}'"
            )
        ctx = await self._load_context(estate_id)
        limit_type = catalog[service_key].get("limit_type")
        result = check_service_entitlement(
            ctx["entitlements"], service_key, limit_type
        )
        sub = ctx["subscription"]
        tier = ctx["tier"]
        return {
            "estate_id": estate_id,
            "service_key": service_key,
            **result,
            "covered_users": (sub or {}).get("covered_users"),
            "subscription_status": (sub or {}).get("status"),
            "tier_slug": (tier or ctx.get("access_tier") or {}).get("slug"),
        }

    async def estate_entitlements(self, estate_id: str) -> dict[str, Any]:
        """
        Return the full effective entitlements map for an estate.

        Args:
            estate_id: Estate UUID string.

        Returns:
            Estate entitlements payload with subscription metadata.
        """
        ctx = await self._load_context(estate_id)
        sub = ctx["subscription"]
        tier = ctx["tier"]
        return {
            "estate_id": estate_id,
            "entitlements": ctx["entitlements"],
            "covered_users": (sub or {}).get("covered_users"),
            "subscription_status": (sub or {}).get("status"),
            "tier_slug": (tier or ctx.get("access_tier") or {}).get("slug"),
        }

    async def check_ai_feature(
        self, estate_id: str, feature_key: str
    ) -> dict[str, Any]:
        """
        Check whether an estate may use an AI feature grant.

        Free grants skip expiry; paid grants require active status and
        a non-expired expires_at when present.

        Args:
            estate_id: Estate UUID string.
            feature_key: AI feature catalog key.

        Returns:
            AI feature check payload (allowed, status, expiry, etc.).

        Raises:
            HTTPException: 404 if feature_key is unknown.
        """
        catalog = await self.repo.get_ai_feature_map()
        if feature_key not in catalog:
            raise HTTPException(
                status_code=404, detail=f"Unknown feature_key '{feature_key}'"
            )
        feature = catalog[feature_key]
        catalog_is_free = bool(feature.get("is_free"))

        grants = await self.repo.list_estate_ai_features(estate_id)
        feature_id = str(feature["id"])
        grant = next(
            (g for g in grants if str(g.get("ai_feature_id")) == feature_id),
            None,
        )
        if not grant:
            return {
                "estate_id": estate_id,
                "feature_key": feature_key,
                "allowed": False,
                "is_free": catalog_is_free,
                "status": None,
                "expires_at": None,
                "is_installed": False,
            }

        is_installed = bool(grant.get("is_installed"))
        is_free = bool(grant.get("is_free", catalog_is_free))
        status = (grant.get("status") or "").lower()
        expires_at = grant.get("expires_at")

        # Free grants skip expiry; paid grants require active + not expired.
        if not is_installed:
            allowed = False
        elif is_free:
            allowed = True
        else:
            not_expired = True
            if expires_at:
                try:
                    exp = datetime.fromisoformat(
                        str(expires_at).replace("Z", "+00:00")
                    )
                    not_expired = exp > datetime.now(tz=timezone.utc)
                except Exception:
                    not_expired = True
            allowed = status == "active" and not_expired

        return {
            "estate_id": estate_id,
            "feature_key": feature_key,
            "allowed": allowed,
            "is_free": is_free,
            "status": status,
            "expires_at": expires_at,
            "is_installed": is_installed,
        }

    async def list_ai_features(self, estate_id: str) -> dict[str, Any]:
        """
        List AI feature grants for an estate with resolved feature_keys.

        Args:
            estate_id: Estate UUID string.

        Returns:
            Payload with estate_id and enriched feature grant rows.
        """
        catalog = await self.repo.get_ai_feature_map()
        id_to_key = {str(v["id"]): k for k, v in catalog.items()}
        grants = await self.repo.list_estate_ai_features(estate_id)
        features = []
        for g in grants:
            fid = str(g.get("ai_feature_id"))
            key = id_to_key.get(fid)
            features.append(
                {
                    **g,
                    "feature_key": key,
                    "is_free": bool(
                        g.get("is_free")
                        if g.get("is_free") is not None
                        else catalog.get(key or "", {}).get("is_free", False)
                    ),
                }
            )
        return {"estate_id": estate_id, "features": features}
