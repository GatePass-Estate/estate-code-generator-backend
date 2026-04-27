"""HTTP API for feature snapshots and prediction-result persistence."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.code_service.log_feature_engineering import (
    BatchLookupRequest,
    BatchLookupResponse,
    UpsertRequest,
    UpsertResponse,
)
from app.services.code_service.log_feature_engineering import (
    LogFeatureEngineeringService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    return Service(db_session=db_session)


@router.post(
    "/batch-lookup",
    response_model=BatchLookupResponse,
    responses={500: {"description": "Internal server error"}},
    description="Return persisted feature rows for the given log ids.",
)
async def batch_lookup(
    request: BatchLookupRequest,
    service: Service = Depends(get_service),
) -> BatchLookupResponse:
    try:
        return await service.batch_lookup(request)
    except Exception as e:
        logger.exception("batch_lookup log feature engineering")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post(
    "/upsert",
    response_model=UpsertResponse,
    responses={500: {"description": "Internal server error"}},
    description=(
        "Create/merge feature JSON columns and optional prediction payload "
        "for one log-validation anchor."
    ),
)
async def upsert(
    request: UpsertRequest,
    service: Service = Depends(get_service),
) -> UpsertResponse:
    try:
        return await service.upsert(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("upsert log feature engineering")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
