"""
HTTP API for estate incident intelligence (free topics + paid LLM summary).

See ``explainer_docs/INCIDENT_REPORT_SUMMARY_EXPLAINER.md`` for mathematics and tier behaviour.
"""

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
    """Execute ``IncidentReportOrchestrator.analyze`` and validate the response."""
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
    Analyse an estate's incident cohort (TF-IDF + NMF themes always).

    **Free:** ``topics`` with ``report_text`` and assignments. **Paid** (when
    ``estate_payment_active``): adds ``summary`` with EDA and LLM JSON fields.
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
