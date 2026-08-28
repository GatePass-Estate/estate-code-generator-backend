import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.revenue.payment_transaction import (
    PaymentTransactionRepository as Repository,
)
from app.schemas.revenue.payment_transaction import (
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


class PaymentTransactionService:
    """
    Service class for payment_transaction table.
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

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        return await self.repository.list(page=page, limit=limit)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        return await self.repository.search(
            request=request, page=page, limit=limit
        )
