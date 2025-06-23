import logging
from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler

# from app.schemas.household import (
#     CreateHouseholdRequest,
# )
from app.core.config import settings

logger = logging.getLogger(__name__)


class HouseholdRepository:
    """
    Repository for interacting with the db-service to manage households.

    Methods:
        create_household: Creates a new household in the db-service.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.households_endpoint = (
            f"{self.base_url}api/v1/userprofile/household"
        )

    async def create_household(self, household_data: dict) -> dict:
        """
        Creates a new household in the db-service.

        Arguments:
            household_data: The data for the new household.
        """
        url = self.households_endpoint
        response = await self.client.async_post(url, json_data=household_data)

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to create household."
            )

        return response

    async def get_household_by_id(self, household_id: str) -> dict | None:
        url = f"{self.households_endpoint}/{household_id}"
        return await self.client.async_get(url)
