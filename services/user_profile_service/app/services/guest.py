from app.schemas.guest import (
    RegisterGuestRequest,
    RegisterGuestResponse,
    UpdateGuestRequest,
    UpdateGuestResponse,
    GetGuestResponse,
    DeleteGuestResponse,
    SearchGuestRequest,
    ListGuestResponse,
)
from app.repositories.guest import GuestRepository
from fastapi import HTTPException


class GuestService:
    """
    Service layer for handling guest management and related logic.

    Methods:
        register_guest: Registers a new guest.
        update_guest: Updates an existing guest.
        get_guest: Retrieves a guest by ID.
        delete_guest: Soft deletes a guest.
        search_guests: Searches guests with filters and pagination.
    """

    def __init__(
        self,
        repository: GuestRepository,
    ):
        self.repository = repository

    async def register_guest(
        self, request: RegisterGuestRequest
    ) -> RegisterGuestResponse:
        """
        Handles guest registration flow.

        Args:
            request: The incoming guest registration data.

        Returns:
            Tuple containing:
                - RegisterGuestResponse: Registered guest information

        Raises:
            HTTPException: If registration fails or email exists.
        """
        # Create user through repository
        guest = await self.repository.create_guest(request)

        return guest

    async def update_guest(
        self, guest_id: str, requester_id: str, request: UpdateGuestRequest
    ) -> UpdateGuestResponse:
        """
        Updates an existing guest.

        Args:
            guest_id: The guest ID to update.
            request: The update data.

        Returns:
            UpdateGuestResponse: Updated guest information.

        Raises:
            HTTPException: If guest not found or update fails.
        """
        # Check if user exists
        existing_guest = await self.repository.get_guest_by_id(guest_id)
        if not existing_guest or existing_guest.is_deleted:
            raise HTTPException(status_code=404, detail="Guest not found")

        if str(existing_guest.resident_id) != requester_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this guest"
            )

        # Check if any fields are being updated
        if all(
            field is None
            for field in [
                request.guest_name,
                request.guest_gender,
                request.relationship,
                request.guest_phone_number,
            ]
        ):
            raise HTTPException(status_code=400, detail="No fields to update")

        return await self.repository.update_guest(guest_id, request)

    async def get_guest(
        self, guest_id: str, resident_id: str
    ) -> GetGuestResponse:
        """
        Retrieves a guest by ID.

        Args:
            guest_id: The guest ID to retrieve.

        Returns:
            GetGuestResponse: Guest information.

        Raises:
            HTTPException: If guest not found.
        """
        guest = await self.repository.get_guest_by_id(guest_id)

        if not guest or guest.is_deleted:
            raise HTTPException(status_code=404, detail="guest not found")

        if str(guest.resident_id) != resident_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return guest

    async def delete_guest(
        self, guest_id: str, requester_id: str
    ) -> DeleteGuestResponse:
        """
        Soft deletes a guest.

        Args:
            guest_id: The guest ID to delete.

        Returns:
            DeleteGuestResponse: Deletion confirmation.

        Raises:
            HTTPException: If guest not found or already deleted.
        """
        # Check if guest exists and is not already deleted
        existing_guest = await self.repository.get_guest_by_id(guest_id)
        if not existing_guest or existing_guest.is_deleted:
            raise HTTPException(status_code=404, detail="guest not found")

        if str(existing_guest.resident_id) != requester_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this guest"
            )

        return await self.repository.delete_guest(guest_id)

    async def search_guests(
        self, request: SearchGuestRequest, resident_id: str
    ) -> ListGuestResponse:
        """
        Searches guests with filters and pagination.

        Args:
            request: Search parameters.

        Returns:
            ListUserResponse: Search results with pagination.
        """
        return await self.repository.search_guests(request, resident_id)

    async def list_guests(
        self, page: int = 1, limit: int = 10
    ) -> ListGuestResponse:
        """
        Lists all guests with pagination.

        Args:
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            ListGuestResponse: Guest list with pagination.
        """
        request = SearchGuestRequest(page=page, limit=limit)
        return await self.repository.search_guests(request)
