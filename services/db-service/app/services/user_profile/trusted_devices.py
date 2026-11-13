import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_profile.trusted_devices import (
    TrustedDevicesRepository as Repository,
)
from app.schemas.user_profile.trusted_devices import (
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


class TrustedDevicesService:
    """
    Service class for TrustedDevices table.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        return await self.repository.create(request=request)

    async def delete(self, id: str) -> DeleteResponse:
        return await self.repository.delete(id=id)

    async def get(self, id: str) -> GetResponse:
        return await self.repository.get(id=id)

    async def update(self, id: str, request: UpdateRequest) -> UpdateResponse:
        return await self.repository.update(id=id, request=request)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 10
    ) -> ListResponse:
        return await self.repository.search(
            request=request, page=page, limit=limit
        )

    async def revoke_all_for_user(self, user_id: str) -> None:
        from uuid import UUID

        return await self.repository.revoke_all_for_user(user_id=UUID(user_id))

    async def get_by_token_hash(self, token_hash: str) -> GetResponse:
        return await self.repository.get_by_token_hash(token_hash)
