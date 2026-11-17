import logging
from typing import Optional

from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_profile.incident_report import (
    IncidentReportRepository as Repository,
)
from app.schemas.user_profile.incident_report import (
    ClearReadRequest,
    CreateRequest,
    CreateResponse,
    GetResponseWithReadStatus,
    ListResponse,
    ListResponseWithReadStatus,
    MarkAllReadRequest,
    MarkReadRequest,
    SearchRequest,
)

logger = logging.getLogger(__name__)


class IncidentReportService:
    """CRUD, search, and admin read-tracking for ``core.incidentreport``."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        return await self.repository.create(request=request)

    async def get(
        self, id: UUID4, admin_id: Optional[UUID4] = None
    ) -> GetResponseWithReadStatus:
        return await self.repository.get(id=id, admin_id=admin_id)

    async def list(
        self, admin_id: UUID4, page: int = 1, limit: int = 20
    ) -> ListResponseWithReadStatus:
        return await self.repository.list(
            admin_id=admin_id, page=page, limit=limit
        )

    async def search(
        self,
        request: SearchRequest,
        admin_id: Optional[UUID4] = None,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponseWithReadStatus | ListResponse:
        return await self.repository.search(
            request=request, admin_id=admin_id, page=page, limit=limit
        )

    async def mark_read(
        self, request: MarkReadRequest, incident_report_id: UUID4
    ) -> dict:
        return await self.repository.mark_read(
            incident_report_id=incident_report_id,
            admin_id=request.admin_id,
        )

    async def mark_all_read(self, request: MarkAllReadRequest) -> dict:
        return await self.repository.mark_all_read(
            admin_id=request.admin_id,
            estate_id=request.estate_id,
        )

    async def clear_read(self, request: ClearReadRequest) -> dict:
        return await self.repository.clear_read(
            admin_id=request.admin_id,
            estate_id=request.estate_id,
        )
