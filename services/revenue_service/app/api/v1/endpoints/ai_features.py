"""AI feature check and estate AI feature list endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.entitlements import (
    AiFeatureCheckResponse,
    EstateAiFeaturesResponse,
)
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)
router = APIRouter()


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
