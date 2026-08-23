"""AI feature check, list, install, uninstall, and activate endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.entitlements import (
    AiActivateRequest,
    AiFeatureCheckResponse,
    EstateAiFeaturesResponse,
)
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)
router = APIRouter()


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
    service: EntitlementService = Depends(get_service),
):
    """
    Check whether an estate may use an AI feature.

    Query params: estate_id, feature_key.
    """
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
    service: EntitlementService = Depends(get_service),
):
    """List AI feature grants for an estate."""
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
    service: EntitlementService = Depends(get_service),
):
    """Set is_installed=true for a feature (create grant row if needed)."""
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
    service: EntitlementService = Depends(get_service),
):
    """Set is_installed=false; preserve billing/expiry fields."""
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


@router.post("/estate/{estate_id}/activate")
async def activate_ai_features(
    estate_id: str,
    request: AiActivateRequest,
    service: EntitlementService = Depends(get_service),
):
    """Provision standalone AI grants after charge success (no Paystack)."""
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
