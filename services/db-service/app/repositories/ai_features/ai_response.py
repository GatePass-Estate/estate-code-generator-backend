"""Read and upsert rows in ``core.ai_response``."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError
from app.models.ai_features.ai_response import AiResponse as TableModel
from app.schemas.ai_features.ai_response import (
    GetRequest,
    GetResponse,
    UpsertRequest,
    to_response,
)

logger = logging.getLogger(__name__)


class AiResponseRepository:
    """Lookup and merge cached AI reports by feature + lookup key."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to ``session``."""
        self.session = session

    async def get(self, request: GetRequest) -> GetResponse:
        """Return the live row for ``feature_key`` + ``lookup_key``."""
        try:
            record = await self._get_row(
                request.feature_key, request.lookup_key
            )
            if record is None:
                raise NotFoundError(
                    f"AI response {request.feature_key}/{request.lookup_key} not found"
                )
            return to_response(record)
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.exception("get ai response")
            raise DatabaseError("Database error in get ai response") from e

    async def upsert(self, request: UpsertRequest) -> GetResponse:
        """
        Insert or merge tiers into the ``ai_summary`` JSON.

        Only supplied ``tier1`` / ``tier2`` keys are written so a later
        tier-2 patch keeps an existing tier-1 payload.
        """
        try:
            record = await self._get_row(
                request.feature_key, request.lookup_key
            )
            merged = dict(record.ai_summary or {}) if record else {}
            if request.tier1 is not None:
                merged["tier1"] = request.tier1
            if request.tier2 is not None:
                merged["tier2"] = request.tier2
            if record is None:
                record = TableModel(
                    feature_key=request.feature_key,
                    lookup_key=request.lookup_key,
                    prediction_result_id=request.prediction_result_id,
                    estate_id=request.estate_id,
                    from_date=request.from_date,
                    to_date=request.to_date,
                    ai_summary=merged or None,
                )
                self.session.add(record)
            else:
                if request.prediction_result_id is not None:
                    record.prediction_result_id = request.prediction_result_id
                if request.estate_id is not None:
                    record.estate_id = request.estate_id
                if request.from_date is not None:
                    record.from_date = request.from_date
                if request.to_date is not None:
                    record.to_date = request.to_date
                record.ai_summary = merged or None
            await self.session.flush()
            await self.session.refresh(record)
            return to_response(record)
        except SQLAlchemyError as e:
            logger.exception("upsert ai response")
            raise DatabaseError("Database error in upsert ai response") from e

    async def _get_row(self, feature_key: str, lookup_key: str):
        """Load the non-deleted row for the unique pair, or ``None``."""
        query = select(TableModel).where(
            TableModel.is_deleted == False,  # noqa: E712
            TableModel.feature_key == feature_key,
            TableModel.lookup_key == lookup_key,
        )
        return (await self.session.execute(query)).scalar_one_or_none()
