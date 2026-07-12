import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)


async def scheduled_http_job(
    url: str,
    internal_api_key: str,
    hour: int = 0,
    name: str = "job",
) -> None:
    """
    Runs an HTTP POST to `url` at `hour` (UTC, 0-23) every day.

    Designed to run as a long-lived asyncio task (e.g. via
    asyncio.create_task inside a FastAPI lifespan). Failures are logged
    but do not stop the loop — the next run will still be scheduled.

    Args:
        url: Full URL to POST to (e.g.
        http://user-profile-service:9034/api/v1/internal/cron/daily).
        internal_api_key: Value sent as the X-Internal-Key header.
        hour: UTC hour at which the job runs (0-23). Defaults to 0 (midnight).
        name: Human-readable label used in log messages.
    """
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)

        sleep_seconds = (next_run - now).total_seconds()
        logger.info(
            "[%s] Next run scheduled for %s (in %.0fs)",
            name,
            next_run.isoformat(),
            sleep_seconds,
        )
        await asyncio.sleep(sleep_seconds)

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    url,
                    headers={"X-Internal-Key": internal_api_key},
                )
                logger.info(
                    "[%s] Completed: HTTP %s — %s",
                    name,
                    response.status_code,
                    response.text[:200],
                )
        except Exception:
            logger.exception("[%s] HTTP call failed", name)
