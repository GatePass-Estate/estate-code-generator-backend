"""Service layer for prediction-result search and overview."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.code_service.prediction_result import (
    PredictionResultRepository as Repository,
)
from app.schemas.code_service.prediction_result import (
    ListResponse,
    OverviewRequest,
    OverviewResponse,
    SearchRequest,
)


class PredictionResultService:
    """Pass-through to prediction-result search and overview reads."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Bind the repository to ``db_session``."""
        self.repository = Repository(db_session)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 10
    ) -> ListResponse:
        """Return a paginated prediction list for the given filters."""
        return await self.repository.search(
            request=request, page=page, limit=limit
        )

    async def overview(self, request: OverviewRequest) -> OverviewResponse:
        """Return estate counts, a 30% normal sample, and period maxes."""
        return await self.repository.overview(request)
