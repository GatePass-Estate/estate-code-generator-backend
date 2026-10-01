"""Estate subscription lookup and lifecycle endpoints."""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from gatepass_auth.dependencies import get_current_user
from gatepass_rbac import (
    require_admin,
    require_estate_membership,
    require_roles,
)

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
    BillingCycleResponse,
    EstateSubscriptionResponse,
    MutationSubscriptionResponse,
    ScheduleSeatReductionRequest,
    ScheduleSeatReductionResponse,
    ScheduleTierChangeRequest,
    ScheduleTierChangeResponse,
    SeatReductionEligibilityResponse,
)
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)
router = APIRouter()

_PRIMARY_ADMIN_ROLES = ("primary_admin", "root")


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
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Return the estate's active subscription and entitlements."""
    require_admin(current_user["role"])
    require_estate_membership(current_user, estate_id)
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


@router.get(
    "/estate/{estate_id}/billing-cycle",
    response_model=BillingCycleResponse,
)
async def get_billing_cycle(
    estate_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Return next billing cycle projection for an estate.

    Complements GET /estate/{estate_id} (full subscription +
    entitlements) by computing what the next auto-renewal will charge
    and under which tier, including any scheduled tier change.
    """
    require_admin(current_user["role"])
    require_estate_membership(current_user, estate_id)
    try:
        return await service.get_billing_cycle(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "get_billing_cycle failed for estate_id=%s", estate_id
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
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """
    Activate or replace a subscription without going through Paystack.

    Internal use only (``X-Internal-Key`` required). Normal activations
    are driven by the ``charge.success`` webhook.
    """
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, request.estate_id)
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
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Cancel auto-renew and disable the Paystack subscription."""
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        return await service.cancel(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Cancel failed estate_id=%s", estate_id)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/estate/{estate_id}/schedule-tier-change",
    response_model=ScheduleTierChangeResponse,
)
async def schedule_tier_change(
    estate_id: str,
    request: ScheduleTierChangeRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Schedule a tier upgrade or downgrade for the next billing cycle.

    No payment is collected now. The pending tier and AI grants are
    applied automatically on the next auto-renewal.
    """
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        return await service.schedule_tier_change(estate_id, request.tier_slug)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "schedule_tier_change failed estate_id=%s tier_slug=%s",
            estate_id,
            request.tier_slug,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/estate/{estate_id}/schedule-tier-change",
    response_model=ScheduleTierChangeResponse,
)
async def cancel_tier_change(
    estate_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Cancel a previously scheduled tier change.

    Clears pending_tier_slug and reverts the Paystack plan amount so
    the next auto-renewal charges the current tier price.
    """
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        return await service.cancel_tier_change(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("cancel_tier_change failed estate_id=%s", estate_id)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/estate/{estate_id}/seat-reduction-eligibility",
    response_model=SeatReductionEligibilityResponse,
)
async def get_seat_reduction_eligibility(
    estate_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Return whether a seat reduction is currently possible.

    The FE uses this to decide whether to show the seat-reduction UI and
    what the minimum allowable seat count is (== active user count).
    """
    require_admin(current_user["role"])
    require_estate_membership(current_user, estate_id)
    try:
        return await service.get_seat_reduction_eligibility(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "get_seat_reduction_eligibility failed estate_id=%s", estate_id
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/estate/{estate_id}/schedule-seat-reduction",
    response_model=ScheduleSeatReductionResponse,
)
async def schedule_seat_reduction(
    estate_id: str,
    request: ScheduleSeatReductionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Schedule a seat reduction for the next billing cycle.

    No refund is issued. The reduced seat count takes effect automatically
    on the next auto-renewal. Registration is capped at the pending count
    immediately (via effective_covered_users on the subscription response).
    """
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        return await service.schedule_seat_reduction(estate_id, request.seats)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "schedule_seat_reduction failed estate_id=%s seats=%s",
            estate_id,
            request.seats,
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/estate/{estate_id}/schedule-seat-reduction",
    response_model=ScheduleSeatReductionResponse,
)
async def cancel_seat_reduction(
    estate_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    service: SubscriptionService = Depends(get_service),
):
    """Cancel a previously scheduled seat reduction.

    Clears pending_covered_users and reverts the Paystack plan amount so
    the next auto-renewal charges for the current (unreduced) seat count.
    """
    require_roles(current_user["role"], _PRIMARY_ADMIN_ROLES)
    require_estate_membership(current_user, estate_id)
    try:
        return await service.cancel_seat_reduction(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "cancel_seat_reduction failed estate_id=%s", estate_id
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/estate/{estate_id}/provision-access",
    dependencies=[Depends(require_internal_key)],
)
async def provision_access_subscription(
    estate_id: str,
    service: SubscriptionService = Depends(get_service),
):
    """Provision an access-tier subscription for a newly registered estate.

    Idempotent — safe to call on existing estates (returns current sub).
    Called by UPS after estate registration; also used for backfilling.
    """
    try:
        return await service.provision_access_subscription(estate_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "provision_access_subscription failed estate_id=%s", estate_id
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
