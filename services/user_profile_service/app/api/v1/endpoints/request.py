from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from app.schemas.request import (
    CreateEditRequestRequest,
    CreateEditRequestResponse,
    GetEditRequestResponse,
    ListEditRequestResponse,
    SearchEditRequestRequest,
    UpdateRequestStatusRequest,
    UpdateRequestStatusResponse,
    RequestType,
    RequestStatus,
)
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.libs.role_permissions import check_permission
from app.repositories.request import RequestRepository
from app.repositories.user import UserRepository
from app.services.request import RequestService
from app.services.auth import get_current_user

router = APIRouter()


@router.post("/edit", response_model=CreateEditRequestResponse)
async def create_edit_request(
    request: CreateEditRequestRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new edit request to change user profile details.
    Residents: Creates a pending request for admin approval.
    Admins: Auto-approves and applies change immediately.
    """
    user_id = current_user["id"]

    repository = RequestRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = RequestService(repository, user_repository)

    return await service.create_edit_request(request, user_id)


@router.get("/edit/me", response_model=ListEditRequestResponse)
async def get_my_requests(
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(
        10, ge=1, le=100, description="Number of items per page"
    ),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """
    Get all edit requests for the current user with pagination.
    """
    user_id = current_user["id"]

    repository = RequestRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = RequestService(repository, user_repository)

    return await service.list_my_requests(user_id, page, limit)


@router.get("/edit/{request_id}", response_model=GetEditRequestResponse)
async def get_request(
    request_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """
    Get details of a specific edit request by ID.
    Residents can only view their own requests.
    Admins can view all requests in their estate.
    """
    user_id = current_user["id"]
    user_role = current_user["role"]

    repository = RequestRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = RequestService(repository, user_repository)

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
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
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

    repository = RequestRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = RequestService(repository, user_repository)

    return await service.search_requests(search_request, user_id, user_role)


@router.patch(
    "/edit/{request_id}/status", response_model=UpdateRequestStatusResponse
)
async def update_request_status(
    request_id: str,
    request: UpdateRequestStatusRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
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

    repository = RequestRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = RequestService(repository, user_repository)

    return await service.update_request_status(
        request_id, request, reviewer_id, reviewer_role
    )
