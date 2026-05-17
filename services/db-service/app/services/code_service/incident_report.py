import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.code_service.incident_report import (
    IncidentReportRepository as Repository,
)
from app.schemas.code_service.incident_report import (
    CreateRequest,
    CreateResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
)

logger = logging.getLogger(__name__)


class IncidentReportService:
    """CRUD and search for ``core.incidentreport`` (consumed by ai-service analyse)."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        return await self.repository.create(request=request)

    async def get(self, id: str) -> GetResponse:
        return await self.repository.get(id=id)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        return await self.repository.list(page=page, limit=limit)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        return await self.repository.search(
            request=request, page=page, limit=limit
        )
