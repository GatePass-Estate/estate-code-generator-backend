"""Read and advance ``core.incident_summary_generation``."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.libs.incident_summary_quota import (
    DailyGenerationLimitError,
    next_generation_count,
)
from app.models.ai_features.incident_summary_generation import (
    IncidentSummaryGeneration as TableModel,
)
from app.schemas.ai_features.incident_summary_generation import ConsumeResponse

logger = logging.getLogger(__name__)


class IncidentSummaryGenerationRepository:
    """One generation slot per estate, reset on a new UTC date."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to ``session``."""
        self.session = session

    async def consume(self, estate_id: UUID) -> ConsumeResponse:
        """
        Reserve one new third-party generation for ``estate_id``.

        Inserts the estate row on the first attempt. When the stored
        UTC date differs from today, the counter restarts at 1.
        Otherwise it increases by 1 until the daily limit.

        Arguments:
            estate_id: Estate spending a generation.

        Returns:
            The row after the counter moved.

        Raises:
            DailyGenerationLimitError: Today's count is already at the
                daily limit. The stored counter is not changed.
            DatabaseError: The row could not be locked or written.
        """
        today = datetime.now(timezone.utc).date()
        try:
            record = await self._lock_row(estate_id)
            if record is None:
                inserted = await self._insert_first(estate_id, today)
                if inserted is not None:
                    return self._to_response(inserted)
                record = await self._lock_row(estate_id)
                if record is None:
                    raise DatabaseError(
                        "Could not create incident summary generation row"
                    )
            count = next_generation_count(
                stored_date=record.generation_date,
                stored_count=int(record.generation_count or 0),
                today=today,
            )
            record.generation_date = today
            record.generation_count = count
            record.is_deleted = False
            record.deleted_at = None
            await self.session.flush()
            await self.session.refresh(record)
            return self._to_response(record)
        except DailyGenerationLimitError:
            raise
        except SQLAlchemyError as exc:
            logger.exception("consume incident summary generation")
            raise DatabaseError(
                "Database error in consume incident summary generation"
            ) from exc

    async def _lock_row(self, estate_id: UUID) -> TableModel | None:
        """Lock the estate's slot, including a soft-deleted row."""
        query = (
            select(TableModel)
            .where(TableModel.estate_id == estate_id)
            .with_for_update()
        )
        return (await self.session.execute(query)).scalar_one_or_none()

    async def _insert_first(self, estate_id: UUID, today) -> TableModel | None:
        """
        Insert the first slot at count 1.

        Returns ``None`` when a concurrent insert won the unique
        estate slot so the caller can lock that row instead.
        """
        record = TableModel(
            estate_id=estate_id,
            generation_date=today,
            generation_count=1,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(record)
                await self.session.flush()
        except IntegrityError:
            return None
        await self.session.refresh(record)
        return record

    @staticmethod
    def _to_response(record: TableModel) -> ConsumeResponse:
        """Map the ORM row onto the API response."""
        return ConsumeResponse(
            estate_id=record.estate_id,
            generation_date=record.generation_date,
            generation_count=int(record.generation_count),
        )
