"""Daily counter rules for third-party incident summary generation."""

from __future__ import annotations

from datetime import date

DAILY_THIRD_PARTY_SUMMARY_LIMIT = 100
DAILY_LIMIT_MESSAGE = (
    "The daily limit for report summary has been reached. "
    "The limit will reset after UTC midnight."
)


class DailyGenerationLimitError(Exception):
    """Raised when an estate has already used today's third-party slots."""

    def __init__(self, message: str = DAILY_LIMIT_MESSAGE) -> None:
        super().__init__(message)
        self.message = message


def next_generation_count(
    *,
    stored_date: date | None,
    stored_count: int,
    today: date,
    limit: int = DAILY_THIRD_PARTY_SUMMARY_LIMIT,
) -> int:
    """
    Return the counter after one new third-party generation.

    A missing row or a UTC date that does not match ``today`` starts
    the cycle at 1. The same date increments by 1 until ``limit``.
    At the limit the counter is left unchanged and
    ``DailyGenerationLimitError`` is raised.

    Arguments:
        stored_date: UTC date the counter was last moved, if any.
        stored_count: Generations already recorded for that date.
        today: UTC calendar date of this generation attempt.
        limit: Maximum generations allowed on one UTC date.

    Returns:
        The counter value to store for this generation.
    """
    if stored_date is None or stored_date != today:
        return 1
    if stored_count >= limit:
        raise DailyGenerationLimitError()
    return stored_count + 1
