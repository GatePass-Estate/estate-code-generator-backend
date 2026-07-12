"""HTTP routes for ARIMA daily validation-volume forecasting."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.exceptions import VolumeForecastError
from app.domain.forecast_target import ForecastTarget
from app.models.forecast_schema import (
    VolumeForecastRequest,
    VolumeForecastResponse,
)
from app.pipeline.volume_forecast_orchestrator import (
    VolumeForecastOrchestrator,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/predict/{target}",
    response_model=VolumeForecastResponse,
)
async def predict_validation_volume(
    target: ForecastTarget,
    body: VolumeForecastRequest,
    current_user: dict = Depends(get_current_user),
) -> VolumeForecastResponse:
    """
    Forecast daily validation volume for an estate using ARIMA.

    ``target`` selects the stream: ``visitor``, ``resident``, or ``combined``.
    Requires a bearer token. Pulls the estate's validation history from
    db-service, buckets it into a zero-filled daily series, and returns the
    ``horizon``-day forecast with a 95% interval plus model diagnostics.
    """
    logger.debug(
        "volume forecast caller_id=%s estate_id=%s target=%s",
        current_user.get("id"),
        body.estate_id,
        target.value,
    )

    orch = VolumeForecastOrchestrator()
    timeout = httpx.Timeout(120.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            result = await orch.forecast(
                client=client,
                estate_id=body.estate_id,
                target=target,
                history_days=body.history_days,
                horizon=body.horizon,
                from_date=body.from_date,
                to_date=body.to_date,
                max_records=body.max_records,
            )
        except VolumeForecastError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
            ) from e

    return VolumeForecastResponse(**result)
