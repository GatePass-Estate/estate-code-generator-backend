"""Estate subscription lookup and lifecycle endpoints."""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from gatepass_auth.dependencies import get_current_user

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.internal_auth import require_internal_key
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
    return SubscriptionService(
        DbRevenueRepository(http),
        paystack_client=PaystackClient(
            secret_key=settings.PAYSTACK_SECRET_KEY
        ),
    )


@router.get("/estate/{estate_id}", response_model=EstateSubscriptionResponse)
async def get_estate_subscription(
    estate_id: str,
    _: Annotated[dict, Depends(get_current_user)],
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


@router.post(
    "/activate",
    response_model=ActivateSubscriptionResponse,
    dependencies=[Depends(require_internal_key)],
)
async def activate_subscription(
    request: ActivateSubscriptionRequest,
    service: SubscriptionService = Depends(get_service),
):
    """
    Activate or replace a subscription without going through Paystack.

    Internal use only (``X-Internal-Key`` required). Normal activations
    are driven by the ``charge.success`` webhook.
    """
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
    dependencies=[Depends(require_internal_key)],
)
async def renew_subscription(
    estate_id: str,
    request: RenewSubscriptionRequest,
    service: SubscriptionService = Depends(get_service),
):
    """
    Renew a subscription without going through Paystack.

    Internal use only (``X-Internal-Key`` required). Normal renewals are
    driven by the ``charge.success`` webhook on a Paystack auto-renewal.
    """
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
    _: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Cancel auto-renew and disable the Paystack subscription."""
    try:
        return await service.cancel(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cancel failed estate_id=%s", estate_id)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
