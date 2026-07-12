from datetime import datetime, timezone

from fastapi import HTTPException

from app.repositories.estate import EstateRepository
from app.repositories.user import UserRepository
from app.schemas.estate import (
    DeleteEstateResponse,
    GetEstateResponse,
    ListEstateResponse,
    RegisterEstateRequest,
    RegisterEstateResponse,
    SearchEstateRequest,
    UpdateEstateRequest,
    UpdateEstateResponse,
)
from app.schemas.user import UpdateUserRequest


class EstateService:
    """
    Service layer for handling estate management and related logic.

    Methods:
        register_estate: Registers a new estate.
        update_estate: Updates an existing estate.
        get_estate: Retrieves an estate by ID.
        delete_estate: Soft deletes an estate.
        search_estates: Searches estates with filters and pagination.
        list_estates: Lists all estates with pagination.
        get_estate_id_from_user_id: Gets estate ID from user ID.
        validate_admin_access: Validates admin access to estate.
    """

    def __init__(
        self,
        estate_repository: EstateRepository,
        user_repository: UserRepository,
    ):
        self.estate_repository = estate_repository
        self.user_repository = user_repository

    async def register_estate(
        self, request: RegisterEstateRequest
    ) -> RegisterEstateResponse:
        """
        Handles estate registration flow.

        Args:
            request (RegisterEstateRequest): The incoming estate data.

        Returns:
            RegisterEstateResponse: Registered estate information.

        Raises:
            HTTPException: If registration fails or admin not found.
        """
        # Validate primary admin exists if provided
        if request.primary_admin_id:
            admin = await self.user_repository.get_user_by_id(
                str(request.primary_admin_id)
            )
            if not admin or not admin.get("status"):
                raise HTTPException(
                    status_code=404,
                    detail="Primary admin not found or not active",
                )

            # Verify user has admin role
            if admin.get("role") not in ("admin", "primary_admin"):
                raise HTTPException(
                    status_code=400,
                    detail="User must have admin role to be primary admin",
                )

        estate_data = {
            "name": request.name,
            "location": request.location,
            "lga": request.lga,
            "state": request.state,
            "country": request.country,
            "postal_code": request.postal_code,
            "primary_admin_id": (
                str(request.primary_admin_id)
                if request.primary_admin_id
                else None
            ),
        }

        return await self.estate_repository.create_estate(estate_data)

    async def update_estate(
        self, estate_id: str, request: UpdateEstateRequest
    ) -> UpdateEstateResponse:
        """
        Updates an existing estate.

        Args:
            estate_id (str): The estate ID to update.
            request (UpdateEstateRequest): The update data.

        Returns:
            UpdateEstateResponse: Updated estate information.

        Raises:
            HTTPException: If estate not found or update fails.
        """
        # Check if estate exists
        existing_estate = await self.estate_repository.get_estate_by_id(
            estate_id
        )
        if not existing_estate or existing_estate.is_deleted:
            raise HTTPException(status_code=404, detail="Estate not found")

        # Validate primary admin if being updated
        if request.primary_admin_id:
            admin = await self.user_repository.get_user_by_id(
                str(request.primary_admin_id)
            )
            if not admin or not admin.status:
                raise HTTPException(
                    status_code=404,
                    detail="Primary admin not found or not active",
                )

            # Verify user has admin role
            if admin.role not in ("admin", "primary_admin"):
                raise HTTPException(
                    status_code=400,
                    detail="User must have admin role to be primary admin",
                )

        # Build update data (only include non-None fields)
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.location is not None:
            update_data["location"] = request.location
        if request.lga is not None:
            update_data["lga"] = request.lga
        if request.state is not None:
            update_data["state"] = request.state
        if request.country is not None:
            update_data["country"] = request.country
        if request.postal_code is not None:
            update_data["postal_code"] = request.postal_code
        if request.primary_admin_id is not None:
            update_data["primary_admin_id"] = str(request.primary_admin_id)

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_data = UpdateEstateRequest(**update_data)
        estate = await self.estate_repository.update_estate(
            estate_id, update_data
        )

        if not estate:
            raise HTTPException(
                status_code=400, detail="Failed to update estate"
            )

        return estate

    async def get_estate(self, estate_id: str) -> GetEstateResponse:
        """
        Retrieves an estate by ID.

        Args:
            estate_id (str): The estate ID to retrieve.

        Returns:
            GetEstateResponse: Estate information.

        Raises:
            HTTPException: If estate not found.
        """
        estate = await self.estate_repository.get_estate_by_id(estate_id)

        if not estate or estate.is_deleted:
            raise HTTPException(status_code=404, detail="Estate not found")

        return GetEstateResponse(
            id=estate.id,
            name=estate.name,
            location=estate.location,
            lga=estate.lga,
            state=estate.state,
            country=estate.country,
            postal_code=estate.postal_code,
            primary_admin_id=estate.primary_admin_id,
            created_at=estate.created_at,
            updated_at=estate.updated_at,
            is_deleted=estate.is_deleted,
        )

    async def delete_estate(self, estate_id: str) -> DeleteEstateResponse:
        """
        Soft deletes an estate.

        Args:
            estate_id (str): The estate ID to delete.

        Returns:
            DeleteEstateResponse: Deletion confirmation.

        Raises:
            HTTPException: If estate not found or already deleted.
        """
        # Check if estate exists and is not already deleted
        existing_estate = await self.estate_repository.get_estate_by_id(
            estate_id
        )
        if not existing_estate or existing_estate.is_deleted:
            raise HTTPException(status_code=404, detail="Estate not found")

        return await self.estate_repository.delete_estate(estate_id)

    async def search_estates(
        self, request: SearchEstateRequest
    ) -> ListEstateResponse:
        """
        Searches estates with filters and pagination.

        Args:
            request (SearchEstateRequest): Search parameters.

        Returns:
            ListEstateResponse: Search results with pagination.
        """
        # Convert datetime objects to ISO strings if present
        request.from_date = (
            request.from_date.isoformat() if request.from_date else None
        )
        request.to_date = (
            request.to_date.isoformat() if request.to_date else None
        )
        request.primary_admin_id = (
            str(request.primary_admin_id) if request.primary_admin_id else None
        )

        return await self.estate_repository.search_estates(request)

    async def list_estates(
        self, page: int = 1, limit: int = 10
    ) -> ListEstateResponse:
        """
        Lists all estates with pagination.

        Args:
            page (int): Page number for pagination.
            limit (int): Number of items per page.

        Returns:
            ListEstateResponse: Estate list with pagination.
        """
        request = SearchEstateRequest(page=page, limit=limit)
        return await self.search_estates(request)

    async def get_estates_by_admin(self, admin_id: str) -> ListEstateResponse:
        """
        Retrieves all estates where the user is the primary admin.

        Args:
            admin_id (str): The admin user ID.

        Returns:
            ListEstateResponse: List of estates managed by the admin.

        Raises:
            HTTPException: If admin not found.
        """
        # Validate admin exists
        admin = await self.user_repository.get_user_by_id(admin_id)
        if not admin or not admin.status:
            raise HTTPException(
                status_code=404, detail="Admin not found or not active"
            )

        request = SearchEstateRequest(primary_admin_id=admin_id)
        return await self.search_estates(request)

    async def get_estate_id_from_user_id(self, user_id: str) -> str:
        """
        Gets estate ID from user ID.

        Args:
            user_id (str): The user ID.

        Returns:
            str: The estate ID.

        Raises:
            HTTPException: If user not found.
        """
        user = await self.user_repository.get_user_by_id(user_id)
        if not user or not user.get("status"):
            raise HTTPException(status_code=404, detail="User not found")
        return user["estate_id"]

    async def validate_admin_access(
        self, admin_id: str, estate_id: str
    ) -> bool:
        """
        Validates if an admin has access to manage a specific estate.

        Args:
            admin_id (str): The admin user ID.
            estate_id (str): The estate ID.

        Returns:
            bool: True if admin has access, False otherwise.

        Raises:
            HTTPException: If admin or estate not found.
        """
        # Check if admin exists and is active
        admin = await self.user_repository.get_user_by_id(admin_id)
        if not admin or not admin.status:
            raise HTTPException(
                status_code=404, detail="Admin not found or not active"
            )

        # Check if admin has admin role
        if admin.role not in ("primary_admin"):
            return False

        # Check if estate exists
        estate = await self.estate_repository.get_estate_by_id(estate_id)
        if not estate or estate.is_deleted:
            raise HTTPException(status_code=404, detail="Estate not found")

        # For admin role, check if they are assigned to this estate
        # This checks if the admin is the primary admin of the estate
        if str(estate.primary_admin_id) == str(admin_id):
            return True

        return False

    async def check_estate_exists(self, estate_id: str) -> bool:
        """
        Checks if an estate exists and is not deleted.

        Args:
            estate_id (str): The estate ID to check.

        Returns:
            bool: True if estate exists and is active, False otherwise.
        """
        return await self.estate_repository.check_estate_exists(estate_id)

    async def transfer_primary_admin(
        self, estate_id: str, admin_id: str, requester_id: str
    ) -> UpdateEstateResponse:
        """
        Transfers the primary admin role from one admin to another.

        Args:
            estate_id (str): The estate ID.
            admin_id (str): The admin user ID to assign.
            requester_id (str): The user ID of the requester.
        """
        response = await self.assign_primary_admin(estate_id, admin_id)
        if not response:
            raise HTTPException(
                status_code=400, detail="Failed to transfer primary admin"
            )
        # Update the users role to primary_admin
        payload = UpdateUserRequest(
            role="primary_admin",
        )
        await self.user_repository.update_user(user_id=admin_id, data=payload)
        # Update the previous users role to admin
        payload = UpdateUserRequest(
            role="admin",
        )
        await self.user_repository.update_user(
            user_id=requester_id, data=payload
        )
        return response

    async def assign_primary_admin(
        self, estate_id: str, admin_id: str
    ) -> UpdateEstateResponse:
        """
        Assigns a primary admin to an estate.

        Args:
            estate_id (str): The estate ID.
            admin_id (str): The admin user ID to assign.

        Returns:
            UpdateEstateResponse: Updated estate information.

        Raises:
            HTTPException: If estate or admin not found.
        """
        request = UpdateEstateRequest(primary_admin_id=admin_id)
        return await self.update_estate(estate_id, request)

    async def deactivate_estate(
        self, estate_id: str, actor_user_id: str
    ) -> None:
        """
        Deactivates an estate (reversible). Sets is_active=False and records
        who deactivated it and when.

        Raises:
            HTTPException 404: Estate not found or deleted.
            HTTPException 400: Estate is already inactive.
        """
        estate = await self.estate_repository.get_estate_by_id(estate_id)
        if not estate or estate.is_deleted:
            raise HTTPException(status_code=404, detail="Estate not found.")
        if not estate.is_active:
            raise HTTPException(
                status_code=400, detail="Estate is already deactivated."
            )
        now = datetime.now(timezone.utc)
        await self.estate_repository.patch_estate(
            estate_id,
            {
                "is_active": False,
                "deactivated_by": actor_user_id,
                "deactivated_at": now.isoformat(),
            },
        )

    async def reactivate_estate(
        self, estate_id: str, actor_user_id: str
    ) -> None:
        """
        Reactivates a previously deactivated estate. Clears is_active=True
        and nulls deactivated_by / deactivated_at.

        Raises:
            HTTPException 404: Estate not found or deleted.
            HTTPException 400: Estate is already active.
        """
        estate = await self.estate_repository.get_estate_by_id(estate_id)
        if not estate or estate.is_deleted:
            raise HTTPException(status_code=404, detail="Estate not found.")
        if estate.is_active:
            raise HTTPException(
                status_code=400, detail="Estate is already active."
            )
        await self.estate_repository.patch_estate(
            estate_id,
            {
                "is_active": True,
                "deactivated_by": None,
                "deactivated_at": None,
            },
        )

    async def schedule_deactivate_estate(
        self,
        estate_id: str,
        actor_user_id: str,
        deactivate_at,
        schedule_repo,
    ) -> dict:
        """
        Validates and schedules an estate deactivation via Redis.

        Validates the estate exists and is currently active, then overwrites
        any existing scheduled entry for this estate.

        Args:
            estate_id: The ID of the estate to deactivate.
            actor_user_id: The ID of the root user scheduling the action.
            deactivate_at: The datetime at which to deactivate the estate.
            schedule_repo: The schedule repository instance.

        Returns:
            dict: Success message, deactivate_at_utc, and primary_admin_id.

        Raises:
            HTTPException 400: If deactivate_at is in the past or exceeds
                the maximum scheduling window.
            HTTPException 404: If the estate is not found.
        """
        import json
        from datetime import datetime, timedelta, timezone

        from app.core.config import settings
        from app.repositories.schedule import (
            SCHEDULED_ESTATE_DEACTIVATIONS_KEY,
        )

        estate = await self.estate_repository.get_estate_by_id(estate_id)
        if not estate or estate.is_deleted:
            raise HTTPException(status_code=404, detail="Estate not found.")

        deactivate_at_utc = (
            deactivate_at.replace(tzinfo=timezone.utc)
            if deactivate_at.tzinfo is None
            else deactivate_at.astimezone(timezone.utc)
        )
        now_utc = datetime.now(timezone.utc)
        if deactivate_at_utc <= now_utc:
            raise HTTPException(
                status_code=400,
                detail="deactivate_at must be in the future.",
            )
        max_days = settings.SCHEDULE_CLOSE_MAX_DAYS
        if deactivate_at_utc > now_utc + timedelta(days=max_days):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"deactivate_at cannot be more than {max_days} days"
                    " in the future."
                ),
            )

        await schedule_repo.remove_by_field(
            SCHEDULED_ESTATE_DEACTIVATIONS_KEY, "estate_id", estate_id
        )
        await schedule_repo.add(
            key=SCHEDULED_ESTATE_DEACTIVATIONS_KEY,
            score=deactivate_at_utc.timestamp(),
            member=json.dumps(
                {
                    "estate_id": estate_id,
                    "actor_user_id": actor_user_id,
                }
            ),
        )
        return {
            "success": True,
            "message": "Estate deactivation scheduled.",
            "deactivate_at": deactivate_at_utc,
            "primary_admin_id": (
                str(estate.primary_admin_id)
                if estate.primary_admin_id
                else None
            ),
        }

    async def cancel_scheduled_deactivation(
        self, estate_id: str, schedule_repo
    ) -> None:
        """
        Cancels a pending scheduled estate deactivation.

        Args:
            estate_id: The ID of the estate whose deactivation to cancel.
            schedule_repo: The schedule repository instance.

        Raises:
            HTTPException 404: If no scheduled deactivation exists.
        """
        from app.repositories.schedule import (
            SCHEDULED_ESTATE_DEACTIVATIONS_KEY,
        )

        removed = await schedule_repo.remove_by_field(
            SCHEDULED_ESTATE_DEACTIVATIONS_KEY, "estate_id", estate_id
        )
        if not removed:
            raise HTTPException(
                status_code=404,
                detail="No scheduled deactivation found for this estate.",
            )
