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
    ExtendResponse,
    FreezeResponse,
    GetResponseResident,
    GetResponseVisitor,
    ListResponse,
    Receiver,
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
        receiver: Receiver,
        user_details: dict | None = None,
    ) -> CreateResponse:
        """
        Create a visitor or resident access code.

        Visitor requests may include optional ``validity_period`` and
        ``validity_window``. The total validity period may not exceed
        2 weeks from the current time.

        Raises:
            ScheduleError: If the visitor validity period exceeds 2 weeks.
        """
        return await self.repository.create(
            request=request, receiver=receiver, user_details=user_details
        )

    async def validate(
        self,
        code: str,
        user_details: dict | None = None,
        auth_token: str | None = None,
    ) -> GetResponseResident | GetResponseVisitor:
        """
        Get an item by ID.

        Arguments:
            code: The generated access code to be validated.
            user_details: The details of the user making the request.
            auth_token: Bearer token forwarded to ai-service for anomaly check.
                Anomalous results also notify estate admins.

        Returns:
            A GetResponse object after retrieving the item by id.
        """
        return await self.repository.get(
            code=code, user_details=user_details, auth_token=auth_token
        )

    async def get_items_by_user(
        self,
        user_id: UUID4,
        receiver: Receiver,
        user_details: dict | None = None,
        upcoming: bool = False,
    ) -> ListResponse | GetResponseResident:
        """
        Get items from the table by user ID.

        Arguments:
            user_id: The ID of the user whose items are to be retrieved.
            receiver: The status of the code owner (visitor or resident).
            user_details: The details of the user making the request.
            upcoming: When True, return only visitor codes scheduled for
                future use (requires visitor receiver).
        """
        return await self.repository._get_items_by_user(
            user_id=user_id,
            receiver=receiver,
            user_details=user_details,
            upcoming=upcoming,
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

    async def extend_code(
        self, code: str, user_details: dict | None = None
    ) -> ExtendResponse:
        """Extend a visitor code's validity duration by one hour."""
        return await self.repository.extend_code(
            code=code, user_details=user_details
        )

    async def toggle_freeze_code(
        self, code: str, user_details: dict | None = None
    ) -> FreezeResponse:
        """Toggle freeze/pause on a visitor code."""
        return await self.repository.toggle_freeze_code(
            code=code, user_details=user_details
        )

    async def update_resident_code(
        self, user_id: UUID4, user_details: dict | None = None
    ) -> CreateResponse:
        """
        Update a resident's access code by generating a new one.

        Arguments:
            user_id: The ID of the resident whose code needs to be updated.
            user_details: The details of the user making the request.

        Returns:
            The CreateResponse object after updating the resident's code.
        """
        return await self.repository.update_resident_code(
            user_id=user_id, user_details=user_details
        )
