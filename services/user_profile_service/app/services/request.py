from fastapi import HTTPException

from app.schemas.request import (
    CreateEditRequestRequest,
    CreateEditRequestResponse,
    GetEditRequestResponse,
    ListEditRequestResponse,
    SearchEditRequestRequest,
    UpdateRequestStatusRequest,
    UpdateRequestStatusResponse,
    UpdatePendingRequestRequest,
    UpdatePendingRequestResponse,
    DeletePendingRequestResponse,
    RequestType,
    RequestStatus,
)
from app.repositories.request import RequestRepository
from app.repositories.user import UserRepository
from app.repositories.user_documents import UserDocumentsRepository


class RequestService:
    """
    Service layer for handling edit request management and related logic.

    Methods:
        create_edit_request: Creates a new edit request or
        auto-approves for admins.
        get_request: Retrieves a request by ID.
        search_requests: Searches requests with filters and pagination.
        update_request_status: Approves or rejects a request.
        list_my_requests: Lists requests for the current user.
    """

    def __init__(
        self,
        repository: RequestRepository,
        user_repository: UserRepository,
        documents_repository: UserDocumentsRepository | None = None,
    ):
        self.repository = repository
        self.user_repository = user_repository
        self.documents_repository = documents_repository

    async def create_edit_request(
        self, request: CreateEditRequestRequest, user_id: str
    ) -> CreateEditRequestResponse:
        """
        Handles edit request creation flow.
        For admins/primary_admins: auto-approves and
        applies change immediately.
        For residents: creates pending request for admin approval.

        Args:
            request: The incoming edit request data.
            user_id: ID of the user making the request.

        Returns:
            CreateEditRequestResponse: Created request information.

        Raises:
            HTTPException: If creation fails or user not found.
        """
        user = await self.user_repository.get_user_by_id(user_id)
        if not user or user.is_deleted or not user.status:
            raise HTTPException(status_code=404, detail="User not found")

        if request.request_type == RequestType.ID_CHANGE:
            raise HTTPException(
                status_code=400,
                detail=(
                    "ID changes are submitted by uploading an ID card document"
                ),
            )

        request_type_value = request.request_type.value
        old_value = self._get_current_value(user, request.request_type)
        new_value = request.new_value
        estate_id = str(user.estate_id)

        # Check if admin or primary_admin
        is_admin = user.role in ("admin", "primary_admin")

        # For non-admin users, check if there's already a pending request
        # for this field type
        if not is_admin:
            existing_pending = (
                await self.repository.get_pending_request_by_type(
                    resident_id=user_id, request_type=request_type_value
                )
            )

            if existing_pending:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"You already have a pending request to"
                        f" change your "
                        f"{request.request_type.value.replace('_', ' ')}",
                        "existing_request_id": str(existing_pending.id),
                        "existing_request_created_at": existing_pending.created_at.isoformat(),
                        "existing_new_value": existing_pending.new_value,
                    },
                )

        if is_admin:
            # Auto-approve and apply change immediately
            status = RequestStatus.APPROVED
            reviewed_by = user_id

            # Apply the change to the user profile
            await self._apply_profile_change(
                user_id, request.request_type, new_value
            )
        else:
            # Create pending request for resident
            status = RequestStatus.PENDING
            reviewed_by = None

        # Create the request record in the database
        edit_request = await self.repository.create_request(
            resident_id=user_id,
            estate_id=estate_id,
            request_type=request_type_value,
            old_value=old_value,
            new_value=new_value,
            status=status.value,
            reviewed_by=reviewed_by,
        )

        return edit_request

    async def create_id_change_request(
        self,
        user_id: str,
        estate_id: str,
        pending_document_id: str,
    ) -> CreateEditRequestResponse:
        """
        Create a pending ID change request for a newly uploaded pending ID card.

        ``old_value`` is the active ID document row ID, or empty on first upload.
        ``new_value`` is the pending document row ID awaiting admin approval.
        """
        if self.documents_repository is None:
            raise HTTPException(
                status_code=500,
                detail="Document repository not configured",
            )

        await self._validate_id_change_document(
            pending_document_id, user_id, require_pending=True
        )

        existing_pending = await self.repository.get_pending_request_by_type(
            resident_id=user_id,
            request_type=RequestType.ID_CHANGE.value,
        )
        if existing_pending:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "You already have a pending ID change request",
                    "existing_request_id": str(existing_pending.id),
                    "existing_request_created_at": (
                        existing_pending.created_at.isoformat()
                    ),
                    "existing_new_value": existing_pending.new_value,
                },
            )

        active = await self.documents_repository.get_active_by_user_and_type(
            user_id, "id_card"
        )
        old_value = str(active["id"]) if active else ""

        return await self.repository.create_request(
            resident_id=user_id,
            estate_id=estate_id,
            request_type=RequestType.ID_CHANGE.value,
            old_value=old_value,
            new_value=pending_document_id,
            status=RequestStatus.PENDING.value,
            reviewed_by=None,
        )

    async def get_request(
        self, request_id: str, user_id: str, user_role: str
    ) -> GetEditRequestResponse:
        """
        Retrieves a request by ID with authorization check.

        Args:
            request_id: The request ID to retrieve.
            user_id: ID of the user requesting access.
            user_role: Role of the user requesting access.

        Returns:
            GetEditRequestResponse: Request information.

        Raises:
            HTTPException: If request not found or unauthorized.
        """
        edit_request = await self.repository.get_request_by_id(request_id)

        if not edit_request or edit_request.is_deleted:
            raise HTTPException(status_code=404, detail="Request not found")

        # Authorization: user can only view their own requests unless admin
        if user_role not in ("admin", "primary_admin", "root"):
            if str(edit_request.resident_id) != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to view this request",
                )

        return edit_request

    async def search_requests(
        self,
        search_request: SearchEditRequestRequest,
        user_id: str,
        user_role: str,
    ) -> ListEditRequestResponse:
        """
        Searches requests with filters and pagination.
        Residents can only see their own requests.
        Admins can see all requests in their estate.

        Args:
            search_request: Search parameters.
            user_id: ID of the user performing search.
            user_role: Role of the user performing search.

        Returns:
            ListEditRequestResponse: Search results with pagination.

        Raises:
            HTTPException: If user not found.
        """
        # Get user's estate for filtering
        user = await self.user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # For residents, filter to only their requests
        if user_role not in ("admin", "primary_admin", "root"):
            search_request.resident_id = user.id
            search_request.estate_id = user.estate_id
        else:
            # For admins, filter to their estate if not root
            if user_role != "root":
                search_request.estate_id = user.estate_id

        return await self.repository.search_requests(search_request)

    async def update_request_status(
        self,
        request_id: str,
        status_request: UpdateRequestStatusRequest,
        reviewer_id: str,
        reviewer_role: str,
    ) -> UpdateRequestStatusResponse:
        """
        Approves or rejects a pending edit request.
        Only admins can approve/reject requests.
        If approved, applies the change to user profile.

        Args:
            request_id: The request ID to update.
            status_request: New status (approved/rejected).
            reviewer_id: ID of the admin reviewing.
            reviewer_role: Role of the reviewer.

        Returns:
            UpdateRequestStatusResponse: Updated request information.

        Raises:
            HTTPException: If not authorized, request not found,
            or update fails.
        """
        # Check authorization
        if reviewer_role not in ("admin", "primary_admin"):
            raise HTTPException(
                status_code=403,
                detail="Only admins can approve/reject requests",
            )

        # Get the request
        edit_request = await self.repository.get_request_by_id(request_id)
        if not edit_request or edit_request.is_deleted:
            raise HTTPException(status_code=404, detail="Request not found")

        # Check if request is already processed
        if edit_request.status != RequestStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=f"Request already {edit_request.status.value}",
            )

        # Verify reviewer is in same estate as requester
        reviewer = await self.user_repository.get_user_by_id(reviewer_id)
        if not reviewer:
            raise HTTPException(status_code=404, detail="Reviewer not found")

        if str(reviewer.estate_id) != str(edit_request.estate_id):
            raise HTTPException(
                status_code=403,
                detail="Cannot review requests from other estates",
            )

        # On approval, apply the side effect (ID document promotion or profile
        # change) BEFORE flipping the request status. If it fails, the request
        # stays pending and the error propagates, keeping the two in sync.
        if status_request.status == RequestStatus.APPROVED:
            request_type = RequestType(edit_request.request_type)
            if request_type == RequestType.ID_CHANGE:
                await self._approve_id_change_document(
                    reviewer_id=reviewer_id,
                    reviewer_role=reviewer_role,
                    pending_document_id=edit_request.new_value or "",
                    resident_id=str(edit_request.resident_id),
                )
            else:
                await self._apply_profile_change(
                    str(edit_request.resident_id),
                    request_type,
                    edit_request.new_value,
                )

        # Update the request status only after the side effect succeeded.
        updated_request = await self.repository.update_request_status(
            request_id=request_id,
            status=status_request.status,
            reviewed_by=reviewer_id,
        )

        return updated_request

    async def list_my_requests(
        self, user_id: str, page: int = 1, limit: int = 10
    ) -> ListEditRequestResponse:
        """
        Lists all requests for the current user with pagination.

        Args:
            user_id: ID of the user.
            page: Page number for pagination.
            limit: Number of items per page.

        Returns:
            ListEditRequestResponse: User's request list with pagination.
        """
        search_request = SearchEditRequestRequest(
            resident_id=user_id, page=page, limit=limit
        )
        return await self.repository.search_requests(search_request)

    async def check_pending_request(
        self, user_id: str, request_type: RequestType
    ) -> GetEditRequestResponse | None:
        """
        Checks if user has a pending request for specific field.

        Args:
            user_id: ID of the user.
            request_type: Type of field to check.

        Returns:
            GetEditRequestResponse if pending request exists, None.
        """
        return await self.repository.get_pending_request_by_type(
            resident_id=user_id, request_type=request_type.value
        )

    async def update_pending_request(
        self,
        request_id: str,
        update_data: UpdatePendingRequestRequest,
        user_id: str,
    ) -> UpdatePendingRequestResponse:
        """
        Updates a pending request's new value.
        Users can only update their own pending requests.

        Args:
            request_id: ID of the request to update.
            update_data: New value data.
            user_id: ID of the user making the update.

        Returns:
            UpdatePendingRequestResponse: Updated request info.

        Raises:
            HTTPException: If request not found, not authorized,
                or not pending.
        """
        # Get the request
        edit_request = await self.repository.get_request_by_id(request_id)
        if not edit_request or edit_request.is_deleted:
            raise HTTPException(status_code=404, detail="Request not found")

        # Check authorization: user can only update own requests
        if str(edit_request.resident_id) != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only update your own requests",
            )

        # Check if request is still pending
        if edit_request.status != RequestStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot update request that is already "
                    f"{edit_request.status.value}"
                ),
            )

        # Validate the new value for the request type
        request_type = RequestType(edit_request.request_type)
        await self._validate_new_value(
            request_type, update_data.new_value, user_id
        )

        if request_type == RequestType.ID_CHANGE:
            await self._validate_id_change_document(
                update_data.new_value, user_id, require_pending=True
            )
            if edit_request.new_value:
                await self._archive_id_change_pending(
                    edit_request.new_value, user_id
                )

        # Update the request
        return await self.repository.update_pending_request_value(
            request_id=request_id, new_value=update_data.new_value
        )

    async def delete_pending_request(
        self, request_id: str, user_id: str
    ) -> DeletePendingRequestResponse:
        """
        Deletes (cancels) a pending request.
        Users can only delete their own pending requests.

        Args:
            request_id: ID of the request to delete.
            user_id: ID of the user making the deletion.

        Returns:
            DeletePendingRequestResponse: Deletion confirmation.

        Raises:
            HTTPException: If request not found, not authorized,
                or not pending.
        """
        # Get the request
        edit_request = await self.repository.get_request_by_id(request_id)
        if not edit_request or edit_request.is_deleted:
            raise HTTPException(status_code=404, detail="Request not found")

        # Check authorization: user can only delete own requests
        if str(edit_request.resident_id) != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own requests",
            )

        # Check if request is still pending
        if edit_request.status != RequestStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot delete request that is already "
                    f"{edit_request.status.value}"
                ),
            )

        request_type = RequestType(edit_request.request_type)
        if request_type == RequestType.ID_CHANGE and edit_request.new_value:
            await self._archive_id_change_pending(
                edit_request.new_value, user_id
            )

        # Delete the request
        return await self.repository.delete_pending_request(request_id)

    def _get_current_value(self, user, request_type: RequestType) -> str:
        """
        Gets the current value of the field being requested to change.

        Args:
            user: User object.
            request_type: Type of field.

        Returns:
            Current value as string.
        """
        field_map = {
            RequestType.FIRST_NAME_CHANGE: user.first_name,
            RequestType.LAST_NAME_CHANGE: user.last_name,
            RequestType.HOME_ADDRESS_CHANGE: user.home_address,
            RequestType.EMAIL_CHANGE: user.email,
            RequestType.GENDER_CHANGE: user.gender,
            RequestType.ID_CHANGE: "",
        }
        return str(field_map.get(request_type, ""))

    async def _validate_new_value(
        self,
        request_type: RequestType,
        new_value: str,
        user_id: str,
    ):
        """
        Validates the new value for a request type.

        Args:
            request_type: Type of field to change.
            new_value: New value to validate.
            user_id: ID of the user.

        Raises:
            HTTPException: If validation fails.
        """
        # For email changes, check if email already exists
        if request_type == RequestType.EMAIL_CHANGE:
            existing_user = await self.user_repository.get_user_by_email(
                new_value
            )
            if existing_user and str(existing_user.id) != user_id:
                raise HTTPException(
                    status_code=400, detail="Email already in use"
                )

        if request_type == RequestType.ID_CHANGE:
            await self._validate_id_change_document(
                new_value, user_id, require_pending=True
            )

    async def _validate_id_change_document(
        self,
        document_id: str,
        user_id: str,
        *,
        require_pending: bool,
    ) -> dict:
        """Ensure a document row belongs to the user and is a pending ID card."""
        if self.documents_repository is None:
            raise HTTPException(
                status_code=500,
                detail="Document repository not configured",
            )

        doc_meta = await self.documents_repository.get_by_id(document_id)
        if str(doc_meta.get("user_id")) != user_id:
            raise HTTPException(
                status_code=403,
                detail="Document does not belong to this user",
            )
        if doc_meta.get("document_type") != "id_card":
            raise HTTPException(
                status_code=400,
                detail="ID change requests must reference an ID card document",
            )
        status = doc_meta.get("document_status")
        if require_pending and status != "pending":
            raise HTTPException(
                status_code=400,
                detail="ID change requests must reference a pending document",
            )
        return doc_meta

    async def _archive_id_change_pending(
        self, document_id: str, user_id: str
    ) -> None:
        """Archive a pending ID card document without moving it from temp."""
        if self.documents_repository is None:
            raise HTTPException(
                status_code=500,
                detail="Document repository not configured",
            )

        doc_meta = await self.documents_repository.get_by_id(document_id)
        if str(doc_meta.get("user_id")) != user_id:
            raise HTTPException(
                status_code=403,
                detail="Document does not belong to this user",
            )
        if doc_meta.get("document_type") != "id_card":
            raise HTTPException(
                status_code=400,
                detail="ID change requests must reference an ID card document",
            )
        if doc_meta.get("document_status") != "pending":
            return
        await self.documents_repository.archive_pending(document_id)

    async def _approve_id_change_document(
        self,
        *,
        reviewer_id: str,
        reviewer_role: str,
        pending_document_id: str,
        resident_id: str,
    ) -> None:
        """Promote the pending ID card referenced by an approved request."""
        if self.documents_repository is None:
            raise HTTPException(
                status_code=500,
                detail="Document repository not configured",
            )

        await self._validate_id_change_document(
            pending_document_id, resident_id, require_pending=True
        )

        reviewer = await self.user_repository.get_user_by_id(reviewer_id)
        if reviewer is None:
            raise HTTPException(status_code=404, detail="Reviewer not found")

        if reviewer_role != "root":
            target_user = await self.user_repository.get_user_by_id(
                resident_id
            )
            if target_user is None or target_user.is_deleted:
                raise HTTPException(
                    status_code=404, detail="Target User not found"
                )
            if str(target_user.estate_id) != str(reviewer.estate_id):
                raise HTTPException(
                    status_code=403,
                    detail="Cannot approve documents from other estates",
                )

        await self.documents_repository.approve(pending_document_id)

    async def _apply_profile_change(
        self, user_id: str, request_type: RequestType, new_value: str
    ):
        """
        Applies the approved change to user profile via repository.

        Args:
            user_id: ID of the user.
            request_type: Type of field to change.
            new_value: New value to set.

        Raises:
            HTTPException: If update fails.
        """
        # Validate the new value
        await self._validate_new_value(request_type, new_value, user_id)

        # Map request type to field name
        field_map = {
            RequestType.FIRST_NAME_CHANGE: "first_name",
            RequestType.LAST_NAME_CHANGE: "last_name",
            RequestType.HOME_ADDRESS_CHANGE: "home_address",
            RequestType.EMAIL_CHANGE: "email",
            RequestType.GENDER_CHANGE: "gender",
        }

        field_name = field_map.get(request_type)
        if not field_name:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid request type: {request_type}",
            )
        await self.user_repository.update_user_field(
            user_id, field_name, new_value
        )
