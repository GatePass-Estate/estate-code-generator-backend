from app.schemas.register import (
    RegisterUserRequest,
    RegisterUserResponse,
    # EmailTokenRequest,
    EmailTokenResponse,
    SetPasswordRequest,
    SetPasswordResponse,
)
from app.repositories.user_repository import UserRepository
from app.services.token import generate_email_token, decode_email_token
from app.libs.password_utils import generate_random_password, hash_password
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
        print(f"user_id: {user_id}")
        user = await self.repository.get_user_by_id(user_id)

        print(f"user: {user}")

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

    async def set_user_password(
        self, request: SetPasswordRequest
    ) -> SetPasswordResponse:
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
