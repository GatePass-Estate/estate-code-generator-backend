"""Orchestrates entitlement and AI feature checks via db-service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.core.config import settings
from app.libs.period_dating import (
    compute_period_end,
    paid_feature_access_valid,
)
from app.repositories.db_revenue import DbRevenueRepository
from app.services.ai_grant_sync import provision_standalone_ai_grant
from app.services.entitlement_resolver import (
    check_service_entitlement,
    resolve_entitlements,
    uses_access_fallback,
)

logger = logging.getLogger(__name__)

MAX_ACTIVE_USERS_KEY = "max_active_users"


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

        needs_access_fallback = uses_access_fallback(subscription, tier)

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
            "uses_access_fallback": needs_access_fallback,
        }

    async def check(self, estate_id: str, service_key: str) -> dict[str, Any]:
        """
        Check whether an estate may use a catalog service_key.

        ``max_active_users`` uses ``covered_users`` on the subscription as the
        seat cap when present.

        When the estate has fallen back to Access and the subscription has
        ``over_cap_locked`` (set by the expiry sweep), returns a locked denial
        so UPS can block non-primary-admin logins.

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
        sub = ctx["subscription"]
        tier = ctx["tier"]

        if (
            ctx.get("uses_access_fallback")
            and sub is not None
            and bool(sub.get("over_cap_locked"))
        ):
            return {
                "estate_id": estate_id,
                "service_key": service_key,
                "allowed": False,
                "locked": True,
                "reason": "over_cap",
                "limit": None,
                "limit_type": limit_type,
                "covered_users": sub.get("covered_users"),
                "subscription_status": sub.get("status"),
                "tier_slug": (ctx.get("access_tier") or {}).get("slug"),
            }

        if service_key == MAX_ACTIVE_USERS_KEY and sub is not None:
            covered = sub.get("covered_users")
            if covered is not None:
                limit = int(covered)
                result = {
                    "allowed": limit > 0,
                    "limit": limit,
                    "limit_type": limit_type or "count",
                }
            else:
                result = check_service_entitlement(
                    ctx["entitlements"], service_key, limit_type
                )
        else:
            result = check_service_entitlement(
                ctx["entitlements"], service_key, limit_type
            )

        return {
            "estate_id": estate_id,
            "service_key": service_key,
            **result,
            "locked": False,
            "reason": None,
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

        Free grants skip expiry. Paid grants stay allowed while installed
        until access ends (or status ``expired``). For ``active`` grants,
        access continues through ``expires_at + RENEWAL_GRACE_PERIOD_DAYS``
        while auto-renew retries run. ``cancelled`` and ``past_due`` keep
        access only until ``expires_at`` (no grace). Uninstalled grants are
        always denied.

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

        if not is_installed:
            allowed = False
        elif is_free:
            allowed = True
        elif status == "expired":
            allowed = False
        else:
            # active: expires_at + grace; cancelled/past_due: expires_at only.
            allowed = paid_feature_access_valid(
                status=status,
                expires_at=expires_at,
                grace_days=settings.RENEWAL_GRACE_PERIOD_DAYS,
            )

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

    async def install_ai_feature(
        self, estate_id: str, feature_key: str
    ) -> dict[str, Any]:
        """
        Set ``is_installed=true`` for an AI grant (create row if missing).

        Does not change billing ``status``, ``expires_at``, or payment linkage.
        """
        catalog = await self.repo.get_ai_feature_map()
        feature = catalog.get(feature_key)
        if not feature:
            raise HTTPException(
                status_code=404, detail=f"Unknown feature_key '{feature_key}'"
            )
        feature_id = str(feature["id"])
        is_free = bool(feature.get("is_free"))
        grants = await self.repo.list_estate_ai_features(estate_id)
        grant = next(
            (g for g in grants if str(g.get("ai_feature_id")) == feature_id),
            None,
        )
        if grant:
            updated = await self.repo.update_estate_ai_feature(
                str(grant["id"]), {"is_installed": True}
            )
        else:
            updated = await self.repo.create_estate_ai_feature(
                {
                    "estate_id": estate_id,
                    "ai_feature_id": feature_id,
                    "source": "free_install" if is_free else "admin_grant",
                    "is_installed": True,
                    "status": "active",
                    "is_free": is_free,
                    "auto_renew": False,
                    "starts_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            )
        return {
            "estate_id": estate_id,
            "feature_key": feature_key,
            "is_installed": True,
            "grant": updated,
        }

    async def uninstall_ai_feature(
        self, estate_id: str, feature_key: str
    ) -> dict[str, Any]:
        """
        Set ``is_installed=false`` only; preserve expiry and billing fields.
        """
        catalog = await self.repo.get_ai_feature_map()
        feature = catalog.get(feature_key)
        if not feature:
            raise HTTPException(
                status_code=404, detail=f"Unknown feature_key '{feature_key}'"
            )
        feature_id = str(feature["id"])
        grants = await self.repo.list_estate_ai_features(estate_id)
        grant = next(
            (g for g in grants if str(g.get("ai_feature_id")) == feature_id),
            None,
        )
        if not grant:
            raise HTTPException(
                status_code=404,
                detail=f"No AI grant for feature_key '{feature_key}'",
            )
        updated = await self.repo.update_estate_ai_feature(
            str(grant["id"]), {"is_installed": False}
        )
        return {
            "estate_id": estate_id,
            "feature_key": feature_key,
            "is_installed": False,
            "grant": updated,
        }

    async def activate_ai_features(
        self, request: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Provision standalone AI grants after charge success (no Paystack).

        Extends ``expires_at`` by period_months using dating rules when a
        prior paid grant exists.
        """
        estate_id = request["estate_id"]
        feature_keys = list(request.get("ai_feature_keys") or [])
        if not feature_keys:
            raise HTTPException(
                status_code=400, detail="ai_feature_keys required"
            )
        period_months = int(request.get("period_months") or 1)
        paid_at_raw = request.get("paid_at")
        if paid_at_raw:
            paid_at = datetime.fromisoformat(
                str(paid_at_raw).replace("Z", "+00:00")
            )
        else:
            paid_at = datetime.now(tz=timezone.utc)
        if paid_at.tzinfo is None:
            paid_at = paid_at.replace(tzinfo=timezone.utc)

        duration = timedelta(days=30 * period_months)
        grants_out: list[dict] = []
        existing = await self.repo.list_estate_ai_features(estate_id)
        catalog = await self.repo.get_ai_feature_map()

        for feature_key in feature_keys:
            feature = catalog.get(feature_key)
            if not feature:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown feature_key '{feature_key}'",
                )
            feature_id = str(feature["id"])
            prior = next(
                (
                    g
                    for g in existing
                    if str(g.get("ai_feature_id")) == feature_id
                ),
                None,
            )
            old_end = None
            if prior and prior.get("expires_at"):
                old_end = datetime.fromisoformat(
                    str(prior["expires_at"]).replace("Z", "+00:00")
                )
            period_end = compute_period_end(
                paid_at=paid_at,
                duration=duration,
                old_period_end=old_end,
                grace_days=settings.RENEWAL_GRACE_PERIOD_DAYS,
            )
            grant = await provision_standalone_ai_grant(
                self.repo,
                estate_id=estate_id,
                feature=feature,
                period_end=period_end,
                existing_grant=prior,
            )
            grants_out.append(
                {
                    "feature_key": feature_key,
                    "grant": grant,
                    "expires_at": period_end.isoformat(),
                }
            )

        return {
            "estate_id": estate_id,
            "features": grants_out,
            "status": "activated",
            "paystack": "stubbed",
        }
