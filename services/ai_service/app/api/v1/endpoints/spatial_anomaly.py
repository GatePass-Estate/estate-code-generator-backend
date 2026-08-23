"""HTTP routes for spatial visit anomaly detection (K-means / DBSCAN / LOF ensemble)."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.exceptions import (
    EntitlementDeniedError,
    FeatureStoreError,
    LogHistoryError,
)
from app.domain.anomaly_types import AnomalyType
from app.integrations.revenue_service import (
    ANOMALY_FEATURE_KEY,
    check_ai_feature_allowed,
)
from app.models.code_validation import AnalyzeRequest
from app.models.spatial_anomaly_schema import SpatialAnalyzeResponse
from app.pipeline.spatial_anomaly_orchestration import (
    SpatialAnomalyOrchestrator,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze/{anomaly_type}",
    response_model=SpatialAnalyzeResponse,
)
async def analyze_spatial_anomalies(
    anomaly_type: AnomalyType,
    body: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
) -> SpatialAnalyzeResponse:
    """
    Run the spatial anomaly pipeline for the given type using validation context.

    Requires a bearer token, validates path vs payload receiver alignment,
    verifies the estate's AI feature entitlement via revenue-service, loads log
    history from db-service, runs K-means/DBSCAN/LOF per scope, and returns
    scores plus transparency. See ``explainer_docs/ANOMALY_DETECTION_EXPLAINER.md``.
    """
    if anomaly_type == AnomalyType.COMBINED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "anomaly_type 'combined' is only supported by the "
                "temporal-anomaly endpoint; use 'visitor' or 'resident' here."
            ),
        )
    if anomaly_type.value != body.code_validation.receiver.value:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "anomaly_type in path must match code_validation.receiver "
                f"({body.code_validation.receiver.value!r})."
            ),
        )
    logger.debug(
        "spatial anomaly analyze caller_id=%s anomaly_type=%s estate_id=%s",
        current_user.get("id"),
        anomaly_type.value,
        body.code_validation.estate_id,
    )

    orch = SpatialAnomalyOrchestrator()
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            await check_ai_feature_allowed(
                client,
                settings,
                estate_id=body.code_validation.estate_id,
                feature_key=ANOMALY_FEATURE_KEY,
            )
            result = await orch.analyze(
                client=client,
                anomaly_type=anomaly_type,
                code_validation=body.code_validation,
            )
        except EntitlementDeniedError as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=e.message,
            ) from e
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

    return SpatialAnalyzeResponse(**result)
