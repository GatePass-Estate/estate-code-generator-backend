import logging
from typing import Dict, List, Any
from urllib.parse import urlencode
from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.schemas.estate import (
    RegisterEstateRequest,
    RegisterEstateResponse,
    UpdateEstateRequest,
    UpdateEstateResponse,
    GetEstateResponse,
    DeleteEstateResponse,
    SearchEstateRequest,
    ListEstateResponse,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class EstateRepository:
    """
    Repository for interacting with the db-service
    to manage estates and permissions.

    Methods:
        create_estate: Registers a new estate in the db-service.
        update_estate: Updates an existing estate in the db-service.
        get_estate_by_id: Retrieves a single estate by ID.
        delete_estate: Soft deletes an estate by ID.
        search_estates: Searches estates with filters and pagination.
        get_estate_users: Retrieves users associated with an estate.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.estates_endpoint = f"{self.base_url}api/v1/userprofile/estates"

    async def create_estate(
        self, estate_data: RegisterEstateRequest
    ) -> RegisterEstateResponse:
        """
        Creates a new estate in the db-service.

        Args:
            estate_data: Dictionary containing estate information
                       (name, location, primary_admin_id)

        Returns:
            Dict containing the created estate data.

        Raises:
            HTTPException: If creation fails.
        """
        url = self.estates_endpoint
        response = await self.client.async_post(url, json_data=estate_data)

        if not response:
            raise HTTPException(
                status_code=500, detail="Estate creation failed."
            )
        print(response)
        estate_response = RegisterEstateResponse(
            id=response["id"],
            name=estate_data["name"],
            location=estate_data["location"],
            primary_admin_id=estate_data.get("primary_admin_id"),
            created_at=response["created_at"],
        )

        logger.info(f"Estate created successfully: {response}")
        return estate_response

    async def update_estate(
        self, estate_id: str, estate_data: UpdateEstateRequest
    ) -> UpdateEstateResponse:
        """
        Updates an existing estate in the db-service.

        Args:
            estate_id: The estate ID to update.
            estate_data: Dictionary containing fields to update
                        (name, location, primary_admin_id)

        Returns:
            Dict containing the updated estate data.

        Raises:
            HTTPException: If update fails.
        """
        url = f"{self.estates_endpoint}/{estate_id}"
        update_data = {}
        if estate_data.name is not None:
            update_data["name"] = estate_data.name
        if estate_data.location is not None:
            update_data["location"] = estate_data.location
        if estate_data.primary_admin_id is not None:
            update_data["primary_admin_id"] = str(estate_data.primary_admin_id)

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        response = await self.client.async_patch(url, json_data=update_data)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=f"Estate update failed for ID: {estate_id}",
            )

        logger.info(f"Estate updated successfully: {response}")
        return UpdateEstateResponse(
            id=response["id"],
            created_at=response["created_at"],
            updated_at=response["updated_at"],
        )

    async def get_estate_by_id(
        self, estate_id: str
    ) -> GetEstateResponse | None:
        """
        Retrieves a single estate by ID from the db-service.

        Args:
            estate_id: The estate ID to retrieve.

        Returns:
            Dict containing the estate data or None if not found.
        """
        url = f"{self.estates_endpoint}/{estate_id}"
        response = await self.client.async_get(url)
        if not response:
            raise HTTPException(
                status_code=404, detail=f"Estate not found for ID: {estate_id}"
            )

        return GetEstateResponse(
            id=response["id"],
            name=response["name"],
            location=response["location"],
            primary_admin_id=response.get("primary_admin_id"),
            created_at=response["created_at"],
            updated_at=response["updated_at"],
            is_deleted=response["is_deleted"],
        )

    async def delete_estate(self, estate_id: str) -> DeleteEstateResponse:
        """
        Soft deletes an estate by ID in the db-service.

        Args:
            estate_id: The estate ID to delete.

        Returns:
            Dict containing deletion confirmation.

        Raises:
            HTTPException: If deletion fails.
        """
        url = f"{self.estates_endpoint}/{estate_id}"
        response = await self.client.async_delete(url)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=f"Estate deletion failed for ID: {estate_id}",
            )

        logger.info(f"Estate deleted successfully: {response}")
        return DeleteEstateResponse(
            is_deleted=response["is_deleted"],
            deleted_at=response["deleted_at"],
        )

    async def search_estates(
        self, request: SearchEstateRequest
    ) -> ListEstateResponse | None:
        """
        Searches estates with optional filters and pagination.

        Args:
            name: Filter by estate name (partial match).
            location: Filter by estate location (partial match).
            primary_admin_id: Filter by primary admin ID.
            from_date: Filter by creation date (from) in ISO format.
            to_date: Filter by creation date (to) in ISO format.
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            Dict containing search results with pagination info
            or None if not found.
        """
        # Build query parameters
        params = {}
        if request.name:
            params["name"] = request.name
        if request.location:
            params["location"] = request.location
        if request.primary_admin_id:
            params["primary_admin_id"] = request.primary_admin_id
        if request.from_date:
            params["from_date"] = request.from_date
        if request.to_date:
            params["to_date"] = request.to_date
        if request.page:
            params["page"] = request.page
        if request.limit:
            params["limit"] = request.limit

        # Build URL with query parameters
        base_url = f"{self.estates_endpoint}/search"
        if params:
            query_string = urlencode(params)
            url = f"{base_url}?{query_string}"
        else:
            url = base_url

        response = await self.client.async_get(url)
        if not response:
            return ListEstateResponse(
                total=0,
                page=request.page,
                limit=request.limit,
                items=[],
            )

        estate_items = [
            GetEstateResponse(
                id=item["id"],
                name=item["name"],
                location=item["location"],
                primary_admin_id=item.get("primary_admin_id"),
                created_at=item["created_at"],
                updated_at=item["updated_at"],
                is_deleted=item["is_deleted"],
            )
            for item in response.get("items", [])
        ]

        return ListEstateResponse(
            total=response.get("total", 0),
            page=request.page,
            limit=request.limit,
            items=estate_items,
        )

    async def list_estates(
        self, page: int = 1, limit: int = 10
    ) -> ListEstateResponse | None:
        """
        Lists all estates with pagination (convenience method for
        search without filters).

        Args:
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            Dict containing estate list with pagination info
            or None if not found.
        """
        return await self.search_estates(page=page, limit=limit)

    async def get_estates_by_admin(
        self, admin_id: str
    ) -> List[Dict[str, Any]] | None:
        """
        Retrieves all estates where the given admin is the primary admin.

        Args:
            admin_id: The admin user ID to search for.

        Returns:
            List of estate dictionaries or None if not found.
        """
        response = await self.search_estates(primary_admin_id=admin_id)
        if response and "items" in response:
            return response["items"]
        return []

    async def check_estate_exists(self, estate_id: str) -> bool:
        """
        Checks if an estate exists and is not deleted.

        Args:
            estate_id: The estate ID to check.

        Returns:
            True if estate exists and is not deleted, False otherwise.
        """
        estate = await self.get_estate_by_id(estate_id)
        if estate and not estate.get("is_deleted", False):
            return True
        return False
