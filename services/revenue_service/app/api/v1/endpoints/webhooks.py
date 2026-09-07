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
    dispatches to the matching handler. Successful and duplicate events
    return 200. A processing failure returns 500 so Paystack retries
    (the event is not recorded until the handler succeeds).
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

    # Build a stable dedup key: always scope by event_type so that two
    # different event types that share a numeric data.id do not collide.
    raw_id = data.get("id")
    if raw_id:
        event_id = f"{event_type}:{raw_id}"
    else:
        ref = data.get("reference") or data.get("subscription_code") or ""
        event_id = f"{event_type}:{ref}" if ref else event_type

    # 2. Dedup: skip events we have already successfully processed.
    existing = await service.repo.get_payment_event_by_event_id(event_id)
    if existing:
        logger.info(
            "Duplicate webhook event_type=%s event_id=%s — skipping",
            event_type,
            event_id,
        )
        return {"status": "duplicate", "event_id": event_id}

    # 3. Dispatch first; record only on success so that a processing
    # failure leaves the event unrecorded and Paystack can retry.
    try:
        await service.process_event(event_type, data)
    except Exception:
        logger.exception(
            "Webhook processing error event_type=%s event_id=%s — "
            "event NOT recorded; returning 500 so Paystack retries",
            event_type,
            event_id,
        )
        raise HTTPException(
            status_code=500, detail="Webhook processing failed"
        )

    await service.repo.create_payment_event(
        {
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
            "processed_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    )

    return {"status": "ok"}
