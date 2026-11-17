"""Bounded retries for transient upstream failures (via tenacity)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Status codes that usually recover after a short wait.
_TRANSIENT_HTTP_STATUSES = frozenset({502, 503})


def is_transient_error(exc: BaseException) -> bool:
    """
    Return True for failures that are worth retrying briefly.

    Retries HTTP 502/503 from our outbound client, plus common transport
    timeouts/connection errors. Validation and 4xx responses are not transient.
    """
    if isinstance(exc, HTTPException):
        return exc.status_code in _TRANSIENT_HTTP_STATUSES
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    # httpx may surface before conversion in some call paths.
    module = type(exc).__module__ or ""
    name = type(exc).__name__
    if module.startswith("httpx") and name in {
        "RequestError",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "NetworkError",
        "TimeoutException",
    }:
        return True
    return False


async def retry_transient(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    base_delay_seconds: float,
    operation_name: str,
) -> T:
    """
    Run ``operation`` up to ``attempts`` times on transient failures.

    Uses tenacity with exponential backoff. Non-transient errors raise
    immediately. Exhausted retries re-raise the last transient error.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(
            multiplier=base_delay_seconds,
            exp_base=2,
            min=base_delay_seconds,
        ),
        retry=retry_if_exception(is_transient_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    ):
        with attempt:
            logger.debug(
                "Running operation=%s attempt=%s",
                operation_name,
                attempt.retry_state.attempt_number,
            )
            return await operation()

    raise RuntimeError(
        f"retry_transient exhausted without result: {operation_name}"
    )
