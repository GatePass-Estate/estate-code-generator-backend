"""Unit tests for tenacity-backed transient retry helpers."""

import pytest
from fastapi import HTTPException

from app.libs.transient_retry import is_transient_error, retry_transient


def test_is_transient_for_502_503():
    assert is_transient_error(HTTPException(status_code=502, detail="x"))
    assert is_transient_error(HTTPException(status_code=503, detail="x"))


def test_is_not_transient_for_4xx():
    assert not is_transient_error(HTTPException(status_code=400, detail="x"))
    assert not is_transient_error(HTTPException(status_code=404, detail="x"))
    assert not is_transient_error(HTTPException(status_code=403, detail="x"))


def test_is_transient_for_connection_errors():
    assert is_transient_error(ConnectionError("down"))
    assert is_transient_error(TimeoutError("slow"))


@pytest.mark.asyncio
async def test_retry_transient_succeeds_after_failures():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise HTTPException(status_code=503, detail="unavailable")
        return "ok"

    result = await retry_transient(
        flaky,
        attempts=3,
        base_delay_seconds=0.01,
        operation_name="test_flaky",
    )
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_transient_gives_up_after_attempts():
    calls = {"n": 0}

    async def always_fail():
        calls["n"] += 1
        raise HTTPException(status_code=502, detail="bad gateway")

    with pytest.raises(HTTPException) as exc_info:
        await retry_transient(
            always_fail,
            attempts=3,
            base_delay_seconds=0.01,
            operation_name="test_always_fail",
        )
    assert exc_info.value.status_code == 502
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_transient_does_not_retry_non_transient():
    calls = {"n": 0}

    async def bad_request():
        calls["n"] += 1
        raise HTTPException(status_code=400, detail="bad")

    with pytest.raises(HTTPException) as exc_info:
        await retry_transient(
            bad_request,
            attempts=5,
            base_delay_seconds=0.01,
            operation_name="test_bad_request",
        )
    assert exc_info.value.status_code == 400
    assert calls["n"] == 1
