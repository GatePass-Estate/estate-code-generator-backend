"""HTTP routes for visit anomaly analysis."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.core.exceptions import FeatureStoreError, LogHistoryError
from app.domain.anomaly_types import AnomalyType
from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.pipeline.orchestrator import AnomalyOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze/{anomaly_type}",
    response_model=AnalyzeResponse,
)
async def analyze_visit_anomalies(
    anomaly_type: AnomalyType,
    body: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
) -> AnalyzeResponse:
    """
    Run the anomaly pipeline for the given type using validation context.

    Requires a bearer token, validates path vs payload receiver alignment,
    loads log history from db-service, and returns scores plus transparency.
    """
    if anomaly_type.value != body.code_validation.receiver.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "anomaly_type in path must match code_validation.receiver "
                f"({body.code_validation.receiver.value!r})."
            ),
        )
    logger.debug(
        "anomaly analyze caller_id=%s anomaly_type=%s",
        current_user.get("id"),
        anomaly_type.value,
    )

    orch = AnomalyOrchestrator()
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            result = await orch.analyze(
                client=client,
                anomaly_type=anomaly_type,
                code_validation=body.code_validation,
            )
        except LogHistoryError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
            ) from e
        except FeatureStoreError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
            ) from e

    return AnalyzeResponse(**result)
