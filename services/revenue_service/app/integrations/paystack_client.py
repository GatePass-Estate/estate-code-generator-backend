"""Paystack client stub (Phase 2)."""


class StubError(NotImplementedError):
    """Raised when a stubbed Paystack method is called."""


class PaystackClient:
    """Phase 1 stub — real Paystack calls land in Phase 2."""

    def __init__(self, secret_key: str | None = None) -> None:
        """
        Store the Paystack secret key for Phase 2 use.

        Args:
            secret_key: Optional Paystack secret; defaults to empty string.
        """
        self.secret_key = secret_key or ""

    async def initialize_transaction(self, **kwargs):
        """
        Initialize a Paystack checkout transaction (not implemented).

        Raises:
            StubError: Always, until Phase 2.
        """
        raise StubError("Paystack checkout not implemented yet")

    async def verify_transaction(self, reference: str):
        """
        Verify a Paystack transaction by reference (not implemented).

        Args:
            reference: Paystack transaction reference.

        Raises:
            StubError: Always, until Phase 2.
        """
        raise StubError("Paystack verify not implemented yet")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Validate a Paystack webhook HMAC signature (not implemented).

        Args:
            payload: Raw request body bytes.
            signature: Value of the x-paystack-signature header.

        Raises:
            StubError: Always, until Phase 2.
        """
        raise StubError("Paystack webhook verification not implemented yet")
