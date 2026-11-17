"""Service layer for the incident-report result page."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ai_features.incident_resultpage import (
    IncidentResultPageRepository as Repository,
)
from app.schemas.ai_features.incident_resultpage import (
    ListResponse,
    OverviewRequest,
    OverviewResponse,
    SearchRequest,
)


class IncidentResultPageService:
    """Pass-through to incident result-page overview and search."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Bind the repository to ``db_session``."""
        self.repository = Repository(db_session)

    async def overview(self, request: OverviewRequest) -> OverviewResponse:
        """Return estate identity and reporter-role counts."""
        return await self.repository.overview(request)

    async def search(
        self,
        request: SearchRequest,
        page: int = 1,
        limit: int = 10,
    ) -> ListResponse:
        """Return a paginated incident list for the result page."""
        return await self.repository.search(
            request=request, page=page, limit=limit
        )
