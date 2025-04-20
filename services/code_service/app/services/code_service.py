import logging

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
)

logger = logging.getLogger(__name__)


class CodeService:
    """
    Service class for workflows.workflows table.

    Attributes:
        repository: Repository logic for the table.
    """

    def __init__(self, ahttp_client: AsyncHttpHandler) -> None:
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
            id: The ID of the item to retrieve.

        Returns:
            A GetResponse object after retrieving the item by id.
        """
        return await self.repository.get(code=code, receiver=receiver)
