"""Checkout quote, Paystack initialization, and status endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from gatepass_auth.dependencies import get_current_user

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.schemas.checkout import (
    AiCheckoutRequest,
    CheckoutInitializeRequest,
    CheckoutInitializeResponse,
    CheckoutStatusResponse,
    QuoteRequest,
    QuoteResponse,
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
    """Compute a pricing quote for a subscription / custom purchase."""
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
    """Quote mid-period seat add (remaining days × daily rate; AI excluded)."""
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


@router.post(
    "/initialize",
    response_model=CheckoutInitializeResponse,
    status_code=201,
)
async def initialize_checkout(
    request: CheckoutInitializeRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    current_user: Annotated[dict, Depends(get_current_user)],
    service: CheckoutService = Depends(get_service),
):
    """
    Initialize a Paystack checkout transaction.

    Returns an authorization_url to redirect the user to Paystack, plus
    a checkout_token for polling /status/{reference}.

    Requires an ``Idempotency-Key`` header. Re-using a key that maps to a
    failed or expired session returns 409.
    """
    try:
        return await service.initialize(
            request.model_dump(),
            idempotency_key=idempotency_key,
            current_user_id=current_user["id"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Checkout initialize failed estate_id=%s kind=%s",
            request.estate_id,
            request.checkout_kind,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/status/{paystack_reference}", response_model=CheckoutStatusResponse
)
async def checkout_status(
    paystack_reference: str,
    # NOTE: this endpoint must be rate-limited at gateway level.
    checkout_token: Annotated[
        str | None, Header(alias="X-Checkout-Token")
    ] = None,
    service: CheckoutService = Depends(get_service),
):
    """
    Return the current status of a checkout session.

    Accepts an optional ``X-Checkout-Token`` header (from the initialize
    response). When present, it is verified against the session. When
    absent, the lookup proceeds by reference only.
    """
    try:
        return await service.get_status(paystack_reference, checkout_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Checkout status lookup failed reference=%s", paystack_reference
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
