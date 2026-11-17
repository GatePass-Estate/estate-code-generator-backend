"""Service layer for feature snapshots and prediction-result upserts."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.code_service.log_feature_engineering import (
    LogFeatureEngineeringRepository as Repository,
)
from app.schemas.code_service.log_feature_engineering import (
    BatchLookupRequest,
    BatchLookupResponse,
    UpsertRequest,
    UpsertResponse,
)

logger = logging.getLogger(__name__)


class LogFeatureEngineeringService:
    """Batch lookup and upsert for ``LogFeatureEngineering`` records."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    async def batch_lookup(
        self, request: BatchLookupRequest
    ) -> BatchLookupResponse:
        items = await self.repository.batch_lookup(request)
        return BatchLookupResponse(items=items)

    async def upsert(self, request: UpsertRequest) -> UpsertResponse:
        row_id, prediction_result_id = await self.repository.upsert(request)
        return UpsertResponse(
            id=row_id, prediction_result_id=prediction_result_id
        )
