import logging
import secrets
from typing import List, Optional

import httpx
import pyotp
from cryptography.fernet import Fernet
from passlib.context import CryptContext

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
    Role,
)
from app.schemas.estate import UpdateEstateRequest
from app.schemas.email import (
    EmailTokenResponse,
)
from app.repositories.user import UserRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.admin_management import AdminRepository
from app.services.token import (
    generate_email_token,
    decode_email_token,
    generate_password_reset_token,
    decode_password_reset_token,
    decode_tos_pending_token,
    decode_2fa_pending_token,
)
from app.libs.password_utils import (
    generate_random_password,
    hash_password,
)
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _log_user_fetch_exception(user_id: str, exc: Exception) -> None:
    """Log the underlying db-service error; caller still returns 503 to
    clients."""
    status_code = None
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
    elif isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code

    if status_code == 404:
        logger.error("User not found while fetching user_id=%s", user_id)
    elif status_code == 500:
        logger.error(
            "Internal server error while fetching user_id=%s", user_id
        )
    else:
        logger.error(
            "Failed to fetch user_id=%s (status_code=%s): %s",
            user_id,
            status_code,
            exc,
            exc_info=True,
        )


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

    # --- private helpers ---

    def _get_fernet(self) -> Fernet:
        from app.core.config import settings

        key = settings.TOTP_ENCRYPTION_KEY
        if not key:
            raise HTTPException(
                status_code=500,
                detail="TOTP encryption key not configured.",
            )
        return Fernet(key.encode())

    def _encrypt_secret(self, secret: str) -> str:
        return self._get_fernet().encrypt(secret.encode()).decode()

    def _decrypt_secret(self, encrypted: str) -> str:
        return self._get_fernet().decrypt(encrypted.encode()).decode()

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
        # Only 1 Primary Admin per estate is allowed
        if request.role == Role.PRIMARY_ADMIN:
            if await self.admin_repository.check_primary_admin_exists(
                request.estate_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail="A primary admin already exists for this estate.",
                )

        # Generate random password for new user
        raw_password = generate_random_password()
        hashed_password = hash_password(raw_password)

        # Block if an active account already exists for this (email, estate)
        if await self.repository.check_active_email_exists(
            request.email, str(request.estate_id)
        ):
            raise HTTPException(
                status_code=400, detail="Email already registered"
            )

        user = await self.repository.create_user(request, hashed_password)
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
                request.gender,
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

        if existing_user.status:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete an active user.",
            )

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
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            home_address=user.home_address,
            email=user.email,
            phone_number=user.phone_number or "",
            gender=user.gender,
            role=user.role,
            estate_id=estate_id,
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
        self,
        estate_id: str,
        status: str | None = None,
        page: int = 1,
        limit: int = 10,
        from_date=None,
        to_date=None,
    ) -> ListUserResponse:
        """
        Gets all users in a specific estate.

        Args:
            estate_id: The estate ID.
            status: Optional status filter.
            page: Page number for pagination.
            limit: Number of items per page.
            from_date: Optional creation date filter (from).
            to_date: Optional creation date filter (to).

        Returns:
            ListUserResponse: List of users in the estate.
        """
        if status == "all":
            request = SearchUserRequest(
                estate_id=estate_id,
                page=page,
                limit=limit,
                from_date=from_date,
                to_date=to_date,
            )
        else:
            request = SearchUserRequest(
                estate_id=estate_id,
                status=status == "true",
                page=page,
                limit=limit,
                from_date=from_date,
                to_date=to_date,
            )
        response = await self.repository.search_users(request)

        # Calculate role summary by fetching all users with same filters
        try:
            role_counts = await self._get_role_counts(
                estate_id=estate_id,
                status=status,
                from_date=from_date,
                to_date=to_date,
            )

            # Import RoleSummary
            from app.schemas.user import RoleSummary

            # Add role summary to response
            response.role_summary = RoleSummary(
                root=role_counts.get("root", 0),
                primary_admin=role_counts.get("primary_admin", 0),
                admin=role_counts.get("admin", 0),
                resident=role_counts.get("resident", 0),
                security=role_counts.get("security", 0),
                guest=role_counts.get("guest", 0),
            )
        except Exception as e:
            # If role summary calculation fails, log but continue
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to calculate role summary: {e}")
            # Leave role_summary as None

        return response

    async def _get_role_counts(
        self,
        estate_id: str,
        status: str | None = None,
        from_date=None,
        to_date=None,
    ) -> dict:
        """
        Gets role counts for users in a specific estate.

        Args:
            estate_id: The estate ID.
            status: Optional status filter.
            from_date: Optional creation date filter (from).
            to_date: Optional creation date filter (to).

        Returns:
            dict: Dictionary with role as key and count as value.
        """
        # Fetch all users with same filters
        if status == "all":
            request = SearchUserRequest(
                estate_id=estate_id,
                page=1,
                limit=10000000,  # Very large limit to ensure all users
                from_date=from_date,
                to_date=to_date,
            )
        else:
            request = SearchUserRequest(
                estate_id=estate_id,
                status=status == "true",
                page=1,
                limit=10000000,  # Very large limit to ensure all users
                from_date=from_date,
                to_date=to_date,
            )

        all_users_response = await self.repository.search_users(request)

        # Count users by role
        from collections import Counter

        # Extract role as string (in case it's an enum or object)
        roles = []
        for user in all_users_response.items:
            role = user.role
            # Convert to string if it's an enum or has a value attribute
            if hasattr(role, "value"):
                role = role.value
            elif not isinstance(role, str):
                role = str(role)
            roles.append(role)

        role_counts = Counter(roles)

        return dict(role_counts)

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

    async def update_user_phone(
        self, user_id: str, phone_number: str
    ) -> UpdateUserResponse:
        """
        Updates a user's phone number by delegating to update_user.

        Minimal checks are performed; the existing update_user method
        will validate user existence.

        Args:
            user_id: ID of the user to update.
            phone_number: New phone number to set.

        Returns:
            UpdateUserResponse: Updated user metadata.
        """
        request = UpdateUserRequest(phone_number=phone_number)
        return await self.update_user(user_id=user_id, request=request)

    async def regenerate_verification_token(
        self, user_id: str
    ) -> tuple[str, str]:
        """
        Regenerates an email verification token for an unverified user.

        Args:
            user_id: The user ID to regenerate the token for.

        Returns:
            Tuple of (email, token) for sending the verification email.

        Raises:
            HTTPException: If user not found or already verified.
        """
        user = await self.repository.get_user_by_id(user_id)

        if not user or user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found")

        if user.status:
            raise HTTPException(
                status_code=400, detail="User is already verified."
            )

        token = generate_email_token(str(user.id))
        return str(user.id), token

    async def forgot_password(
        self, email: str, estate_id: Optional[str] = None
    ) -> tuple[str, str] | None:
        """
        Initiates the forgot password flow for a given email and estate.

        Looks up the active user for (email, estate_id). If estate_id is
        omitted, only resolves for root users. Returns None for any
        unresolved case to prevent enumeration.

        Args:
            email: The email address to reset the password for.
            estate_id: The estate the account belongs to. None for root only.

        Returns:
            Tuple of (email, first_name, token) if found and active, else None.
        """
        if estate_id:
            user = await self.repository.get_user_by_email_and_estate(
                email, estate_id, active_only=True
            )
        else:
            user = await self.repository.get_user_by_email(email)
            if user and user.role != Role.ROOT:
                return None

        if not user or not user.status or user.is_deleted:
            return None

        token = generate_password_reset_token(str(user.id))
        return str(user.id), token

    async def verify_password_reset_token(
        self, token: str
    ) -> EmailTokenResponse:
        """
        Validates a password reset token and returns the associated user info.

        Args:
            token: The password reset JWT token.

        Returns:
            EmailTokenResponse: User info for proceeding with password reset.

        Raises:
            HTTPException: If token is invalid, expired,
            or user not found/inactive.
        """
        try:
            user_id = decode_password_reset_token(token)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired password reset token.",
            )

        user = await self.repository.get_user_by_id(str(user_id))

        if not user or user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found.")

        if not user.status:
            raise HTTPException(
                status_code=400, detail="Account is not activated."
            )

        return EmailTokenResponse(
            message="Token verified. You may now reset your password.",
            user_id=str(user.id),
            email=user.email,
            must_change_password=False,
        )

    async def reset_password(
        self, request: SetPasswordRequest
    ) -> SetPasswordResponse:
        """
        Resets the password for an activated user
        (no current password required).

        Args:
            request: Contains user_id and the new password.

        Returns:
            SetPasswordResponse: Operation result.

        Raises:
            HTTPException: If user not found or account not activated.
        """
        user = await self.repository.get_user_by_id(str(request.user_id))

        if not user or user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found.")

        if not user.status:
            raise HTTPException(
                status_code=400, detail="Account is not activated."
            )

        hashed_password = hash_password(request.new_password)
        url = f"{self.repository.users_endpoint}/{request.user_id}"
        response = await self.repository.client.async_patch(
            url,
            json_data={"password": hashed_password},
        )

        if not response:
            raise HTTPException(
                status_code=500, detail="Password reset failed."
            )

        return SetPasswordResponse(
            success=True, message="Password has been reset successfully."
        )

    async def accept_tos(self, tos_token: str) -> dict:
        """
        Validates a TOS-pending token, records acceptance, and returns the
        data needed to generate a full access token.

        Args:
            tos_token: The tos_pending JWT token issued at login.

        Returns:
            dict: User data (id, email, role) for generating a full token.

        Raises:
            HTTPException: If token is invalid/expired or user not found.
        """
        from app.core.config import settings

        try:
            user_id = decode_tos_pending_token(tos_token)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired TOS token.",
            )

        user = await self.repository.get_user_by_id(str(user_id))

        if not user or user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found.")

        if not user.status:
            raise HTTPException(
                status_code=400, detail="Account is not activated."
            )

        url = f"{self.repository.users_endpoint}/{user.id}"
        await self.repository.client.async_patch(
            url,
            json_data={"tos_accepted_version": settings.TOS_VERSION},
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "estate_id": str(user.estate_id) if user.estate_id else None,
        }

    async def update_admin_record(self, admin_id: str, data: dict) -> dict:
        """
        Updates an admin record.
        """
        return await self.admin_repository.update_admin_record(admin_id, data)

    # ------------------------------------------------------------------
    # 2FA methods
    # ------------------------------------------------------------------

    async def setup_2fa(self, user_id: str) -> dict:
        """
        Generates a new TOTP secret, encrypts it, saves it to the user
        (totp_enabled stays False), and returns the provisioning URI + secret.
        """
        try:
            user = await self.repository.get_user_by_id(user_id)
        except Exception:
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable."
            )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        secret = pyotp.random_base32()
        encrypted = self._encrypt_secret(secret)

        url = f"{self.repository.users_endpoint}/{user_id}"
        await self.repository.client.async_patch(
            url, json_data={"totp_secret": encrypted, "totp_enabled": False}
        )

        provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="GatePass"
        )
        return {"provisioning_uri": provisioning_uri, "secret": secret}

    async def enable_2fa(
        self, user_id: str, code: str, totp_recovery_repo
    ) -> List[str]:
        """
        Verifies the TOTP code against the stored (unconfirmed) secret,
        sets totp_enabled=True, and generates 8 recovery codes.
        Returns the plaintext recovery codes (shown once).
        """
        try:
            user = await self.repository.get_user_by_id(user_id)
        except Exception as exc:
            _log_user_fetch_exception(user_id, exc)
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable."
            )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if not user.totp_secret:
            raise HTTPException(
                status_code=400, detail="2FA setup not initiated."
            )
        if user.totp_enabled:
            raise HTTPException(
                status_code=400, detail="2FA is already enabled."
            )

        plain_secret = self._decrypt_secret(user.totp_secret)
        totp = pyotp.TOTP(plain_secret)
        if not totp.verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid TOTP code.")

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        url = f"{self.repository.users_endpoint}/{user_id}"
        await self.repository.client.async_patch(
            url,
            json_data={
                "totp_enabled": True,
                "last_2fa_verified_at": now.isoformat(),
            },
        )

        # Generate 8 recovery codes
        recovery_codes = [
            f"{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}"
            for _ in range(8)
        ]

        bcrypt_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        for code_plain in recovery_codes:
            await totp_recovery_repo.create_recovery_code(
                user_id=user_id,
                code_hash=bcrypt_ctx.hash(code_plain),
            )

        return recovery_codes

    async def disable_2fa(
        self, user_id: str, code: str, totp_recovery_repo
    ) -> None:
        """
        Verifies the TOTP code, clears totp_secret/totp_enabled, and
        soft-deletes all recovery codes for the user.
        """
        try:
            user = await self.repository.get_user_by_id(user_id)
        except Exception:
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable."
            )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if not user.totp_enabled:
            raise HTTPException(status_code=400, detail="2FA is not enabled.")

        plain_secret = self._decrypt_secret(user.totp_secret)
        if not pyotp.TOTP(plain_secret).verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid TOTP code.")

        url = f"{self.repository.users_endpoint}/{user_id}"
        await self.repository.client.async_patch(
            url,
            json_data={"totp_enabled": False, "totp_secret": None},
        )
        await totp_recovery_repo.delete_all_for_user(user_id)

    async def verify_totp_code(self, user_id: str, code: str) -> bool:
        """
        Verifies a TOTP code for an already-enabled user.
        Returns True if valid, False otherwise. Does not raise on failure.
        """
        try:
            user = await self.repository.get_user_by_id(user_id)
        except Exception:
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable."
            )
        if not user or not user.totp_enabled or not user.totp_secret:
            return False
        plain_secret = self._decrypt_secret(user.totp_secret)
        return pyotp.TOTP(plain_secret).verify(code, valid_window=1)

    async def recover_with_code(
        self, two_fa_token: str, recovery_code: str, totp_recovery_repo
    ) -> dict:
        """
        Authenticates using a one-time recovery code.
        Marks the code as used and disables 2FA entirely.
        Returns user dict for token generation.
        """
        try:
            user_id = decode_2fa_pending_token(two_fa_token)
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid or expired 2FA token."
            )

        try:
            user = await self.repository.get_user_by_id(str(user_id))
        except Exception:
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable."
            )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Find an unused recovery code that matches
        result = await totp_recovery_repo.search_recovery_codes(
            user_id=str(user_id), is_used=False
        )
        codes = result.get("items", [])
        bcrypt_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        matched = None
        for record in codes:
            if bcrypt_ctx.verify(recovery_code, record["code_hash"]):
                matched = record
                break

        if not matched:
            raise HTTPException(
                status_code=401, detail="Invalid recovery code."
            )

        # Mark code as used
        from datetime import datetime, timezone

        await totp_recovery_repo.mark_code_used(
            matched["id"],
            datetime.now(timezone.utc).isoformat(),
        )

        # Disable 2FA
        url = f"{self.repository.users_endpoint}/{user_id}"
        await self.repository.client.async_patch(
            url, json_data={"totp_enabled": False, "totp_secret": None}
        )

        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "estate_id": str(user.estate_id) if user.estate_id else None,
            "tos_accepted_version": user.tos_accepted_version,
        }

    async def regenerate_recovery_codes(
        self, user_id: str, code: str, totp_recovery_repo
    ) -> List[str]:
        """
        Verifies TOTP code, soft-deletes existing recovery codes,
        and generates 8 new ones.
        """
        try:
            user = await self.repository.get_user_by_id(user_id)
        except Exception:
            raise HTTPException(
                status_code=503, detail="Service temporarily unavailable."
            )
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if not user.totp_enabled:
            raise HTTPException(status_code=400, detail="2FA is not enabled.")

        plain_secret = self._decrypt_secret(user.totp_secret)
        if not pyotp.TOTP(plain_secret).verify(code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid TOTP code.")

        await totp_recovery_repo.delete_all_for_user(user_id)

        recovery_codes = [
            f"{secrets.token_hex(3).upper()}-{secrets.token_hex(3).upper()}"
            for _ in range(8)
        ]
        bcrypt_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        for code_plain in recovery_codes:
            await totp_recovery_repo.create_recovery_code(
                user_id=user_id,
                code_hash=bcrypt_ctx.hash(code_plain),
            )

        return recovery_codes

    async def close_account(self, user_id: str) -> DeleteUserResponse:
        """
        Closes the authenticated user's own account.

        Primary admins must transfer their role before closing their account.
        Admin records and household records are cleaned up automatically.

        Args:
            user_id: The ID of the user closing their account.

        Returns:
            DeleteUserResponse: Deletion confirmation.

        Raises:
            HTTPException: If the user cannot close their account.
        """
        user = await self.repository.get_user_by_id(user_id)

        if not user or user.is_deleted:
            raise HTTPException(status_code=404, detail="User not found.")

        if user.role == "root":
            raise HTTPException(
                status_code=403,
                detail="Root accounts cannot be closed.",
            )

        if user.role == "primary_admin":
            raise HTTPException(
                status_code=403,
                detail=(
                    "You must transfer your primary admin role to another "
                    "admin before closing your account."
                ),
            )

        if user.role == "admin":
            try:
                admin_record = (
                    await self.admin_repository.get_admin_from_user_id(user_id)
                )
                await self.admin_repository.delete_admin_record(
                    admin_record["id"]
                )
            except HTTPException:
                pass

        if user.household_id:
            try:
                await self.household_repository.delete_household(
                    str(user.household_id)
                )
            except HTTPException:
                pass

        return await self.repository.delete_user(user_id)
