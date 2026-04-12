"""Domain errors surfaced as HTTP errors from the anomaly API."""


class LogHistoryError(Exception):
    """Raised when log rows cannot be loaded for analysis (fail-closed)."""

    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
