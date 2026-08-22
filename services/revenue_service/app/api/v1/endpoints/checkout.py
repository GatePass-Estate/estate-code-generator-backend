"""Checkout quote and Paystack initialize stub endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.checkout import QuoteRequest, QuoteResponse
from app.services.checkout_service import CheckoutService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    http: AsyncHttpHandler = Depends(get_http_handler),
) -> CheckoutService:
    """Build a CheckoutService for request handling."""
    return CheckoutService(DbRevenueRepository(http))


@router.post("/quote", response_model=QuoteResponse)
async def quote(
    request: QuoteRequest,
    service: CheckoutService = Depends(get_service),
):
    """Compute a pricing quote for a subscription / custom entitlements purchase."""
    try:
        return await service.quote(request.model_dump())
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        entitlement_keys = (
            sorted(request.entitlements.keys())
            if request.entitlements is not None
            else None
        )
        logger.exception(
            "Quote failed for estate_id=%s tier_slug=%s "
            "covered_users=%s period_months=%s "
            "ai_feature_keys=%s entitlement_keys=%s",
            request.estate_id,
            request.tier_slug,
            request.covered_users,
            request.period_months,
            request.ai_feature_keys,
            entitlement_keys,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post("/initialize")
async def initialize_checkout():
    """Stub: initialize Paystack checkout (Phase 2)."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "status": "stubbed",
            "message": "Paystack checkout not implemented yet",
        },
    )
