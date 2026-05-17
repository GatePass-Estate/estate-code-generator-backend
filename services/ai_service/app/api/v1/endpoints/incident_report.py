"""Incident report intelligence: topic modelling and payment-gated LLM summary."""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user
from app.core.exceptions import IncidentReportError
from app.models.incident_schemas import (
    IncidentSummarizeRequest,
    IncidentSummarizeResponse,
)
from app.pipeline.incident_report_orchestrator import (
    IncidentReportOrchestrator,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_analyze(
    body: IncidentSummarizeRequest,
) -> IncidentSummarizeResponse:
    orch = IncidentReportOrchestrator()
    timeout = httpx.Timeout(120.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        result = await orch.analyze(
            client=client,
            estate_id=body.estate_id,
            from_date=body.from_date,
            to_date=body.to_date,
            max_records=body.max_records,
            n_topics=body.n_topics,
        )
    return IncidentSummarizeResponse(**result)


@router.post(
    "/summarize",
    response_model=IncidentSummarizeResponse,
)
async def summarize_incidents(
    body: IncidentSummarizeRequest,
    current_user: dict = Depends(get_current_user),
) -> IncidentSummarizeResponse:
    """
    Pull incidents for an estate, discover themes (TF-IDF + NMF), and when
    ``estate_payment_active`` is true also return EDA + structured LLM summary.

    When payment is inactive, ``summary`` is empty and ``topics`` is still
    populated.
    """
    logger.debug(
        "incident analyze caller_id=%s estate_id=%s",
        current_user.get("id"),
        body.estate_id,
    )
    try:
        return await _run_analyze(body)
    except IncidentReportError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        ) from e
