import logging
from typing import Dict, Optional, Any
from urllib.parse import urlencode
from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.schemas.user import (
    RegisterUserRequest,
    RegisterUserResponse,
    UpdateUserRequest,
    UpdateUserResponse,
    ListUserResponse,
    SearchUserRequest,
    GetUserResponse,
    DeleteUserResponse,
    Role,
)
from app.core.config import settings
from app.libs.password_utils import verify_password

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for interacting with the db-service to manage users.

    Methods:
        create_user: Creates a new user in the db-service.
        update_user: Updates an existing user in the db-service.
        get_user_by_id: Retrieves a single user by ID.
        get_user_by_email: Retrieves a single user by email.
        delete_user: Soft deletes a user by ID.
        search_users: Searches users with filters and pagination.
        authenticate_user: Authenticates a user by email and password.
        activate_user: Activates/deactivates a user account.
        check_user_exists: Checks if a user exists and is active.
        get_role_permissions: Gets permission set for a role.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided HTTP client.

        Arguments:
            http_client: The AsyncHttpHandler instance.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL
        self.users_endpoint = f"{self.base_url}api/v1/userprofile/users"

    async def create_user(
        self, request: RegisterUserRequest, password: str
    ) -> RegisterUserResponse:
        """
        Creates a new user in the db-service.

        Args:
            request: Data for user registration.
            password: Hashed password for the user.

        Returns:
            RegisterUserResponse: Response from db-service.

        Raises:
            HTTPException: If creation fails.
        """
        payload = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "home_address": request.home_address,
            "email": request.email,
            "password": password,
            "phone_number": request.phone_number,
            "gender": request.gender.value,
            "role": request.role.value,
            "estate_id": str(request.estate_id),
            "household_id": (
                str(request.household_id) if request.household_id else None
            ),
            "status": False,
            "is_deleted": False,
        }

        url = self.users_endpoint
        response = await self.client.async_post(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500, detail="User creation failed."
            )

        user_response = RegisterUserResponse(
            id=response["id"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            home_address=payload["home_address"],
            email=payload["email"],
            gender=payload["gender"],
            role=payload["role"],
            estate_id=payload["estate_id"],
            household_id=payload.get("household_id"),
            status=payload["status"],
            created_at=response["created_at"],
        )

        logger.info(f"User created successfully: {response}")
        return user_response

    async def update_user(
        self, user_id: str, data: UpdateUserRequest
    ) -> UpdateUserResponse:
        """
        Updates an existing user in the db-service.

        Args:
            user_id: The user ID to update.
            data: UpdateUserRequest containing fields to update.

        Returns:
            UpdateUserResponse: Updated user data.

        Raises:
            HTTPException: If update fails.
        """
        # Convert UpdateUserRequest to dict for API call
        payload = {}
        if data.first_name is not None:
            payload["first_name"] = data.first_name
        if data.last_name is not None:
            payload["last_name"] = data.last_name
        if data.home_address is not None:
            payload["home_address"] = data.home_address
        if data.phone_number is not None:
            payload["phone_number"] = data.phone_number
        if data.gender is not None:
            payload["gender"] = data.gender.value
        if data.role is not None:
            payload["role"] = data.role.value
        if data.household_id is not None:
            payload["household_id"] = str(data.household_id)

        url = f"{self.users_endpoint}/{user_id}"
        response = await self.client.async_patch(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500, detail=f"User update failed for ID: {user_id}"
            )

        logger.info(f"User updated successfully: {response}")

        # Convert response to UpdateUserResponse
        return UpdateUserResponse(
            id=response["id"],
            created_at=response["created_at"],
            updated_at=response["updated_at"],
        )

    async def get_user_by_id(self, user_id: str) -> GetUserResponse | None:
        """
        Retrieves a single user by ID from the db-service.

        Args:
            user_id: The user ID to retrieve.

        Returns:
            GetUserResponse containing the user data or None if not found.
        """
        url = f"{self.users_endpoint}/{user_id}"
        response = await self.client.async_get(url)

        if not response:
            return None

        return GetUserResponse(
            id=response["id"],
            first_name=response["first_name"],
            last_name=response["last_name"],
            email=response["email"],
            home_address=response["home_address"],
            phone_number=response.get("phone_number"),
            gender=response["gender"],
            role=response["role"],
            estate_id=response["estate_id"],
            household_id=response.get("household_id"),
            status=response["status"],
            created_at=response["created_at"],
            updated_at=response.get("updated_at"),
            is_deleted=response.get("is_deleted", False),
        )

    async def get_user_by_email(self, email: str) -> GetUserResponse | None:
        """
        Retrieves a single user by email from the db-service.

        Args:
            email: The user email to search for.

        Returns:
            GetUserResponse containing the user data or None if not found.
        """
        url = f"{self.users_endpoint}/search?email={email}"
        response = await self.client.async_get(url)

        if response and response.get("items"):
            user_data = response["items"][0]
            return GetUserResponse(
                id=user_data["id"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                email=user_data["email"],
                home_address=user_data["home_address"],
                phone_number=user_data.get("phone_number"),
                gender=user_data["gender"],
                role=user_data["role"],
                estate_id=user_data["estate_id"],
                household_id=user_data.get("household_id"),
                status=user_data["status"],
                created_at=user_data["created_at"],
                updated_at=user_data.get("updated_at"),
                is_deleted=user_data.get("is_deleted", False),
            )
        return None

    async def delete_user(self, user_id: str) -> DeleteUserResponse:
        """
        Soft deletes a user by ID in the db-service.

        Args:
            user_id: The user ID to delete.

        Returns:
            DeleteUserResponse: Deletion confirmation.

        Raises:
            HTTPException: If deletion fails.
        """
        url = f"{self.users_endpoint}/{user_id}"
        response = await self.client.async_delete(url)

        if not response:
            raise HTTPException(
                status_code=500,
                detail=f"User deletion failed for ID: {user_id}",
            )

        logger.info(f"User deleted successfully: {response}")

        return DeleteUserResponse(
            is_deleted=response["is_deleted"],
            deleted_at=response["deleted_at"],
        )

    async def search_users(
        self, request: SearchUserRequest
    ) -> ListUserResponse:
        """
        Searches users with optional filters and pagination.

        Args:
            request: SearchUserRequest containing search parameters.

        Returns:
            ListUserResponse: Search results with pagination info.
        """
        # Build query parameters from SearchUserRequest
        params = {}
        if request.first_name:
            params["first_name"] = request.first_name
        if request.last_name:
            params["last_name"] = request.last_name
        if request.email:
            params["email"] = request.email
        if request.gender:
            params["gender"] = request.gender.value
        if request.role:
            params["role"] = request.role.value
        if request.estate_id:
            params["estate_id"] = str(request.estate_id)
        if request.household_id:
            params["household_id"] = str(request.household_id)
        if request.status is not None:
            params["status"] = str(request.status).lower()
        if request.from_date:
            params["from_date"] = request.from_date.isoformat()
        if request.to_date:
            params["to_date"] = request.to_date.isoformat()
        if request.page:
            params["page"] = request.page
        if request.limit:
            params["limit"] = request.limit

        # Build URL with query parameters
        base_url = f"{self.users_endpoint}/search"
        if params:
            query_string = urlencode(params)
            url = f"{base_url}?{query_string}"
        else:
            url = base_url

        response = await self.client.async_get(url)

        if not response:
            return ListUserResponse(
                total=0,
                page=request.page,
                limit=request.limit,
                items=[],
            )

        # Convert response items to GetUserResponse objects
        user_items = [
            GetUserResponse(
                id=item["id"],
                first_name=item["first_name"],
                last_name=item["last_name"],
                email=item["email"],
                home_address=item["home_address"],
                phone_number=item.get("phone_number"),
                gender=item["gender"],
                role=item["role"],
                estate_id=item.get("estate_id"),
                household_id=item.get("household_id"),
                status=item["status"],
                created_at=item["created_at"],
                updated_at=item.get("updated_at"),
                is_deleted=item.get("is_deleted", False),
            )
            for item in response.get("items", [])
        ]

        return ListUserResponse(
            total=response.get("total", 0),
            page=response.get("page", request.page),
            limit=response.get("limit", request.limit),
            items=user_items,
        )

    async def list_users(
        self, page: int = 1, limit: int = 10
    ) -> ListUserResponse:
        """
        Lists all users with pagination.

        Args:
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            ListUserResponse: User list with pagination info.
        """
        request = SearchUserRequest(page=page, limit=limit)
        return await self.search_users(request)

    async def authenticate_user(
        self, email: str, password: str
    ) -> GetUserResponse:
        """
        Authenticates a user by email and password.

        Args:
            email: User's email.
            password: User's password.

        Returns:
            GetUserResponse: User data if authentication succeeds.

        Raises:
            HTTPException: If authentication fails.
        """

        url = f"{self.users_endpoint}/search?email={email}"
        response = await self.client.async_get(url)

        if not response or not response.get("items"):
            raise HTTPException(
                status_code=401, detail="Invalid email or password"
            )

        user_data = response["items"][0]

        if not verify_password(password, user_data["password"]):
            raise HTTPException(
                status_code=401, detail="Invalid email or password"
            )

        user = dict(
            id=user_data["id"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            email=user_data["email"],
            home_address=user_data["home_address"],
            phone_number=user_data.get("phone_number"),
            gender=user_data["gender"],
            role=user_data["role"],
            estate_id=user_data.get("estate_id"),
            household_id=user_data.get("household_id"),
            status=user_data["status"],
            created_at=user_data["created_at"],
            updated_at=user_data.get("updated_at"),
            is_deleted=user_data.get("is_deleted", False),
        )

        return user

    async def activate_user(
        self, user_id: str, status: bool
    ) -> UpdateUserResponse:
        """
        Activates or deactivates a user account.

        Args:
            user_id: The user ID to activate/deactivate.
            status: True to activate, False to deactivate.

        Returns:
            UpdateUserResponse: Updated user data.

        Raises:
            HTTPException: If activation fails.
        """
        url = f"{self.users_endpoint}/{user_id}"
        response = await self.client.async_patch(
            url, json_data={"status": status}
        )

        if not response:
            raise HTTPException(
                status_code=500,
                detail=f"User activation failed for ID: {user_id}",
            )

        return UpdateUserResponse(
            id=response["id"],
            created_at=response["created_at"],
            updated_at=response["updated_at"],
        )

    async def get_users_by_estate(
        self, estate_id: str, status: Optional[bool] = None
    ) -> ListUserResponse:
        """
        Retrieves all users in a specific estate.

        Args:
            estate_id: The estate ID to filter by.
            status: Optional status filter.

        Returns:
            ListUserResponse: Users in the estate.
        """
        request = SearchUserRequest(estate_id=estate_id, status=status)
        return await self.search_users(request)

    async def get_users_by_household(
        self, household_id: str
    ) -> ListUserResponse:
        """
        Retrieves all users in a specific household.

        Args:
            household_id: The household ID to filter by.

        Returns:
            ListUserResponse: Users in the household.
        """
        request = SearchUserRequest(household_id=household_id)
        return await self.search_users(request)

    async def get_users_by_role(
        self, role: str, estate_id: Optional[str] = None
    ) -> ListUserResponse:
        """
        Retrieves users by role, optionally filtered by estate.

        Args:
            role: The user role to filter by.
            estate_id: Optional estate ID to filter by.

        Returns:
            ListUserResponse: Users with the specified role.
        """

        user_role = Role(role)
        request = SearchUserRequest(role=user_role, estate_id=estate_id)
        return await self.search_users(request)

    async def check_user_exists(self, user_id: str) -> bool:
        """
        Checks if a user exists and is not deleted.

        Args:
            user_id: The user ID to check.

        Returns:
            True if user exists and is not deleted, False otherwise.
        """
        user = await self.get_user_by_id(user_id)
        if user and not user.is_deleted and user.status:
            return True
        return False

    async def check_email_exists(self, email: str) -> bool:
        """
        Checks if an email is already registered.

        Args:
            email: The email to check.

        Returns:
            True if email exists, False otherwise.
        """
        user = await self.get_user_by_email(email)
        return user is not None

    async def get_role_permissions(self, role: str) -> Dict[str, Any]:
        """
        Fetches permission flags for a given role from db-service.

        Args:
            role: Role name (e.g., ADMIN).

        Returns:
            Dict: Permission flags.

        Raises:
            HTTPException: If retrieval fails.
        """
        url = (
            f"{self.base_url}api/v1/userprofile/rolepermission/"
            f"search?role_name={role}"
        )
        response = await self.client.async_get(url)

        if not response or not response.get("items"):
            raise HTTPException(
                status_code=404,
                detail=f"Permissions not found for role '{role}'.",
            )

        return response.get("items")[0]
