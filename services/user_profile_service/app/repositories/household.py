import logging
from urllib.parse import urlencode

from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.core.config import settings
from app.schemas.household import (
    CreateHouseholdRequest,
    CreateHouseholdResponse,
    DeleteHouseholdResponse,
    HouseholdItem,
    SearchHouseholdsResponse,
)

logger = logging.getLogger(__name__)


class HouseholdRepository:
    """
    Repository for interacting with the db-service to manage households.
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

    async def create_household(
        self, request: CreateHouseholdRequest
    ) -> CreateHouseholdResponse:
        """
        Creates a new household in the db-service.

        Arguments:
            request: The create household request.
        """
        url = self.households_endpoint
        response = await self.client.async_post(
            url, json_data=request.model_dump()
        )

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to create household."
            )

        return CreateHouseholdResponse(**response)

    async def get_household_by_id(
        self, household_id: str
    ) -> HouseholdItem | None:
        """
        Retrieves a household by its ID.

        Arguments:
            household_id: The ID of the household to retrieve.
        """
        url = f"{self.households_endpoint}/{household_id}"
        response = await self.client.async_get(url)
        if response is None:
            return None
        return HouseholdItem(**response)

    async def update_household(self, household_id: str, data: dict) -> dict:
        """
        Patches a household record with raw field values.
        Accepts a plain dict to support nullable updates
        (e.g. clearing head_user_id to None).

        Arguments:
            household_id: The ID of the household to update.
            data: The fields to update (null values clear the field).
        """
        url = f"{self.households_endpoint}/{household_id}"
        response = await self.client.async_patch(url, json_data=data)

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to update household."
            )

        return response

    async def search_households(
        self,
        estate_id: str,
        name: str | None = None,
        head_user_id: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> SearchHouseholdsResponse:
        """
        Searches households by estate with optional filters.

        Arguments:
            estate_id: The estate to filter by.
            name: Optional substring match on household name.
            head_user_id: Optional filter by head user.
            page: Page number.
            limit: Items per page.
        """
        params: dict = {"estate_id": estate_id, "page": page, "limit": limit}
        if name is not None:
            params["name"] = name
        if head_user_id is not None:
            params["head_user_id"] = head_user_id
        url = f"{self.households_endpoint}/search?{urlencode(params)}"
        response = await self.client.async_get(url) or {
            "items": [],
            "total": 0,
        }
        items = [HouseholdItem(**item) for item in response.get("items", [])]
        return SearchHouseholdsResponse(
            items=items,
            total=response.get("total", 0),
            page=page,
            limit=limit,
        )

    async def delete_household(
        self, household_id: str
    ) -> DeleteHouseholdResponse:
        """
        Soft deletes a household in the db-service.

        Arguments:
            household_id: The ID of the household to delete.
        """
        url = f"{self.households_endpoint}/{household_id}"
        response = await self.client.async_delete(url)

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to delete household."
            )

        return DeleteHouseholdResponse(**response)
