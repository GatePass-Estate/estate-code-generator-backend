"""Checkout quote and Paystack initialize stub endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.checkout import (
    AiCheckoutRequest,
    QuoteRequest,
    QuoteResponse,
    SeatApplyRequest,
    SeatProrateRequest,
    SeatProrateResponse,
)
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


@router.post("/seats/prorate", response_model=SeatProrateResponse)
async def prorate_seats(
    request: SeatProrateRequest,
    service: CheckoutService = Depends(get_service),
):
    """Quote mid-period seat add (remaining days × daily seat rate; AI excluded)."""
    try:
        return await service.prorate_seats(request.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Seat prorate failed estate_id=%s seats_added=%s",
            request.estate_id,
            request.seats_added,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post("/seats/apply")
async def apply_seats(
    request: SeatApplyRequest,
    service: CheckoutService = Depends(get_service),
):
    """Apply seat add after charge success (Paystack not required in Phase 1)."""
    try:
        return await service.apply_seat_add(request.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Seat apply failed estate_id=%s seats_added=%s",
            request.estate_id,
            request.seats_added,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post("/ai/quote")
async def quote_ai(
    request: AiCheckoutRequest,
    service: CheckoutService = Depends(get_service),
):
    """Quote standalone AI feature purchase (flat monthly × months)."""
    try:
        return await service.quote_ai_features(request.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "AI quote failed estate_id=%s keys=%s",
            request.estate_id,
            request.ai_feature_keys,
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
