"""Paystack API client."""

from __future__ import annotations

import hashlib
import hmac
import logging

import httpx
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


class PaystackClient:
    """Thin async wrapper around Paystack's transaction and webhook APIs."""

    def __init__(self, secret_key: str | None = None) -> None:
        """
        Store the Paystack secret key.

        Args:
            secret_key: Paystack secret key (sk_live_... or sk_test_...).
        """
        self.secret_key = secret_key or ""

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}"}

    async def initialize_transaction(
        self,
        *,
        email: str,
        amount_kobo: int,
        reference: str,
        callback_url: str,
        metadata: dict,
        currency: str = "NGN",
    ) -> dict:
        """
        Initialize a Paystack transaction.

        Args:
            email: Customer email for the receipt and Paystack customer record.
            amount_kobo: Charge amount in the smallest currency unit (kobo for
                NGN, pesewas for GHS, etc.).
            reference: Unique transaction reference (e.g. ``GP-<session_id>``).
            callback_url: Frontend URL Paystack redirects to after payment.
            metadata: Arbitrary key/value pairs attached to the transaction.
            currency: ISO currency code (default ``NGN``).

        Returns:
            Paystack response data dict with ``authorization_url``,
            ``access_code``, and ``reference``.

        Raises:
            HTTPException: 502 if Paystack returns an error or is unreachable.
        """
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "callback_url": callback_url,
            "metadata": metadata,
            "currency": currency,
        }
        url = f"{settings.PAYSTACK_BASE_URL}/transaction/initialize"
        timeout = settings.PAYSTACK_TIMEOUT_SECONDS
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self._auth_headers()
                )
                response.raise_for_status()
                body = response.json()
                if not body.get("status"):
                    logger.error(
                        "Paystack initialize_transaction status=false "
                        "reference=%s message=%s",
                        reference,
                        body.get("message"),
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error: "
                            f"{body.get('message', 'unknown')}"
                        ),
                    )
                return body["data"]
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack initialize_transaction HTTP error reference=%s "
                    "status=%s body=%s",
                    reference,
                    exc.response.status_code,
                    exc.response.text,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack initialization failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception(
                    "Paystack initialize_transaction network error "
                    "reference=%s",
                    reference,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack unreachable",
                ) from exc

    async def verify_transaction(self, reference: str) -> dict:
        """
        Verify a Paystack transaction by reference.

        Args:
            reference: The transaction reference to look up.

        Returns:
            Full Paystack transaction data dict.

        Raises:
            HTTPException: 502 on Paystack error or network failure;
                404 if the transaction is not found.
        """
        url = f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}"
        timeout = settings.PAYSTACK_TIMEOUT_SECONDS
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.get(url, headers=self._auth_headers())
                if response.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Transaction not found: {reference}",
                    )
                response.raise_for_status()
                body = response.json()
                if not body.get("status"):
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error: "
                            f"{body.get('message', 'unknown')}"
                        ),
                    )
                return body["data"]
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack verify_transaction HTTP error reference=%s "
                    "status=%s body=%s",
                    reference,
                    exc.response.status_code,
                    exc.response.text,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack verification failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception(
                    "Paystack verify_transaction network error reference=%s",
                    reference,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack unreachable",
                ) from exc

    async def create_plan(
        self,
        *,
        name: str,
        amount_kobo: int,
        interval: str,
        currency: str = "NGN",
    ) -> dict:
        """
        Create a Paystack billing plan.

        Args:
            name: Human-readable plan name.
            amount_kobo: Charge amount in the smallest currency unit.
            interval: Billing cadence — one of ``monthly``, ``quarterly``,
                ``biannually``, or ``annually``.
            currency: ISO currency code (default ``NGN``).

        Returns:
            Paystack plan data dict containing ``plan_code``.

        Raises:
            HTTPException: 502 on Paystack error or network failure.
        """
        payload = {
            "name": name,
            "amount": amount_kobo,
            "interval": interval,
            "currency": currency,
        }
        url = f"{settings.PAYSTACK_BASE_URL}/plan"
        async with httpx.AsyncClient(
            timeout=settings.PAYSTACK_TIMEOUT_SECONDS
        ) as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self._auth_headers()
                )
                response.raise_for_status()
                body = response.json()
                if not body.get("status"):
                    logger.error(
                        "Paystack create_plan status=false name=%s message=%s",
                        name,
                        body.get("message"),
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error: "
                            f"{body.get('message', 'unknown')}"
                        ),
                    )
                return body["data"]
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack create_plan HTTP error status=%s body=%s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack plan creation failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception("Paystack create_plan network error")
                raise HTTPException(
                    status_code=502, detail="Paystack unreachable"
                ) from exc

    async def create_subscription(
        self,
        *,
        customer_email: str,
        plan_code: str,
        authorization_code: str,
        start_date: str | None = None,
    ) -> dict:
        """
        Create a Paystack recurring subscription on an existing plan.

        Args:
            customer_email: Customer email (used to identify the Paystack
                customer).
            plan_code: Plan code returned by :meth:`create_plan`.
            authorization_code: Reusable card authorization from the first
                ``charge.success`` event.
            start_date: ISO 8601 datetime for the first auto-charge (defaults
                to the plan's next billing date if omitted).

        Returns:
            Paystack subscription data dict containing ``subscription_code``.

        Raises:
            HTTPException: 502 on Paystack error or network failure.
        """
        payload: dict = {
            "customer": customer_email,
            "plan": plan_code,
            "authorization": authorization_code,
        }
        if start_date:
            payload["start_date"] = start_date
        url = f"{settings.PAYSTACK_BASE_URL}/subscription"
        async with httpx.AsyncClient(
            timeout=settings.PAYSTACK_TIMEOUT_SECONDS
        ) as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self._auth_headers()
                )
                response.raise_for_status()
                body = response.json()
                if not body.get("status"):
                    logger.error(
                        "Paystack create_subscription status=false "
                        "customer=%s plan=%s message=%s",
                        customer_email,
                        plan_code,
                        body.get("message"),
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error: "
                            f"{body.get('message', 'unknown')}"
                        ),
                    )
                return body["data"]
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack create_subscription HTTP error "
                    "status=%s body=%s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack subscription creation failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception("Paystack create_subscription network error")
                raise HTTPException(
                    status_code=502, detail="Paystack unreachable"
                ) from exc

    async def get_subscription(self, subscription_code: str) -> dict:
        """
        Fetch a Paystack subscription record by code.

        Args:
            subscription_code: The ``SUB_xxx`` code to look up.

        Returns:
            Paystack subscription data dict (includes ``plan``,
            ``email_token``, etc.).

        Raises:
            HTTPException: 502 on Paystack error or network failure.
        """
        url = (
            f"{settings.PAYSTACK_BASE_URL}"
            f"/subscription/{subscription_code}"
        )
        async with httpx.AsyncClient(
            timeout=settings.PAYSTACK_TIMEOUT_SECONDS
        ) as client:
            try:
                response = await client.get(url, headers=self._auth_headers())
                response.raise_for_status()
                body = response.json()
                if not body.get("status"):
                    logger.error(
                        "Paystack get_subscription status=false "
                        "subscription_code=%s message=%s",
                        subscription_code,
                        body.get("message"),
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error: "
                            f"{body.get('message', 'unknown')}"
                        ),
                    )
                return body["data"]
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack get_subscription HTTP error "
                    "subscription_code=%s status=%s",
                    subscription_code,
                    exc.response.status_code,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack subscription fetch failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception(
                    "Paystack get_subscription network error "
                    "subscription_code=%s",
                    subscription_code,
                )
                raise HTTPException(
                    status_code=502, detail="Paystack unreachable"
                ) from exc

    async def update_plan(
        self,
        plan_code: str,
        *,
        amount_kobo: int,
        name: str | None = None,
    ) -> dict:
        """
        Update a Paystack plan's amount and optionally its name.

        Args:
            plan_code: The ``PLN_xxx`` code to update.
            amount_kobo: New charge amount in the smallest currency unit.
            name: Optional new human-readable plan name.

        Returns:
            Paystack response data dict.

        Raises:
            HTTPException: 502 on Paystack error or network failure.
        """
        payload: dict = {"amount": amount_kobo}
        if name:
            payload["name"] = name
        url = f"{settings.PAYSTACK_BASE_URL}/plan/{plan_code}"
        async with httpx.AsyncClient(
            timeout=settings.PAYSTACK_TIMEOUT_SECONDS
        ) as client:
            try:
                response = await client.put(
                    url, json=payload, headers=self._auth_headers()
                )
                response.raise_for_status()
                body = response.json()
                if not body.get("status"):
                    logger.error(
                        "Paystack update_plan status=false "
                        "plan_code=%s message=%s",
                        plan_code,
                        body.get("message"),
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error: "
                            f"{body.get('message', 'unknown')}"
                        ),
                    )
                return body.get("data") or {}
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack update_plan HTTP error "
                    "plan_code=%s status=%s",
                    plan_code,
                    exc.response.status_code,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack plan update failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception(
                    "Paystack update_plan network error plan_code=%s",
                    plan_code,
                )
                raise HTTPException(
                    status_code=502, detail="Paystack unreachable"
                ) from exc

    async def disable_subscription(self, subscription_code: str) -> None:
        """
        Disable a Paystack recurring subscription so no further charges fire.

        Paystack requires the ``email_token`` from the subscription record to
        authorise the disable call, so we fetch the subscription first.

        Args:
            subscription_code: The ``SUB_xxx`` code stored on the estate
                subscription row.

        Raises:
            HTTPException: 502 on Paystack error or network failure.
        """
        timeout = settings.PAYSTACK_TIMEOUT_SECONDS
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Step 1 — fetch subscription to get email_token.
            fetch_url = (
                f"{settings.PAYSTACK_BASE_URL}"
                f"/subscription/{subscription_code}"
            )
            try:
                fetch_resp = await client.get(
                    fetch_url, headers=self._auth_headers()
                )
                fetch_resp.raise_for_status()
                fetch_body = fetch_resp.json()
                if not fetch_body.get("status"):
                    logger.error(
                        "Paystack fetch subscription status=false "
                        "subscription_code=%s message=%s",
                        subscription_code,
                        fetch_body.get("message"),
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error fetching subscription: "
                            f"{fetch_body.get('message', 'unknown')}"
                        ),
                    )
                email_token: str | None = (fetch_body.get("data") or {}).get(
                    "email_token"
                )
                if not email_token:
                    logger.error(
                        "Paystack subscription fetch missing email_token "
                        "subscription_code=%s",
                        subscription_code,
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack subscription response missing "
                            "email_token; cannot disable"
                        ),
                    )
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack fetch subscription HTTP error "
                    "subscription_code=%s status=%s",
                    subscription_code,
                    exc.response.status_code,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack subscription fetch failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception(
                    "Paystack fetch subscription network error "
                    "subscription_code=%s",
                    subscription_code,
                )
                raise HTTPException(
                    status_code=502, detail="Paystack unreachable"
                ) from exc

            # Step 2 — disable the subscription.
            disable_url = f"{settings.PAYSTACK_BASE_URL}/subscription/disable"
            try:
                resp = await client.post(
                    disable_url,
                    json={
                        "code": subscription_code,
                        "token": email_token,
                    },
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
                body = resp.json()
                if not body.get("status"):
                    logger.error(
                        "Paystack disable_subscription status=false "
                        "subscription_code=%s message=%s",
                        subscription_code,
                        body.get("message"),
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Paystack error: "
                            f"{body.get('message', 'unknown')}"
                        ),
                    )
            except HTTPException:
                raise
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "Paystack disable_subscription HTTP error "
                    "subscription_code=%s status=%s",
                    subscription_code,
                    exc.response.status_code,
                )
                raise HTTPException(
                    status_code=502,
                    detail="Paystack disable subscription failed",
                ) from exc
            except httpx.RequestError as exc:
                logger.exception(
                    "Paystack disable_subscription network error "
                    "subscription_code=%s",
                    subscription_code,
                )
                raise HTTPException(
                    status_code=502, detail="Paystack unreachable"
                ) from exc

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Validate a Paystack webhook HMAC-SHA512 signature.

        Args:
            payload: Raw request body bytes (must not be parsed first).
            signature: Value of the ``x-paystack-signature`` header.

        Returns:
            True if the signature is valid, False otherwise.
        """
        if not self.secret_key:
            logger.warning(
                "PAYSTACK_SECRET_KEY not set — webhook signature cannot be verified"
            )
            return False
        expected = hmac.new(
            self.secret_key.encode("utf-8"),
            payload,
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
