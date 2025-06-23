from app.schemas.estate import (
    RegisterEstateRequest,
    RegisterEstateResponse,
    UpdateEstateRequest,
    UpdateEstateResponse,
    GetEstateResponse,
    DeleteEstateResponse,
    SearchEstateRequest,
    ListEstateResponse,
)
from app.schemas.user import UpdateUserRequest
from app.repositories.estate import EstateRepository
from app.repositories.user import UserRepository
from fastapi import HTTPException


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
        if not existing_estate or existing_estate.get("is_deleted"):
            raise HTTPException(status_code=404, detail="Estate not found")

        # Validate primary admin if being updated
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

        # Build update data (only include non-None fields)
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.location is not None:
            update_data["location"] = request.location
        if request.primary_admin_id is not None:
            update_data["primary_admin_id"] = str(request.primary_admin_id)

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        estate = await self.estate_repository.update_estate(
            estate_id, update_data
        )

        if not estate:
            raise HTTPException(
                status_code=400, detail="Failed to update estate"
            )

        return UpdateEstateResponse(
            id=estate["id"],
            created_at=estate["created_at"],
            updated_at=estate["updated_at"],
        )

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

        if not estate or estate.get("is_deleted"):
            raise HTTPException(status_code=404, detail="Estate not found")

        return GetEstateResponse(
            id=estate["id"],
            name=estate["name"],
            location=estate["location"],
            primary_admin_id=estate.get("primary_admin_id"),
            created_at=estate["created_at"],
            updated_at=estate.get("updated_at"),
            is_deleted=estate.get("is_deleted", False),
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
        if not existing_estate or existing_estate.get("is_deleted"):
            raise HTTPException(status_code=404, detail="Estate not found")

        result = await self.estate_repository.delete_estate(estate_id)

        return DeleteEstateResponse(
            is_deleted=result["is_deleted"],
            deleted_at=result["deleted_at"],
        )

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
        if not admin or not admin.get("status"):
            raise HTTPException(
                status_code=404, detail="Admin not found or not active"
            )

        # Check if admin has admin role
        if admin.get("role") not in ("primary_admin"):
            return False

        # Check if estate exists
        estate = await self.estate_repository.get_estate_by_id(estate_id)
        if not estate or estate.get("is_deleted"):
            raise HTTPException(status_code=404, detail="Estate not found")

        # For admin role, check if they are assigned to this estate
        # This checks if the admin is the primary admin of the estate
        if estate.get("primary_admin_id") == admin_id:
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
