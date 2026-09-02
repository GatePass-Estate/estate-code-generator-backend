from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.revenue.ai_marketplace_feature_rating import (
    AiMarketplaceFeatureRatingRepository as Repository,
)
from app.schemas.revenue.ai_marketplace_feature_rating import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    RatingSummaryResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)

logger = logging.getLogger(__name__)


class AiMarketplaceFeatureRatingService:
    """Service class for ai_marketplace_feature_rating table."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Bind the marketplace rating repository to this session."""
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        """Create a marketplace feature rating."""
        return await self.repository.create(request=request)

    async def delete(self, id: str) -> DeleteResponse:
        """Soft-delete a rating by id."""
        return await self.repository.delete(id=id)

    async def get(self, id: str) -> GetResponse:
        """Return a rating by id."""
        return await self.repository.get(id=id)

    async def update(self, id: str, request: UpdateRequest) -> UpdateResponse:
        """Patch a rating by id."""
        return await self.repository.update(id=id, request=request)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        """Return a paginated list of ratings."""
        return await self.repository.list(page=page, limit=limit)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        """Return ratings matching search filters."""
        return await self.repository.search(
            request=request, page=page, limit=limit
        )

    async def summary(self, feature_ids: list[UUID]) -> RatingSummaryResponse:
        """Return average rating plus bounded samples for each feature id."""
        return await self.repository.summary(feature_ids)
