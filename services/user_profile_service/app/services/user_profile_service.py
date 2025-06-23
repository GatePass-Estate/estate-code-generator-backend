from app.schemas.user_profile import (
    RegisterUserRequest,
    RegisterUserResponse,
    # EmailTokenRequest,
    EmailTokenResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    UpdatePasswordRequest,
    UserProfileRequest,
    UserProfileResponse,
    UpdateUserHouseholdRequest,
    UpdateUserHouseholdResponse,
)
from app.repositories.user_repository import UserRepository
from app.services.token import generate_email_token, decode_email_token
from app.libs.password_utils import (
    generate_random_password,
    hash_password,
    verify_password,
)
from app.core.config import settings
from fastapi import HTTPException


class UserProfileService:
    """
    Service layer for handling user registration and profile logic.

    Methods:
        register_user: Registers a new user and generates a verification token.
    """

    def __init__(self, repository: UserRepository):
        self.repository = repository
        self.db_url = settings.DB_SERVICE_URL

    async def register_user(
        self, request: RegisterUserRequest
    ) -> tuple[RegisterUserResponse, str]:
        """
        Handles user registration flow.

        Args:
            request (RegisterUserRequest): The incoming user data.

        Returns:
            Tuple containing:
                - RegisterUserResponse: Registered user information
                - str: Email verification token
        """
        # Add hashed password
        raw_password = generate_random_password()
        hashed_pw = hash_password(raw_password)

        user = await self.repository.create_user(
            request=request, password=hashed_pw
        )

        household_id = request.household_id

        # If no household, create one and assign user as primary_resident
        if not household_id:
            household = await self.repository.create_household(
                {
                    "estate_id": str(request.estate_id),
                    "primary_resident_id": str(user.id),
                    "max_members": 10,
                }
            )
            household_id = household["id"]

        if not request.household_id:
            payload = {"household_id": household_id}
            await self.repository.update_user(
                user_id=str(user.id), data=payload
            )

        # If admin or primary_admin, add to admin_management
        if request.role in ("admin", "primary_admin"):
            await self.repository.add_admin_record(
                {
                    "estate_id": str(request.estate_id),
                    "user_id": str(user.id),
                    "is_primary": request.role == "primary_admin",
                }
            )

        token = generate_email_token(user.id)
        return user, token

    async def verify_email(self, token: str) -> EmailTokenResponse:
        """
        Verifies a user's email using the provided token.

        Args:
            request (EmailTokenRequest): The email verification token.

        Returns:
            str: Success message.

        Raises:
            HTTPException: If token is invalid or expired.
        """
        user_id = decode_email_token(token)
        user = await self.repository.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user["status"]:
            raise HTTPException(
                status_code=400, detail="Account already verified"
            )

        return EmailTokenResponse(
            message=(
                "Email verified. Please change your password"
                "to activate your account."
            ),
            user_id=user["id"],
            email=user["email"],
            must_change_password=True,
        )

    async def get_user_profile(
        self, request: UserProfileRequest
    ) -> UserProfileResponse:
        """
        Retrieves user profile information.
        """
        user = await self.repository.get_user_by_id(request.user_id)

        if not user or not user["status"]:
            raise HTTPException(status_code=404, detail="User not found")

        estate = await self.repository.get_estate_by_id(str(user["estate_id"]))
        if not estate:
            raise HTTPException(status_code=404, detail="Estate not found")

        primary_resident_id = None
        if user["household_id"]:
            household = await self.repository.get_household_by_id(
                str(user["household_id"])
            )
            if household and household["primary_resident_id"]:
                primary_resident_id = household["primary_resident_id"]

        if primary_resident_id:
            primary_resident = await self.repository.get_user_by_id(
                str(primary_resident_id)
            )
            if primary_resident:
                primary_resident_name = (
                    f"{primary_resident['first_name']} "
                    f"{primary_resident['last_name']}"
                )
            else:
                primary_resident_name = None
        else:
            primary_resident_name = None

        return UserProfileResponse(
            first_name=user["first_name"],
            last_name=user["last_name"],
            home_address=user["home_address"],
            email=user["email"],
            phone_number=user["phone_number"] or "",
            role=user["role"],
            estate_name=estate["name"],
            household_primary_resident=primary_resident_name,
            status=user["status"],
        )

    async def get_all_users_in_estate(
        self, estate_id: str | None, status: str
    ) -> list[RegisterUserResponse]:
        """
        Retrieves all users in the estate.
        """
        users = await self.repository.get_estate_users(estate_id, status)
        users = users["items"]
        return [
            RegisterUserResponse(
                id=user["id"],
                first_name=user["first_name"],
                last_name=user["last_name"],
                home_address=user["home_address"],
                email=user["email"],
                role=user["role"],
                estate_id=user["estate_id"],
                household_id=user["household_id"],
                status=user["status"],
            )
            for user in users
        ]

    async def set_user_password(
        self, request: SetPasswordRequest
    ) -> SetPasswordResponse:
        """
        Sets the user's password.

        Args:
            request (SetPasswordRequest): The password update request.

        Returns:
                SetPasswordResponse: The response indicating the success
                of the password update.

        Raises:
            HTTPException: If the user is not found or
            the password update fails.
        """
        user_id = request.user_id
        user = await self.repository.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user["status"]:
            raise HTTPException(
                status_code=400, detail="Account already verified"
            )

        hashed = hash_password(request.new_password)
        payload = {
            "password": hashed,
            "status": True,
        }
        response = await self.repository.update_user(
            user_id=request.user_id, data=payload
        )

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to update password."
            )

        return SetPasswordResponse(
            success=True, message="Password updated successfully"
        )

    async def update_user_password(
        self, request: UpdatePasswordRequest
    ) -> SetPasswordResponse:
        user = await self.repository.get_user_by_id(request.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user["status"]:
            raise HTTPException(status_code=400, detail="User not found")

        if not verify_password(request.current_password, user["password"]):
            raise HTTPException(
                status_code=400, detail="Current password is incorrect"
            )

        payload = SetPasswordRequest(
            user_id=request.user_id,
            new_password=request.new_password,
        )

        return await self.set_user_password(payload)

    async def update_user_household(
        self, request: UpdateUserHouseholdRequest
    ) -> UpdateUserHouseholdResponse:
        user = await self.repository.get_user_by_id(request.user_id)
        if not user or not user["status"]:
            raise HTTPException(status_code=404, detail="User not found")

        payload = {
            "household_id": request.household_id,
        }

        response = await self.repository.update_user(
            user_id=request.user_id, data=payload
        )

        if not response:
            raise HTTPException(
                status_code=500, detail="Failed to update household."
            )

        return UpdateUserHouseholdResponse(
            success=True, message="Household updated successfully"
        )

    async def get_estate_id_from_user_id(self, user_id: str) -> str | None:
        user = await self.repository.get_user_by_id(user_id)
        if not user or not user["status"]:
            raise HTTPException(status_code=404, detail="User not found")
        return user["estate_id"]
