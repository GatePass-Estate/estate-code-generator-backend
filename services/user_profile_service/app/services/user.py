from app.schemas.user import (
    RegisterUserRequest,
    RegisterUserResponse,
    UpdateUserRequest,
    UpdateUserResponse,
    GetUserResponse,
    DeleteUserResponse,
    SearchUserRequest,
    ListUserResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    UpdatePasswordRequest,
    UserProfileRequest,
    UserProfileResponse,
)
from app.schemas.estate import UpdateEstateRequest
from app.schemas.email import (
    EmailTokenResponse,
)
from app.repositories.user import UserRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.admin_management import AdminRepository
from app.services.token import generate_email_token, decode_email_token
from app.libs.password_utils import (
    generate_random_password,
    hash_password,
)
from fastapi import HTTPException


class UserService:
    """
    Service layer for handling user management and related logic.

    Methods:
        register_user: Registers a new user.
        update_user: Updates an existing user.
        get_user: Retrieves a user by ID.
        delete_user: Soft deletes a user.
        search_users: Searches users with filters and pagination.
        authenticate_user: Authenticates a user.
        set_password: Sets user password (for new accounts).
        update_password: Updates user password (for existing accounts).
        activate_user: Activates/deactivates user account.
        get_user_profile: Gets user profile information.
        verify_email: Verifies user email with token.
    """

    def __init__(
        self,
        repository: UserRepository,
        estate_repository: EstateRepository,
        household_repository: HouseholdRepository,
        admin_repository: AdminRepository,
    ):
        self.repository = repository
        self.estate_repository = estate_repository
        self.household_repository = household_repository
        self.admin_repository = admin_repository

    async def register_user(
        self, request: RegisterUserRequest
    ) -> tuple[RegisterUserResponse, str]:
        """
        Handles user registration flow.

        Args:
            request: The incoming user registration data.

        Returns:
            Tuple containing:
                - RegisterUserResponse: Registered user information
                - str: Email verification token

        Raises:
            HTTPException: If registration fails or email exists.
        """
        # Check if email already exists
        if await self.repository.check_email_exists(request.email):
            raise HTTPException(
                status_code=400, detail="Email already registered"
            )

        # Generate random password for new user
        raw_password = generate_random_password()
        hashed_password = hash_password(raw_password)

        # Create user through repository
        user = await self.repository.create_user(request, hashed_password)

        # Generate email verification token
        token = generate_email_token(str(user.id))

        return user, token

    async def update_user(
        self, user_id: str, request: UpdateUserRequest
    ) -> UpdateUserResponse:
        """
        Updates an existing user.

        Args:
            user_id: The user ID to update.
            request: The update data.

        Returns:
            UpdateUserResponse: Updated user information.

        Raises:
            HTTPException: If user not found or update fails.
        """
        # Check if user exists
        existing_user = await self.repository.get_user_by_id(user_id)
        if not existing_user or existing_user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if any fields are being updated
        if all(
            field is None
            for field in [
                request.first_name,
                request.last_name,
                request.home_address,
                request.phone_number,
                request.role,
                request.household_id,
            ]
        ):
            raise HTTPException(status_code=400, detail="No fields to update")

        return await self.repository.update_user(user_id, request)

    async def get_user(self, user_id: str) -> GetUserResponse:
        """
        Retrieves a user by ID.

        Args:
            user_id: The user ID to retrieve.

        Returns:
            GetUserResponse: User information.

        Raises:
            HTTPException: If user not found.
        """
        user = await self.repository.get_user_by_id(user_id)

        if not user or user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    async def delete_user(self, user_id: str) -> DeleteUserResponse:
        """
        Soft deletes a user.

        Args:
            user_id: The user ID to delete.

        Returns:
            DeleteUserResponse: Deletion confirmation.

        Raises:
            HTTPException: If user not found or already deleted.
        """
        # Check if user exists and is not already deleted
        existing_user = await self.repository.get_user_by_id(user_id)
        if not existing_user or existing_user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found")

        return await self.repository.delete_user(user_id)

    async def search_users(
        self, request: SearchUserRequest
    ) -> ListUserResponse:
        """
        Searches users with filters and pagination.

        Args:
            request: Search parameters.

        Returns:
            ListUserResponse: Search results with pagination.
        """
        return await self.repository.search_users(request)

    async def list_users(
        self, page: int = 1, limit: int = 10
    ) -> ListUserResponse:
        """
        Lists all users with pagination.

        Args:
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            ListUserResponse: User list with pagination.
        """
        request = SearchUserRequest(page=page, limit=limit)
        return await self.repository.search_users(request)

    async def authenticate_user(
        self, email: str, password: str
    ) -> GetUserResponse:
        """
        Authenticates a user by email and password.

        Args:
            email: User's email.
            password: User's password.

        Returns:
            GetUserResponse: Authenticated user data.

        Raises:
            HTTPException: If authentication fails.
        """
        return await self.repository.authenticate_user(email, password)

    async def set_password_and_activate(
        self, request: SetPasswordRequest
    ) -> SetPasswordResponse:
        """
        Sets user password (for new accounts after email verification).

        Args:
            request: The password set request.

        Returns:
            SetPasswordResponse: Operation result.

        Raises:
            HTTPException: If user not found or already activated.
        """
        user = await self.repository.get_user_by_id(str(request.user_id))

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.status:
            raise HTTPException(
                status_code=400, detail="Account already activated"
            )

        # Hash password and activate account
        hashed_password = hash_password(request.new_password)

        response = await self.validate_user(str(request.user_id))

        if not response:
            raise HTTPException(
                status_code=500, detail="Account Validation Failed"
            )

        # Update password and activate user
        url = f"{self.repository.users_endpoint}/{request.user_id}"
        response = await self.repository.client.async_patch(
            url,
            json_data={
                "password": hashed_password,
                "status": True,
            },
        )

        if not response:
            raise HTTPException(
                status_code=500, detail="Password update failed"
            )

        return SetPasswordResponse(
            success=True,
            message="Password set and account activated successfully",
        )

    async def update_password(
        self, request: UpdatePasswordRequest
    ) -> SetPasswordResponse:
        """
        Updates user password (for existing activated accounts).

        Args:
            request: The password update request.

        Returns:
            SetPasswordResponse: Operation result.

        Raises:
            HTTPException: If user not found or current password incorrect.
        """
        user = await self.repository.get_user_by_id(str(request.user_id))

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.status:
            raise HTTPException(
                status_code=400, detail="Account not activated"
            )

        try:
            await self.repository.authenticate_user(
                user.email, request.current_password
            )
        except HTTPException:
            raise HTTPException(
                status_code=400, detail="Current password is incorrect"
            )

        # Update password
        hashed_password = hash_password(request.new_password)
        url = f"{self.repository.users_endpoint}/{request.user_id}"
        response = await self.repository.client.async_patch(
            url,
            json_data={
                "password": hashed_password,
            },
        )

        if not response:
            raise HTTPException(
                status_code=500, detail="Password update failed"
            )

        return SetPasswordResponse(
            success=True, message="Password updated successfully"
        )

    async def validate_user(self, user_id: str) -> bool:
        """
        Activates or deactivates a user account.

        Args:
            user_id: The user ID to activate/deactivate.
            status: True to activate, False to deactivate.

        Returns:
            Bool: True if user status updated, False otherwise.

        Raises:
            HTTPException: If user not found.
        """
        try:
            # Check if user exists
            user = await self.repository.get_user_by_id(user_id)
            if not user or user.is_deleted:
                raise HTTPException(status_code=404, detail="User not found")

            # If no household and the role is NOT the root user,
            # create one and assign user as primary_resident
            if not user.household_id and user.role != "root":
                household = await self.household_repository.create_household(
                    {
                        "estate_id": str(user.estate_id),
                        "primary_resident_id": str(user.id),
                        "max_members": 10,
                    }
                )
                household_id = household["id"]
                payload = UpdateUserRequest(household_id=household_id)
                await self.repository.update_user(
                    user_id=str(user.id), data=payload
                )

            # If admin or primary_admin, add to admin_management
            if user.role in ("admin", "primary_admin"):
                await self.admin_repository.create_admin_record(
                    {
                        "estate_id": str(user.estate_id),
                        "user_id": str(user.id),
                        "is_primary": user.role == "primary_admin",
                    }
                )
                if user.role == "primary_admin":
                    payload = UpdateEstateRequest(
                        primary_admin_id=str(user.id)
                    )
                    await self.estate_repository.update_estate(
                        estate_id=str(user.estate_id), estate_data=payload
                    )
            return True
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def get_user_profile(
        self, request: UserProfileRequest
    ) -> UserProfileResponse:
        """
        Retrieves user profile information with estate details.

        Args:
            request: The user profile request containing user_id.

        Returns:
            UserProfileResponse: User profile information.

        Raises:
            HTTPException: If user not found or not activated.
        """
        user = await self.repository.get_user_by_id(str(request.user_id))

        if not user or not user.status:
            raise HTTPException(status_code=404, detail="User not found")

        estate_id = user.estate_id
        estate_name = await self.estate_repository.get_estate_by_id(
            str(estate_id)
        )
        if not estate_name:
            raise HTTPException(status_code=404, detail="Estate not found")
        estate_name = estate_name.name

        primary_resident_id = None
        if user.household_id:
            household = await self.household_repository.get_household_by_id(
                str(user.household_id)
            )
            if household and household["primary_resident_id"]:
                primary_resident_id = household["primary_resident_id"]

        if primary_resident_id:
            primary_resident = await self.repository.get_user_by_id(
                str(primary_resident_id)
            )
            if primary_resident:
                primary_resident_name = (
                    f"{primary_resident.first_name} "
                    f"{primary_resident.last_name}"
                )
            else:
                primary_resident_name = None
        else:
            primary_resident_name = None

        return UserProfileResponse(
            first_name=user.first_name,
            last_name=user.last_name,
            home_address=user.home_address,
            email=user.email,
            phone_number=user.phone_number or "",
            role=user.role,
            estate_name=estate_name,
            household_primary_resident=primary_resident_name,
            status=user.status,
        )

    async def verify_email(self, token: str) -> EmailTokenResponse:
        """
        Verifies user email using the provided token.

        Args:
            token: The email verification token.

        Returns:
            EmailTokenResponse: Verification result.

        Raises:
            HTTPException: If token invalid or user not found.
        """
        user_id = decode_email_token(token)
        user = await self.repository.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.status:
            raise HTTPException(
                status_code=400, detail="Account already verified"
            )

        return EmailTokenResponse(
            message=(
                "Email verified. Please set your password "
                "to activate your account."
            ),
            user_id=str(user.id),
            email=user.email,
            must_change_password=True,
        )

    async def get_users_by_estate(
        self, estate_id: str, status: str | None = None
    ) -> ListUserResponse:
        """
        Gets all users in a specific estate.

        Args:
            estate_id: The estate ID.
            status: Optional status filter.

        Returns:
            ListUserResponse: List of users in the estate.
        """
        if status == "all":
            request = SearchUserRequest(estate_id=estate_id)
        else:
            request = SearchUserRequest(
                estate_id=estate_id, status=status == "true"
            )
        return await self.repository.search_users(request)

    async def get_estate_id_by_user_id(self, user_id: str) -> str:
        """
        Gets the estate ID associated with a user.

        Args:
            user_id: The user ID.

        Returns:
            str: The estate ID.
        """
        user = await self.repository.get_user_by_id(user_id)
        return str(user.estate_id)

    async def get_users_by_household(
        self, household_id: str
    ) -> ListUserResponse:
        """
        Gets all users in a specific household.

        Args:
            household_id: The household ID.

        Returns:
            ListUserResponse: List of users in the household.
        """
        request = SearchUserRequest(household_id=household_id)
        return await self.repository.search_users(request)

    async def get_users_by_role(
        self, role: str, estate_id: str | None = None
    ) -> ListUserResponse:
        """
        Gets users by role, optionally filtered by estate.

        Args:
            role: The user role.
            estate_id: Optional estate ID filter.

        Returns:
            ListUserResponse: List of users with the specified role.
        """
        return await self.repository.get_users_by_role(role, estate_id)

    async def check_user_exists(self, user_id: str) -> bool:
        """
        Checks if a user exists and is not deleted.

        Args:
            user_id: The user ID to check.

        Returns:
            True if user exists and is active, False otherwise.
        """
        return await self.repository.check_user_exists(user_id)

    async def check_email_exists(self, email: str) -> bool:
        """
        Checks if an email is already registered.

        Args:
            email: The email to check.

        Returns:
            True if email exists, False otherwise.
        """
        return await self.repository.check_email_exists(email)

    async def check_same_estate(
        self, user_id: str, requester_user_id: str
    ) -> bool:
        """
        Checks if a user is in the same estate as the requester.

        Args:
            user_id: The user ID to check.
            requester_user_id: The ID of the user making the request.

        Returns:
            True if the user is in the same estate, False otherwise.
        """
        try:
            user = await self.repository.get_user_by_id(user_id)
            requester = await self.repository.get_user_by_id(requester_user_id)
            return user.estate_id == requester.estate_id
        except Exception:
            return False

    async def update_admin_record(self, admin_id: str, data: dict) -> dict:
        """
        Updates an admin record.
        """
        return await self.admin_repository.update_admin_record(admin_id, data)
