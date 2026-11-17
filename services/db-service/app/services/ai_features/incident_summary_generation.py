"""Service layer for the third-party incident summary daily cap."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ai_features.incident_summary_generation import (
    IncidentSummaryGenerationRepository as Repository,
)
from app.schemas.ai_features.incident_summary_generation import ConsumeResponse


class IncidentSummaryGenerationService:
    """Pass-through to the per-estate generation counter."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Bind the repository to ``db_session``."""
        self.repository = Repository(db_session)

    async def consume(self, estate_id: UUID) -> ConsumeResponse:
        """Reserve one new third-party generation for ``estate_id``."""
        return await self.repository.consume(estate_id)
