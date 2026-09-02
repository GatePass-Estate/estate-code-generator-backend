"""Service layer for prediction-result search, overview, and case reads."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.code_service.prediction_result import (
    PredictionResultRepository as Repository,
)
from app.schemas.code_service.prediction_result import (
    AiSummaryPatchRequest,
    AiSummaryResponse,
    CaseDemographicResponse,
    CaseDetailResponse,
    CaseRequest,
    HistoryResponse,
    ListResponse,
    OverviewRequest,
    OverviewResponse,
    SearchRequest,
)


class PredictionResultService:
    """Pass-through to prediction-result search, overview, and case reads."""

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

    async def case_demographic(
        self, request: CaseRequest
    ) -> CaseDemographicResponse:
        """Return person-level demographic for one prediction case."""
        return await self.repository.case_demographic(request)

    async def case_history(self, request: CaseRequest) -> HistoryResponse:
        """Return up to five predictions ending at the selected instance."""
        return await self.repository.case_history(request)

    async def case_detail(self, request: CaseRequest) -> CaseDetailResponse:
        """Return the selected payload plus period sample and max maps."""
        return await self.repository.case_detail(request)

    async def patch_ai_summary(
        self, prediction_id: UUID, request: AiSummaryPatchRequest
    ) -> AiSummaryResponse:
        """Merge cached tier summaries onto the prediction row."""
        return await self.repository.patch_ai_summary(prediction_id, request)
