"""Entitlement check and estate entitlements endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from gatepass_auth.dependencies import get_current_user
from gatepass_rbac import require_estate_membership

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.entitlements import (
    EntitlementCheckResponse,
    EstateEntitlementsResponse,
)
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    http: AsyncHttpHandler = Depends(get_http_handler),
) -> EntitlementService:
    """Build an EntitlementService for request handling."""
    return EntitlementService(DbRevenueRepository(http))


@router.get("/check", response_model=EntitlementCheckResponse)
async def check_entitlement(
    estate_id: str,
    service_key: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: EntitlementService = Depends(get_service),
):
    """
    Check whether an estate is entitled to a catalog service_key.

    Query params: estate_id, service_key.
    """
    require_estate_membership(current_user, estate_id)
    try:
        return await service.check(estate_id, service_key)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Entitlement check failed for estate_id=%s service_key=%s",
            estate_id,
            service_key,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get("/estate/{estate_id}", response_model=EstateEntitlementsResponse)
async def estate_entitlements(
    estate_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: EntitlementService = Depends(get_service),
):
    """Return the full effective entitlements map for an estate."""
    require_estate_membership(current_user, estate_id)
    try:
        return await service.estate_entitlements(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Estate entitlements failed for estate_id=%s",
            estate_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
