"""Internal endpoints protected by X-Internal-Key (cron, etc.)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.internal_auth import require_internal_key
from app.repositories.db_revenue import DbRevenueRepository
from app.services.expiry_service import ExpiryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/cron/daily", response_model=dict)
async def run_daily_cron(
    _key: Annotated[None, Depends(require_internal_key)],
    http_client: AsyncHttpHandler = Depends(get_http_handler),
) -> dict:
    """Expire stale subscriptions and AI grants. Internal use only."""
    repo = DbRevenueRepository(http_client)
    paystack = PaystackClient(settings.PAYSTACK_SECRET_KEY)
    result = await ExpiryService(repo, paystack).run()
    logger.info("Daily cron complete: %s", result)
    return result
