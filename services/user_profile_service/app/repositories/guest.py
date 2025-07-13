import logging
from urllib.parse import urlencode
from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.schemas.guest import (
    RegisterGuestRequest,
    RegisterGuestResponse,
    UpdateGuestRequest,
    UpdateGuestResponse,
    ListGuestResponse,
    SearchGuestRequest,
    GetGuestResponse,
    DeleteGuestResponse,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class GuestRepository:
    """
    Repository for interacting with the db-service to manage users.

    Methods:
        create_guest: Creates a new guest in the db-service.
        update_guest: Updates an existing guest in the db-service.
        get_guest_by_id: Retrieves a single guest by ID.
        delete_guest: Soft deletes a guest by ID.
        search_guests: Searches guests with filters and pagination.
        list_guests: Lists all guests.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.guests_endpoint = f"{self.base_url}api/v1/userprofile/guests"

    async def create_guest(
        self, request: RegisterGuestRequest
    ) -> RegisterGuestResponse:
        """
        Creates a new guest in the db-service.

        Args:
            request: Data for guest registration.

        Returns:
            RegisterGuestResponse: Response from db-service.

        Raises:
            HTTPException: If creation fails.
        """
        payload = {
            "resident_id": request.resident_id,
            "guest_name": request.guest_name,
            "guest_phone_number": request.guest_phone_number,
            "guest_gender": request.guest_gender,
            "relationship": request.relationship,
            "is_deleted": False,
        }

        url = self.guests_endpoint
        response = await self.client.async_post(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500, detail="Guest creation failed."
            )

        guest_response = RegisterGuestResponse(
            id=response["id"],
            created_at=response["created_at"],
        )

        logger.info(f"Guest created successfully: {response}")
        return guest_response

    async def update_guest(
        self, guest_id: str, data: UpdateGuestRequest
    ) -> UpdateGuestResponse:
        """
        Updates an existing guest in the db-service.

        Args:
            guest_id: The guest ID to update.
            data: UpdateGuestRequest containing fields to update.

        Returns:
            UpdateGuestResponse: Updated guest data.

        Raises:
            HTTPException: If update fails.
        """
        # Convert UpdateUserRequest to dict for API call
        payload = {}
        if data.guest_name is not None:
            payload["guest_name"] = data.guest_name
        if data.guest_phone_number is not None:
            payload["guest_phone_number"] = data.guest_phone_number
        if data.guest_gender is not None:
            payload["guest_gender"] = data.guest_gender
        if data.relationship is not None:
            payload["relationship"] = data.relationship

        url = f"{self.guests_endpoint}/{guest_id}"
        response = await self.client.async_patch(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=f"Guest update failed for ID: {guest_id}",
            )

        logger.info(f"Guest updated successfully: {response}")

        # Convert response to UpdateUserResponse
        return UpdateGuestResponse(
            id=response["id"],
            created_at=response["created_at"],
            updated_at=response["updated_at"],
        )

    async def get_guest_by_id(self, guest_id: str) -> GetGuestResponse | None:
        """
        Retrieves a single guest by ID from the db-service.

        Args:
            guest_id: The guest ID to retrieve.

        Returns:
            GetGuestResponse containing the guest data or None if not found.
        """
        url = f"{self.guests_endpoint}/{guest_id}"
        response = await self.client.async_get(url)

        if not response:
            return None

        return GetGuestResponse(
            id=response["id"],
            resident_id=response["resident_id"],
            guest_name=response["guest_name"],
            guest_phone_number=response.get("guest_phone_number"),
            guest_gender=response.get("guest_gender"),
            relationship=response["relationship"],
            created_at=response["created_at"],
            updated_at=response.get("updated_at"),
            is_deleted=response.get("is_deleted", False),
        )

    async def delete_guest(self, guest_id: str) -> DeleteGuestResponse:
        """
        Soft deletes a guest by ID in the db-service.

        Args:
            guest_id: The guest ID to delete.

        Returns:
            DeleteGuestResponse: Deletion confirmation.

        Raises:
            HTTPException: If deletion fails.
        """
        url = f"{self.guests_endpoint}/{guest_id}"
        response = await self.client.async_delete(url)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=f"guest deletion failed for ID: {guest_id}",
            )

        logger.info(f"guest deleted successfully: {response}")

        return DeleteGuestResponse(
            is_deleted=response["is_deleted"],
            deleted_at=response["deleted_at"],
        )

    async def search_guests(
        self, request: SearchGuestRequest, resident_id: str
    ) -> ListGuestResponse:
        """
        Searches guests with optional filters and pagination.

        Args:
            request: SearchGuestRequest containing search parameters.

        Returns:
            ListGuestResponse: Search results with pagination info.
        """
        # Build query parameters from SearchUserRequest
        params = {}
        if resident_id:
            params["resident_id"] = str(resident_id)
        if request.guest_name:
            params["guest_name"] = request.guest_name
        if request.guest_phone_number:
            params["guest_phone_number"] = request.guest_phone_number
        if request.guest_gender:
            params["guest_gender"] = request.guest_gender
        if request.relationship:
            params["relationship"] = request.relationship
        if request.from_date:
            params["from_date"] = request.from_date.isoformat()
        if request.to_date:
            params["to_date"] = request.to_date.isoformat()
        if request.page:
            params["page"] = request.page
        if request.limit:
            params["limit"] = request.limit

        # Build URL with query parameters
        base_url = f"{self.guests_endpoint}/search"
        if params:
            query_string = urlencode(params)
            url = f"{base_url}?{query_string}"
        else:
            url = base_url

        response = await self.client.async_get(url)

        if not response:
            return ListGuestResponse(
                total=0,
                page=request.page,
                limit=request.limit,
                items=[],
            )

        # Convert response items to GetGuestResponse objects
        guest_items = [
            GetGuestResponse(
                id=item["id"],
                resident_id=item.get("resident_id"),
                guest_name=item["guest_name"],
                guest_phone_number=item.get("guest_phone_number"),
                guest_gender=item.get("guest_gender"),
                relationship=item["relationship"],
                created_at=item["created_at"],
                updated_at=item.get("updated_at"),
                is_deleted=item.get("is_deleted", False),
            )
            for item in response.get("items", [])
        ]

        return ListGuestResponse(
            total=response.get("total", 0),
            page=response.get("page", request.page),
            limit=response.get("limit", request.limit),
            items=guest_items,
        )

    async def list_guests(
        self, page: int = 1, limit: int = 10
    ) -> ListGuestResponse:
        """
        Lists all guests with pagination.

        Args:
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            ListGuestResponse: Guest list with pagination info.
        """
        request = SearchGuestRequest(page=page, limit=limit)
        return await self.search_guests(request)
