"""Errors raised when a revenue-service entitlement check fails."""


class EntitlementDeniedError(Exception):
    """Raised when revenue-service denies a feature or lookup fails closed."""

    def __init__(self, message: str, *, status_code: int = 403) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
