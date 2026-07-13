"""HTTP routes for temporal visit anomaly detection (Matrix Profile discords)."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.exceptions import LogHistoryError
from app.domain.anomaly_types import AnomalyType
from app.models.temporal_anomaly_schema import (
    TemporalAnalyzeRequest,
    TemporalAnalyzeResponse,
)
from app.pipeline.temporal_anomaly_orchestration import (
    TemporalAnomalyOrchestrator,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze/{anomaly_type}",
    response_model=TemporalAnalyzeResponse,
)
async def analyze_temporal_anomalies(
    anomaly_type: AnomalyType,
    body: TemporalAnalyzeRequest,
    current_user: dict = Depends(get_current_user),
) -> TemporalAnalyzeResponse:
    """
    Run the temporal Matrix Profile pipeline over an estate's entire history.

    Requires a bearer token. Loads validation events via
    ``load_validation_events``, builds a daily visit-count series for the estate
    (``visitor`` / ``resident`` / ``combined`` selects the log tables), then
    scores the most recent one-week window against the whole history as a
    discord. Returns 422 if history spans fewer than three windows (21 days).
    See ``explainer_docs/TEMPORAL_ANOMALY_MATRIX_PROFILE_EXPLAINER.md``.
    """
    logger.debug(
        "temporal anomaly analyze caller_id=%s anomaly_type=%s estate_id=%s",
        current_user.get("id"),
        anomaly_type.value,
        body.estate_id,
    )

    orch = TemporalAnomalyOrchestrator()
    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            result = await orch.analyze(
                client=client,
                anomaly_type=anomaly_type,
                estate_id=str(body.estate_id),
            )
        except LogHistoryError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
            ) from e

    return TemporalAnalyzeResponse(**result)
