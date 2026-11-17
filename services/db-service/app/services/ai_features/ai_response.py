"""Service layer for the shared AI-response cache."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ai_features.ai_response import (
    AiResponseRepository as Repository,
)
from app.schemas.ai_features.ai_response import (
    GetRequest,
    GetResponse,
    UpsertRequest,
)


class AiResponseService:
    """Pass-through to AI-response lookup and upsert."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Bind the repository to ``db_session``."""
        self.repository = Repository(db_session)

    async def get(self, request: GetRequest) -> GetResponse:
        """Return the cached row for the feature lookup key."""
        return await self.repository.get(request)

    async def upsert(self, request: UpsertRequest) -> GetResponse:
        """Insert or merge cached tier payloads."""
        return await self.repository.upsert(request)
