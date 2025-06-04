import logging
from fastapi import HTTPException

from app.libs.http_handler import AsyncHttpHandler
from app.schemas.register import RegisterUserRequest, RegisterUserResponse
from app.core.config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for interacting with the db-service
    to manage users and permissions.

    Methods:
        create_user: Registers a new user in the db-service.
        get_role_permissions: Retrieves permission set for a given role.
    """

    def __init__(self, http_client: AsyncHttpHandler):
        """
        Initializes the repository with the provided session.

        Arguments:
            session: The HttpClient session.
        """
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL

    async def create_user(
        self, request: RegisterUserRequest, password: str
    ) -> RegisterUserResponse:
        """
        Sends a POST request to db-service to create a new user.

        Args:
            request (RegisterUserRequest): Data for user registration.
            user_id (UUID): ID to assign to the new user.

        Returns:
            RegisterUserResponse: Response from db-service.

        Raises:
            HTTPException: If creation fails.
        """

        payload = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "email": request.email,
            "password": password,
            "role": request.role.value,
            "estate_id": str(request.estate_id),
            "household_id": str(request.household_id)
            if request.household_id
            else None,
            "status": False,
            "is_deleted": False,
        }

        url = f"{self.base_url}api/v1/userprofile/users"
        response = await self.client.async_post(url, json_data=payload)

        if not response:
            raise HTTPException(
                status_code=500, detail="User creation failed."
            )

        response = RegisterUserResponse(
            id=response["id"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            email=payload["email"],
            role=payload["role"],
            estate_id=payload["estate_id"],
            household_id=payload.get("household_id"),
            status=payload["status"],
        )
        # return response
        return RegisterUserResponse.model_validate(response)

    async def get_role_permissions(self, role: str) -> dict:
        """
        Fetches permission flags for a given role from db-service.

        Args:
            role (str): Role name (e.g., ADMIN).

        Returns:
            dict: Permission flags.

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
        response = response.get("items")[0]
        return response

    async def authenticate_user(self, email: str, password: str) -> dict:
        """
        Authenticates a user by email and password.

        Args:
            email (str): User's email.
            password (str): User's password.

        Returns:
                dict: User data if authentication succeeds.

        Raises:
                    HTTPException: If authentication fails.
        """
        url = f"{self.base_url}api/v1/userprofile/users/search?email={email}"
        user = await self.client.async_get(url)

        if not user or not user.get("items"):
            raise HTTPException(
                status_code=401, detail="Invalid email or password"
            )

        user_data = user["items"][0]

        if not pwd_context.verify(password, user_data["password"]):
            raise HTTPException(
                status_code=401, detail="Invalid email or password"
            )

        return user_data

    async def get_user_by_id(self, user_id: str) -> dict:
        url = f"{self.base_url}api/v1/userprofile/users/{user_id}"
        return await self.client.async_get(url)

    async def update_user(self, user_id: str, data: dict) -> dict:
        url = f"{self.base_url}api/v1/userprofile/users/{user_id}"
        return await self.client.async_patch(url, json_data=data)
