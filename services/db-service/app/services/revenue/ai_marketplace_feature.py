import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.revenue.ai_marketplace_feature import (
    AiMarketplaceFeatureRepository as Repository,
)
from app.schemas.revenue.ai_marketplace_feature import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)

logger = logging.getLogger(__name__)


class AiMarketplaceFeatureService:
    """Service class for ai_marketplace_feature table."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Bind the marketplace feature repository to this session."""
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        """Create a marketplace feature."""
        return await self.repository.create(request=request)

    async def delete(self, id: str) -> DeleteResponse:
        """Soft-delete a marketplace feature by id."""
        return await self.repository.delete(id=id)

    async def get(self, id: str) -> GetResponse:
        """Return a marketplace feature by id."""
        return await self.repository.get(id=id)

    async def update(self, id: str, request: UpdateRequest) -> UpdateResponse:
        """Patch a marketplace feature by id."""
        return await self.repository.update(id=id, request=request)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        """Return a paginated list of marketplace features."""
        return await self.repository.list(page=page, limit=limit)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        """Return marketplace features matching search filters."""
        return await self.repository.search(
            request=request, page=page, limit=limit
        )
