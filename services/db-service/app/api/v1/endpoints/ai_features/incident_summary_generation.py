"""HTTP API for the third-party incident summary daily cap."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.db.session import get_db_session
from app.libs.incident_summary_quota import DailyGenerationLimitError
from app.schemas.ai_features.incident_summary_generation import (
    ConsumeRequest,
    ConsumeResponse,
)
from app.services.ai_features.incident_summary_generation import (
    IncidentSummaryGenerationService as Service,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    """Build a generation-cap service bound to this request session."""
    return Service(db_session=db_session)


@router.post(
    "",
    response_model=ConsumeResponse,
    responses={
        429: {"description": "Daily third-party summary limit reached"},
        500: {"description": "Internal server error"},
    },
)
async def consume_incident_summary_generation(
    body: ConsumeRequest,
    service: Service = Depends(get_service),
) -> ConsumeResponse:
    """
    Reserve one new third-party incident summary for an estate.

    Creates the estate row on the first attempt. A UTC date that does
    not match the stored date resets the counter to 1. The same date
    increases the counter by 1 until the daily limit of 100.

    Arguments:
        body: Estate spending a generation.

    Returns:
        The estate id, UTC date, and counter after this reservation.

    Raises:
        HTTPException: 429 when today's count is already 100; 500 on
            unexpected database or server errors.
    """
    try:
        return await service.consume(body.estate_id)
    except DailyGenerationLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.message,
        ) from exc
    except DatabaseError as exc:
        logger.exception("consume incident summary generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc
    except Exception as exc:
        logger.exception("consume incident summary generation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc
