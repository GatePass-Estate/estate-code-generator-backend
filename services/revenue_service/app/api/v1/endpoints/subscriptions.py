"""Estate subscription lookup and lifecycle endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.checkout import (
    ActivateSubscriptionRequest,
    RenewSubscriptionRequest,
)
from app.schemas.subscriptions import (
    ActivateSubscriptionResponse,
    EstateSubscriptionResponse,
    MutationSubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    http: AsyncHttpHandler = Depends(get_http_handler),
) -> SubscriptionService:
    """Build a SubscriptionService for request handling."""
    return SubscriptionService(DbRevenueRepository(http))


@router.get("/estate/{estate_id}", response_model=EstateSubscriptionResponse)
async def get_estate_subscription(
    estate_id: str,
    service: SubscriptionService = Depends(get_service),
):
    """Return the active subscription and effective entitlements for an estate."""
    try:
        return await service.get_estate_subscription(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Get estate subscription failed for estate_id=%s",
            estate_id,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post("/activate", response_model=ActivateSubscriptionResponse)
async def activate_subscription(
    request: ActivateSubscriptionRequest,
    service: SubscriptionService = Depends(get_service),
):
    """Activate or replace a subscription after charge success (no Paystack)."""
    try:
        return await service.activate(request.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Activate subscription failed estate_id=%s tier=%s",
            request.estate_id,
            request.tier_slug,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/estate/{estate_id}/renew",
    response_model=MutationSubscriptionResponse,
)
async def renew_subscription(
    estate_id: str,
    request: RenewSubscriptionRequest,
    service: SubscriptionService = Depends(get_service),
):
    """Renew subscription using dating rules; extend linked paid AI grants."""
    try:
        paid_at = None
        if request.paid_at:
            paid_at = datetime.fromisoformat(
                request.paid_at.replace("Z", "+00:00")
            )
            if paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=timezone.utc)
        return await service.renew(
            estate_id,
            period_months=request.period_months,
            paid_at=paid_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Renew failed estate_id=%s", estate_id)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/estate/{estate_id}/cancel",
    response_model=MutationSubscriptionResponse,
)
async def cancel_subscription(
    estate_id: str,
    service: SubscriptionService = Depends(get_service),
):
    """Cancel auto-renew; keep period_end / AI expires_at unchanged."""
    try:
        return await service.cancel(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cancel failed estate_id=%s", estate_id)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
