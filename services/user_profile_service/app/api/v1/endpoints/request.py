from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.libs.notify import fire_notify

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
    CheckPendingRequestResponse,
    RemindAdminsResponse,
    RequestType,
    RequestStatus,
)
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.libs.role_permissions import check_permission
from app.repositories.request import RequestRepository
from app.repositories.user import UserRepository
from app.repositories.user_documents import UserDocumentsRepository
from app.services.request import RequestService
from app.services.auth import get_current_user

router = APIRouter()


def get_request_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> RequestService:
    """Return RequestService wired to db-service repositories."""
    return RequestService(
        RequestRepository(ahttp_client),
        UserRepository(ahttp_client),
        UserDocumentsRepository(ahttp_client),
    )


@router.post("/edit", response_model=CreateEditRequestResponse)
async def create_edit_request(
    request: CreateEditRequestRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Create a new edit request to change user profile details.
    Residents: Creates a pending request for admin approval.
    Admins: Auto-approves and applies change immediately.
    """
    user_id = current_user["id"]
    user_role = current_user["role"]

    result = await service.create_edit_request(request, user_id)

    # Notify estate admins when a resident files a pending request
    if user_role == "resident":
        estate_id = current_user.get("estate_id")
        if estate_id:
            background_tasks.add_task(
                fire_notify,
                {
                    "type": "EDIT_REQUEST_PENDING",
                    "title": "New edit request",
                    "body": "A resident has submitted a profile edit request.",
                    "fan_out": {
                        "estate_id": estate_id,
                        "roles": ["admin", "primary_admin"],
                    },
                    "metadata": {
                        "request_id": str(result.id),
                        "request_type": request.request_type.value
                        if hasattr(request.request_type, "value")
                        else str(request.request_type),
                        "requester_name": user_id,
                    },
                },
            )

    return result


@router.get("/edit/me", response_model=ListEditRequestResponse)
async def get_my_requests(
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(
        10, ge=1, le=100, description="Number of items per page"
    ),
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Get all edit requests for the current user with pagination.
    """
    user_id = current_user["id"]

    return await service.list_my_requests(user_id, page, limit)


@router.get("/edit/{request_id}", response_model=GetEditRequestResponse)
async def get_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Get details of a specific edit request by ID.
    Residents can only view their own requests.
    Admins can view all requests in their estate.
    """
    user_id = current_user["id"]
    user_role = current_user["role"]

    return await service.get_request(request_id, user_id, user_role)


@router.get("/edit", response_model=ListEditRequestResponse)
async def search_requests(
    request_type: Optional[RequestType] = Query(
        None, description="Filter by request type"
    ),
    status: Optional[RequestStatus] = Query(
        None, description="Filter by request status"
    ),
    resident_id: Optional[str] = Query(
        None, description="Filter by resident ID (admin only)"
    ),
    from_date: Optional[str] = Query(
        None, description="Filter by creation date (from) - ISO format"
    ),
    to_date: Optional[str] = Query(
        None, description="Filter by creation date (to) - ISO format"
    ),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(
        10, ge=1, le=100, description="Number of items per page"
    ),
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Search and list edit requests with optional filters and pagination.
    Residents can only see their own requests.
    Admins can see all requests in their estate.
    """
    user_id = current_user["id"]
    user_role = current_user["role"]

    # Parse datetime strings if provided
    from_date_obj = None
    to_date_obj = None

    if from_date:
        try:
            from datetime import datetime

            from_date_obj = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid from_date format. Use ISO format.",
            )

    if to_date:
        try:
            from datetime import datetime

            to_date_obj = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid to_date format. Use ISO format.",
            )

    # Build search request
    search_request = SearchEditRequestRequest(
        request_type=request_type,
        status=status,
        resident_id=resident_id,
        from_date=from_date_obj,
        to_date=to_date_obj,
        page=page,
        limit=limit,
    )

    return await service.search_requests(search_request, user_id, user_role)


@router.get("/edit/pending/check", response_model=CheckPendingRequestResponse)
async def check_pending_request(
    request_type: RequestType = Query(
        ..., description="Type of field to check for pending request"
    ),
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Check if the current user has a pending request for a specific field type.
    This helps the frontend prevent duplicate requests and show appropriate UI.
    """
    user_id = current_user["id"]

    pending_request = await service.check_pending_request(
        user_id, request_type
    )

    return CheckPendingRequestResponse(
        has_pending_request=pending_request is not None,
        pending_request=pending_request,
    )


@router.patch(
    "/edit/{request_id}", response_model=UpdatePendingRequestResponse
)
async def update_pending_request(
    request_id: str,
    request: UpdatePendingRequestRequest,
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Update the new_value of a pending request.
    Users can only update their own pending requests.
    Request must still be in PENDING status.
    """
    user_id = current_user["id"]

    return await service.update_pending_request(request_id, request, user_id)


@router.delete(
    "/edit/{request_id}", response_model=DeletePendingRequestResponse
)
async def delete_pending_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Cancel (delete) a pending request.
    Users can only delete their own pending requests.
    Request must still be in PENDING status.
    """
    user_id = current_user["id"]

    return await service.delete_pending_request(request_id, user_id)


@router.post("/edit/{request_id}/remind", response_model=RemindAdminsResponse)
async def remind_admins(
    request_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Send a reminder to estate admins about a pending edit request.
    Rate-limited by EDIT_REQUEST_REMIND_COOLDOWN_HOURS (default 24 h).
    Cooldown starts from request creation, not from first reminder.
    """
    user_id = current_user["id"]
    result = await service.remind_admins(request_id, user_id)

    estate_id = current_user.get("estate_id")
    if estate_id:
        background_tasks.add_task(
            fire_notify,
            {
                "type": "EDIT_REQUEST_PENDING",
                "title": "Edit request reminder",
                "body": (
                    "A resident is following up on a pending "
                    "profile edit request."
                ),
                "fan_out": {
                    "estate_id": estate_id,
                    "roles": ["admin", "primary_admin"],
                },
                "metadata": {"request_id": request_id},
            },
        )

    return result


@router.patch(
    "/edit/{request_id}/status", response_model=UpdateRequestStatusResponse
)
async def update_request_status(
    request_id: str,
    request: UpdateRequestStatusRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
    service: RequestService = Depends(get_request_service),
):
    """
    Approve or reject a pending edit request.
    Only admins and primary_admins can perform this action.
    If approved, the change is automatically applied to the user's profile.
    """
    reviewer_id = current_user["id"]
    reviewer_role = current_user["role"]

    # Check permission
    if not await check_permission(
        ahttp_client, reviewer_role, "can_register_users"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to review requests.",
        )

    edit_request = await service.repository.get_request_by_id(request_id)

    result = await service.update_request_status(
        request_id, request, reviewer_id, reviewer_role
    )

    if edit_request:
        resident_id = str(edit_request.resident_id)
        review_status = (
            request.status.value
            if hasattr(request.status, "value")
            else str(request.status)
        )
        request_type = (
            edit_request.request_type.value
            if hasattr(edit_request.request_type, "value")
            else str(edit_request.request_type)
        )
        background_tasks.add_task(
            fire_notify,
            {
                "type": "EDIT_REQUEST_REVIEWED",
                "title": "Edit request reviewed",
                "body": (
                    f"Your profile edit request has been {review_status}."
                ),
                "recipient_user_ids": [resident_id],
                "metadata": {
                    "request_id": request_id,
                    "request_type": request_type,
                    "review_status": review_status,
                },
            },
        )

    return result
