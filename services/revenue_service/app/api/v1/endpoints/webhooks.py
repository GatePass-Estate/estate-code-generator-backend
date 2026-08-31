"""Paystack webhook endpoint."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.integrations.paystack_client import PaystackClient
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.db_revenue import DbRevenueRepository
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_webhook_service(
    http: AsyncHttpHandler = Depends(get_http_handler),
) -> WebhookService:
    """Build a WebhookService for request handling."""
    return WebhookService(DbRevenueRepository(http))


@router.post("/paystack")
async def paystack_webhook(
    http_request: Request,
    service: WebhookService = Depends(get_webhook_service),
):
    """
    Receive and process Paystack webhook events.

    Verifies the HMAC-SHA512 signature, deduplicates by event id, and
    dispatches to the matching handler. Always returns 200 to prevent
    Paystack from retrying indefinitely on processing errors.
    """
    body = await http_request.body()

    # 1. Verify HMAC signature
    signature = http_request.headers.get("x-paystack-signature", "")
    client = PaystackClient(secret_key=settings.PAYSTACK_SECRET_KEY)
    if not client.verify_webhook_signature(body, signature):
        raise HTTPException(
            status_code=401, detail="Invalid webhook signature"
        )

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed JSON body")

    event_type: str = payload.get("event", "")
    data: dict = payload.get("data") or {}

    # Build a stable dedup key. Most events carry a numeric ``data.id``;
    # events that don't (e.g. subscription.disable) get a composite key
    # from event_type + the most-specific identifier available.
    raw_id = data.get("id")
    if raw_id:
        event_id = str(raw_id)
    else:
        ref = data.get("reference") or data.get("subscription_code") or ""
        event_id = f"{event_type}:{ref}" if ref else event_type

    # 2. Dedup: check if we have already processed this event
    existing = await service.repo.get_payment_event_by_event_id(event_id)
    if existing:
        logger.info(
            "Duplicate webhook event_type=%s event_id=%s — skipping",
            event_type,
            event_id,
        )
        return {"status": "duplicate", "event_id": event_id}

    # 3. Record the event before processing (idempotency ledger).
    # NOTE: If the event is recorded but processing below fails, there is
    # currently no automatic recovery — the event will be skipped on any
    # Paystack retry (treated as duplicate). Failed events should be
    # monitored via logs and replayed manually if needed.
    # TODO: Consider a "processed=False" flag on payment_event that gets
    # flipped to True only after successful processing, enabling a
    # background job to replay failed events.
    await service.repo.create_payment_event(
        {
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
            "processed_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    )

    # 4. Dispatch — always return 200, log processing errors
    try:
        await service.process_event(event_type, data)
    except Exception:
        logger.exception(
            "Webhook processing error event_type=%s event_id=%s",
            event_type,
            event_id,
        )

    return {"status": "ok"}
