"""Daily third-party incident summary counter rules."""

from datetime import date

import pytest

from app.libs.incident_summary_quota import (
    DAILY_LIMIT_MESSAGE,
    DAILY_THIRD_PARTY_SUMMARY_LIMIT,
    DailyGenerationLimitError,
    next_generation_count,
)


def test_missing_row_starts_at_one():
    today = date(2026, 9, 27)
    assert (
        next_generation_count(stored_date=None, stored_count=0, today=today)
        == 1
    )


def test_same_utc_date_increments_by_one():
    today = date(2026, 9, 27)
    assert (
        next_generation_count(stored_date=today, stored_count=41, today=today)
        == 42
    )


def test_different_utc_date_resets_to_one():
    assert (
        next_generation_count(
            stored_date=date(2026, 9, 26),
            stored_count=DAILY_THIRD_PARTY_SUMMARY_LIMIT,
            today=date(2026, 9, 27),
        )
        == 1
    )


def test_limit_blocks_without_changing_the_count():
    today = date(2026, 9, 27)
    with pytest.raises(DailyGenerationLimitError) as blocked:
        next_generation_count(
            stored_date=today,
            stored_count=DAILY_THIRD_PARTY_SUMMARY_LIMIT,
            today=today,
        )
    assert blocked.value.message == DAILY_LIMIT_MESSAGE
    assert "UTC midnight" in blocked.value.message


def test_ninety_nine_still_allows_the_hundredth_generation():
    today = date(2026, 9, 27)
    assert (
        next_generation_count(
            stored_date=today,
            stored_count=DAILY_THIRD_PARTY_SUMMARY_LIMIT - 1,
            today=today,
        )
        == DAILY_THIRD_PARTY_SUMMARY_LIMIT
    )
