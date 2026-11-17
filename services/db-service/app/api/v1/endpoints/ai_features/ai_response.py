"""HTTP API for the shared AI-response cache."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.ai_features.ai_response import (
    GetRequest,
    GetResponse,
    UpsertRequest,
)
from app.services.ai_features.ai_response import AiResponseService as Service

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    """Build an ``AiResponseService`` bound to this request session."""
    return Service(db_session=db_session)


@router.get(
    "",
    response_model=GetResponse,
    responses={
        404: {"description": "AI response not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_ai_response(
    feature_key: str,
    lookup_key: str,
    service: Service = Depends(get_service),
) -> GetResponse:
    """
    Return the cached ``ai_summary`` JSON for one feature lookup key.

    Anomaly detection uses ``feature_key=visitor_resident_anomaly_detection``
    and ``lookup_key=<prediction_result id>``. Incident summary uses
    ``feature_key=incident_summary_basic`` and
    ``lookup_key=<estate_id>:<from>:<to>``. Other features pass their own
    unique pair.

    Arguments:
        feature_key: Catalog key that owns the cache row.
        lookup_key: Feature-specific unique identity.

    Returns:
        Stored ``ai_summary`` (``{"tier1": ..., "tier2": ...}``) and
        presence flags.

    Raises:
        HTTPException: 404 if no live row exists; 500 on unexpected
            database or server errors.
    """
    try:
        return await service.get(
            GetRequest(feature_key=feature_key, lookup_key=lookup_key)
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception("get ai response")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.put(
    "",
    response_model=GetResponse,
    responses={500: {"description": "Internal server error"}},
)
async def upsert_ai_response(
    body: UpsertRequest,
    service: Service = Depends(get_service),
) -> GetResponse:
    """
    Insert or merge cached summaries for one feature lookup key.

    Only provided ``tier1`` / ``tier2`` keys are merged into the
    ``ai_summary`` JSON. Existing payloads for omitted tiers are kept.

    Arguments:
        body: Feature key, lookup key, optional typed anchors, and
            tier payloads to store.

    Returns:
        The live cache row after the merge.

    Raises:
        HTTPException: 500 on unexpected database or server errors.
    """
    try:
        return await service.upsert(body)
    except Exception as e:
        logger.exception("upsert ai response")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
