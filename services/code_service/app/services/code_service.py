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
        user_details: dict | None = None,
    ) -> CreateResponse:
        """
        Create a new item in the table.

        Arguments:
            request: The request body for creating a new item in the table.
            receiver: The status of the code owner (visitor or resident).
            user_details: The details of the user making the request.

        Returns:
            The CreateResponse object after creating the item in the table.
        """
        return await self.repository.create(
            request=request, receiver=receiver, user_details=user_details
        )

    async def validate(
        self, code: str, receiver: str, user_details: dict | None = None
    ) -> GetResponseResident | GetResponseVisitor:
        """
        Get an item by ID.

        Arguments:
            code: The generated access code to be validated.
            receiver: The status of the code owner (visitor or resident).
            user_details: The details of the user making the request.

        Returns:
            A GetResponse object after retrieving the item by id.
        """
        return await self.repository.get(
            code=code, receiver=receiver, user_details=user_details
        )

    async def get_items_by_user(
        self, user_id: UUID4, receiver: str, user_details: dict | None = None
    ) -> ListResponse | GetResponseResident:
        """
        Get items from the table by user ID.

        Arguments:
            user_id: The ID of the user whose items are to be retrieved.
            receiver: The status of the code owner (visitor or resident).
            user_details: The details of the user making the request.
        """
        return await self.repository._get_items_by_user(
            user_id=user_id, receiver=receiver, user_details=user_details
        )

    async def delete(
        self, code: str, user_details: dict | None = None
    ) -> None:
        """
        Delete an item from the table by its ID.

        Arguments:
            code: The ID of the item to be deleted.
            user_details: The details of the user making the request.
        """
        return await self.repository._delete(
            code=code, user_details=user_details
        )
