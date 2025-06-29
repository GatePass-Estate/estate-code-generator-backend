from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
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
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.libs.role_permissions import check_permission
from app.repositories.estate import EstateRepository
from app.repositories.user import UserRepository
from app.repositories.admin_management import AdminRepository
from app.services.estate import EstateService
from app.services.admin_management import AdminManagementService
from app.services.auth import get_current_user

router = APIRouter()


@router.post("/register", response_model=RegisterEstateResponse)
async def register_estate(
    request: RegisterEstateRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Register a new estate."""
    requester_role = current_user["role"]

    # Check permission to register estates
    if not await check_permission(
        ahttp_client, requester_role, "can_register_estates"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to register estates.",
        )

    # Proceed with estate creation
    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

    return await service.register_estate(request)


@router.get("/", response_model=ListEstateResponse)
async def list_estates(
    name: Optional[str] = Query(
        None, description="Filter by estate name (partial match)"
    ),
    location: Optional[str] = Query(
        None, description="Filter by estate location (partial match)"
    ),
    primary_admin_id: Optional[str] = Query(
        None, description="Filter by primary admin ID"
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
    """Search and list estates with optional filters and pagination."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_estates"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view estates."
        )

    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

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
    # Root can search all estates
    request = SearchEstateRequest(
        name=name,
        location=location,
        primary_admin_id=primary_admin_id,
        from_date=from_date_obj,
        to_date=to_date_obj,
        page=page,
        limit=limit,
    )

    return await service.search_estates(request)


@router.get("/admin/{admin_id}", response_model=ListEstateResponse)
async def get_estates_by_admin(
    admin_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Get all estates managed by a specific admin."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_estates"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to view estates."
        )

    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

    return await service.get_estates_by_admin(admin_id)


@router.get("/my/estates", response_model=ListEstateResponse)
async def get_my_estates(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Get all estates managed by the current user."""

    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

    user_id = current_user["id"]
    return await service.get_estates_by_admin(user_id)


@router.post("/{estate_id}/assign/admin", response_model=UpdateEstateResponse)
async def assign_primary_admin(
    estate_id: str,
    admin_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Assign a primary admin to an estate."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_transfer_admin"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to assign admins."
        )

    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)
    admin_service = AdminManagementService(admin_repository)

    # Validate admin access unless root user
    requester_id = current_user["id"]
    if requester_role != "root":
        has_access = await service.validate_admin_access(
            requester_id, estate_id
        )
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to modify this estate.",
            )

    response = await admin_service.get_admin_from_user_id(admin_id)
    if not response:
        raise HTTPException(
            status_code=404, detail="New Primary Admin must be an admin."
        )
    response = await service.transfer_primary_admin(
        estate_id, admin_id, requester_id
    )
    await admin_service.transfer_admin_records(estate_id, admin_id)

    return response


@router.get("/{estate_id}", response_model=GetEstateResponse)
async def get_estate(
    estate_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Get estate details by ID."""
    requester_role = current_user["role"]

    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

    # Validate admin access unless root user
    if requester_role != "root":
        user_id = current_user["id"]
        has_access = await service.validate_admin_access(user_id, estate_id)
        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="You are not authorized to view this estate.",
            )

    return await service.get_estate(estate_id)


@router.patch("/{estate_id}", response_model=UpdateEstateResponse)
async def update_estate(
    estate_id: str,
    request: UpdateEstateRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Update an existing estate."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_estates"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to update estates."
        )

    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

    return await service.update_estate(estate_id, request)


@router.delete("/{estate_id}", response_model=DeleteEstateResponse)
async def delete_estate(
    estate_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
):
    """Soft delete an estate."""
    requester_role = current_user["role"]

    if not await check_permission(
        ahttp_client, requester_role, "can_register_estates"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to delete estates."
        )

    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

    return await service.delete_estate(estate_id)
