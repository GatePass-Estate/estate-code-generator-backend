"""Estate subscription lookup endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.subscriptions import EstateSubscriptionResponse
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
