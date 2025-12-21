import logging
from typing import Optional
from urllib.parse import urlencode
from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.schemas.request import (
    CreateEditRequestResponse,
    GetEditRequestResponse,
    ListEditRequestResponse,
    SearchEditRequestRequest,
    UpdateRequestStatusResponse,
    UpdatePendingRequestResponse,
    DeletePendingRequestResponse,
    RequestStatus,
    RequestType,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class RequestRepository:
    """
    Repository for interacting with the db-service to manage edit requests.

    Methods:
        create_request: Creates a new edit request in the db-service.
        get_request_by_id: Retrieves a single request by ID.
        search_requests: Searches requests with filters and pagination.
        update_request_status: Updates the status of a request.
        list_requests: Lists all requests with pagination.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.requests_endpoint = f"{self.base_url}api/v1/userprofile/requests"

    async def create_request(
        self,
        resident_id: str,
        estate_id: str,
        request_type: str,
        old_value: str,
        new_value: str,
        status: str,
        reviewed_by: Optional[str] = None,
    ) -> CreateEditRequestResponse:
        """
        Creates a new edit request in the db-service.

        Args:
            resident_id: User making the request.
            estate_id: Estate of the user.
            request_type: Type of field change.
            old_value: Current value.
            new_value: Requested new value.
            status: Initial status of the request.
            reviewed_by: Admin who reviewed (for auto-approved requests).

        Returns:
            CreateEditRequestResponse: Response from db-service.

        Raises:
            HTTPException: If creation fails.
        """
        payload = {
            "resident_id": resident_id,
            "estate_id": estate_id,
            "request_type": request_type,
            "old_value": old_value,
            "new_value": new_value,
            "status": status,
            "reviewed_by": reviewed_by,
            "is_deleted": False,
        }

        url = self.requests_endpoint
        response = await self.client.async_post(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500, detail="Request creation failed."
            )

        request_response = CreateEditRequestResponse(
            id=response["id"],
            created_at=response["created_at"],
        )

        logger.info(f"Edit request created successfully: {response}")
        return request_response

    async def get_request_by_id(
        self, request_id: str
    ) -> GetEditRequestResponse | None:
        """
        Retrieves a single request by ID from the db-service.

        Args:
            request_id: The request ID to retrieve.

        Returns:
            GetEditRequestResponse containing the request data
            or None if not found.
        """
        url = f"{self.requests_endpoint}/{request_id}"
        response = await self.client.async_get(url)

        if not response:
            return None

        return GetEditRequestResponse(
            id=response["id"],
            resident_id=response["resident_id"],
            estate_id=response["estate_id"],
            request_type=response["request_type"],
            old_value=response["old_value"],
            new_value=response.get("new_value"),
            status=response["status"],
            reviewed_by=response.get("reviewed_by"),
            created_at=response["created_at"],
            updated_at=response.get("updated_at"),
            is_deleted=response.get("is_deleted", False),
        )

    async def search_requests(
        self, request: SearchEditRequestRequest
    ) -> ListEditRequestResponse:
        """
        Searches requests with optional filters and pagination.

        Args:
            request: SearchEditRequestRequest containing search parameters.

        Returns:
            ListEditRequestResponse: Search results with pagination info.
        """
        params = {}
        if request.resident_id:
            params["resident_id"] = str(request.resident_id)
        if request.estate_id:
            params["estate_id"] = str(request.estate_id)
        if request.request_type:
            params["request_type"] = request.request_type.value
        if request.status:
            params["status"] = request.status.value
        if request.from_date:
            params["from_date"] = request.from_date.isoformat()
        if request.to_date:
            params["to_date"] = request.to_date.isoformat()
        if request.page:
            params["page"] = request.page
        if request.limit:
            params["limit"] = request.limit

        base_url = f"{self.requests_endpoint}/search"
        if params:
            query_string = urlencode(params)
            url = f"{base_url}?{query_string}"
        else:
            url = base_url

        response = await self.client.async_get(url)

        if not response:
            return ListEditRequestResponse(
                total=0,
                page=request.page,
                limit=request.limit,
                items=[],
            )

        request_items = [
            GetEditRequestResponse(
                id=item["id"],
                resident_id=item["resident_id"],
                estate_id=item["estate_id"],
                request_type=item["request_type"],
                old_value=item["old_value"],
                new_value=item.get("new_value"),
                status=item["status"],
                reviewed_by=item.get("reviewed_by"),
                created_at=item["created_at"],
                updated_at=item.get("updated_at"),
                is_deleted=item.get("is_deleted", False),
            )
            for item in response.get("items", [])
        ]

        return ListEditRequestResponse(
            total=response.get("total", 0),
            page=response.get("page", request.page),
            limit=response.get("limit", request.limit),
            items=request_items,
        )

    async def list_requests(
        self, page: int = 1, limit: int = 10
    ) -> ListEditRequestResponse:
        """
        Lists all requests with pagination.

        Args:
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            ListEditRequestResponse: Request list with pagination info.
        """
        request = SearchEditRequestRequest(page=page, limit=limit)
        return await self.search_requests(request)

    async def get_pending_request_by_type(
        self, resident_id: str, request_type: str
    ) -> GetEditRequestResponse | None:
        """
        Retrieves a pending request for a specific user and request type.

        Args:
            resident_id: ID of the user.
            request_type: Type of field change.

        Returns:
            GetEditRequestResponse if a pending request exists, None otherwise.
        """
        search_request = SearchEditRequestRequest(
            resident_id=resident_id,
            request_type=RequestType(request_type),
            status=RequestStatus.PENDING,
            page=1,
            limit=1,
        )

        response = await self.search_requests(search_request)

        if response.total > 0 and response.items:
            return response.items[0]
        return None

    async def update_pending_request_value(
        self, request_id: str, new_value: str
    ) -> UpdatePendingRequestResponse:
        """
        Updates the new_value of a pending request.

        Args:
            request_id: The request ID to update.
            new_value: The updated value for the field.

        Returns:
            UpdatePendingRequestResponse: Updated request data.

        Raises:
            HTTPException: If update fails.
        """
        payload = {
            "new_value": new_value,
        }

        url = f"{self.requests_endpoint}/{request_id}"
        response = await self.client.async_patch(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Request value update failed for ID: " f"{request_id}"
                ),
            )

        logger.info(f"Request value updated: {response}")

        return UpdatePendingRequestResponse(
            id=response["id"],
            new_value=new_value,
            updated_at=response["updated_at"],
        )

    async def delete_pending_request(
        self, request_id: str
    ) -> DeletePendingRequestResponse:
        """
        Deletes (cancels) a pending request.

        Args:
            request_id: The request ID to delete.

        Returns:
            DeletePendingRequestResponse: Deletion confirmation.

        Raises:
            HTTPException: If deletion fails.
        """
        url = f"{self.requests_endpoint}/{request_id}"
        response = await self.client.async_delete(url)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=f"Request deletion failed for ID: {request_id}",
            )

        logger.info(f"Request deleted successfully: {request_id}")

        return DeletePendingRequestResponse(
            id=request_id,
            message="Request successfully canceled",
        )

    async def update_request_status(
        self,
        request_id: str,
        status: RequestStatus,
        reviewed_by: str,
    ) -> UpdateRequestStatusResponse:
        """
        Updates the status of a request in the db-service.

        Args:
            request_id: The request ID to update.
            status: New status value.
            reviewed_by: Admin who reviewed the request.

        Returns:
            UpdateRequestStatusResponse: Updated request data.

        Raises:
            HTTPException: If update fails.
        """
        payload = {
            "status": status.value,
            "reviewed_by": reviewed_by,
        }

        url = f"{self.requests_endpoint}/{request_id}"
        response = await self.client.async_patch(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Request status update failed for ID: " f"{request_id}"
                ),
            )

        logger.info(f"Request status updated: {response}")

        return UpdateRequestStatusResponse(
            id=response["id"],
            status=response["status"],
            reviewed_by=response["reviewed_by"],
            updated_at=response["updated_at"],
        )
