import logging
from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.core.config import settings

logger = logging.getLogger(__name__)


class AdminRepository:
    """
    Repository for interacting with the db-service to manage admins.

    Methods:
        create_admin: Creates a new admin row in the db-service.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.admin_endpoint = (
            f"{self.base_url}api/v1/userprofile/adminmanagement"
        )

    async def create_admin_record(self, admin_data: dict) -> dict:
        """
        Creates a new admin in the db-service.

        Arguments:
            admin_data: The data for the new admin record.
        """
        url = self.admin_endpoint
        response = await self.client.async_post(url, json_data=admin_data)

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to create Admin."
            )

        return response

    async def update_admin_record(
        self, admin_id: str, update_data: dict
    ) -> dict:
        """
        Updates an existing admin record in the db-service.

        Arguments:
            admin_id: The ID of the admin to update.
            update_data: The fields to update.
        """
        url = f"{self.admin_endpoint}/{admin_id}"
        response = await self.client.async_patch(url, json_data=update_data)

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to update Admin."
            )

        return response

    async def get_admin_from_user_id(self, user_id: str) -> dict:
        """
        Retrieves the primary admin associated with the given user ID.

        Arguments:
            user_id: The ID of the user.

        Returns:
            The primary admin record as a dictionary.
        """
        url = f"{self.admin_endpoint}/search?" f"user_id={user_id}"
        response = await self.client.async_get(url)

        if not response["items"]:
            raise HTTPException(
                status_code=404,
                detail=f"No primary admin found for user ID {user_id}.",
            )
        return response["items"][0]

    async def get_primary_admin_from_estate_id(self, estate_id: str) -> dict:
        """
        Retrieves the primary admin associated with the given estate ID.

        Arguments:
            estate_id: The ID of the estate.

        Returns:
            The primary admin record as a dictionary.
        """
        url = (
            f"{self.admin_endpoint}/search?"
            f"estate_id={estate_id}&is_primary=true"
        )
        response = await self.client.async_get(url)

        if not response:
            raise HTTPException(
                status_code=404,
                detail=f"No primary admin found for estate ID {estate_id}.",
            )

        return response["items"][0]

    async def delete_admin_record(self, admin_id: str) -> dict:
        """
        Deletes an admin record from the db-service.

        Arguments:
            admin_id: The ID of the admin to delete.
        """
        url = f"{self.admin_endpoint}/{admin_id}"
        response = await self.client.async_delete(url)

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to delete Admin."
            )

        return response

    async def check_primary_admin_exists(self, estate_id: str) -> bool:
        """
        Checks if a primary admin exists for the given estate ID.

        Arguments:
            estate_id: The ID of the estate.

        Returns:
            bool: True if a primary admin exists, False otherwise.
        """
        url = (
            f"{self.admin_endpoint}/search?"
            f"estate_id={estate_id}&is_primary=true"
        )
        response = await self.client.async_get(url)
        response = response["items"]

        if response and not response[0]["is_deleted"]:
            return True
        return False
