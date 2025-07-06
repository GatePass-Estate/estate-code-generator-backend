import logging

from pydantic import UUID4

from app.libs.http_handler import AsyncHttpHandler
from app.repositories.code_service import (
    CodeServiceRepository as Repository,
)
from app.schemas.code_service import (
    CreateRequestResident,
    CreateRequestVisitor,
    CreateResponse,
    GetResponseResident,
    GetResponseVisitor,
    ListResponse,
)

logger = logging.getLogger(__name__)


class CodeService:
    """
    Service class for workflows.workflows table.

    Attributes:
        repository: Repository logic for the table.
    """

    def __init__(self, ahttp_client: AsyncHttpHandler) -> None:
        self.ahttp_client = ahttp_client
        self.repository = Repository(ahttp_client)

    async def generate(
        self,
        request: CreateRequestVisitor | CreateRequestResident,
        receiver: str,
    ) -> CreateResponse:
        """
        Create a new item in the table.

        Arguments:
            request: The request body for creating a new item in the table.
            receiver: The status of the code owner (visitor or resident).

        Returns:
            The CreateResponse object after creating the item in the table.
        """
        return await self.repository.create(request=request, receiver=receiver)

    async def validate(
        self, code: str, receiver: str
    ) -> GetResponseResident | GetResponseVisitor:
        """
        Get an item by ID.

        Arguments:
            code: The generated access code to be validated.
            receiver: The status of the code owner (visitor or resident).

        Returns:
            A GetResponse object after retrieving the item by id.
        """
        return await self.repository.get(code=code, receiver=receiver)

    async def get_items_by_user(
        self, user_id: UUID4, receiver: str
    ) -> ListResponse | GetResponseResident:
        """
        Get items from the table by user ID.
        """
        return await self.repository._get_items_by_user(
            user_id=user_id, receiver=receiver
        )

    async def delete(self, code: str) -> None:
        """
        Delete an item from the table by its ID.
        """
        return await self.repository._delete(code=code)
