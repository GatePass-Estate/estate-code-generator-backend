"""Domain errors surfaced as HTTP errors from the anomaly API."""


class LogHistoryError(Exception):
    """Raised when log rows cannot be loaded for analysis (fail-closed)."""

    def __init__(self, message: str, *, status_code: int = 422) -> None:
        """Store ``message`` and HTTP ``status_code`` for API mapping."""
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class FeatureStoreError(Exception):
    """Raised when persisted feature vectors cannot be read or written."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        """Attach ``message`` and optional HTTP status for API error mapping."""
        super().__init__(message)
        self.status_code = status_code
        self.message = message
