"""AI feature check, list, install, uninstall, and activate endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from gatepass_auth.dependencies import get_current_user
from gatepass_rbac import (
    require_admin,
    require_estate_membership,
    require_roles,
)
from pydantic import BaseModel, Field

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.internal_auth import require_internal_key
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.entitlements import (
    AiActivateRequest,
    AiFeatureCheckResponse,
    EstateAiFeaturesResponse,
)
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)
router = APIRouter()

_PRIMARY_ADMIN_ROLES = ("primary_admin", "root")
_SECURITY_CHECK_ROLES = ("admin", "primary_admin", "security", "root")


class AiFeatureKeyRequest(BaseModel):
    """Body for install / uninstall."""

    feature_key: str = Field(..., min_length=1)


def get_service(
    http: AsyncHttpHandler = Depends(get_http_handler),
) -> EntitlementService:
    """Build an EntitlementService for request handling."""
    return EntitlementService(DbRevenueRepository(http))


@router.get("/check", response_model=AiFeatureCheckResponse)
async def check_ai_feature(
    estate_id: str,
    feature_key: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: EntitlementService = Depends(get_service),
    allow_security: bool = False,
):
    """
    Check whether an estate may use an AI feature.

    Query params: estate_id, feature_key, allow_security. When
    ``allow_security`` is true (gate validate → analyze), admin and
    security may check. Otherwise the lookup is admin-only.
    """
    if allow_security:
        require_roles(current_user["role"], _SECURITY_CHECK_ROLES)
    else:
        require_admin(current_user["role"])
    require_estate_membership(current_user, estate_id)
    try:
        return await service.check_ai_feature(estate_id, feature_key)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "AI feature check failed for estate_id=%s feature_key=%s",
            estate_id,
            feature_key,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get("/estate/{estate_id}", response_model=EstateAiFeaturesResponse)
async def list_ai_features(
    estate_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: EntitlementService = Depends(get_service),
):
    """List AI feature grants; orphans are marked catalog_deleted."""
    require_admin(current_user["role"])
    require_estate_membership(current_user, estate_id)
    try:
        return await service.list_ai_features(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "List AI features failed for estate_id=%s",
            estate_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post("/estate/{estate_id}/install")
async def install_ai_feature(
    estate_id: str,
    request: AiFeatureKeyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: EntitlementService = Depends(get_service),
):
    """Set is_installed=true; create grant only for free features."""
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        return await service.install_ai_feature(estate_id, request.feature_key)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "AI install failed estate_id=%s feature_key=%s",
            estate_id,
            request.feature_key,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post("/estate/{estate_id}/uninstall")
async def uninstall_ai_feature(
    estate_id: str,
    request: AiFeatureKeyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: EntitlementService = Depends(get_service),
):
    """Set is_installed=false; preserve billing/expiry fields."""
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        return await service.uninstall_ai_feature(
            estate_id, request.feature_key
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "AI uninstall failed estate_id=%s feature_key=%s",
            estate_id,
            request.feature_key,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/estate/{estate_id}/activate",
    dependencies=[Depends(require_internal_key)],
)
async def activate_ai_features(
    estate_id: str,
    request: AiActivateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: EntitlementService = Depends(get_service),
):
    """Provision standalone AI grants after charge success (no Paystack)."""
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        payload = request.model_dump()
        payload["estate_id"] = estate_id
        return await service.activate_ai_features(payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "AI activate failed estate_id=%s keys=%s",
            estate_id,
            request.ai_feature_keys,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
