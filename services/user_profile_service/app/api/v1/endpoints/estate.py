from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_notify
from app.libs.role_permissions import check_permission
from app.repositories.admin_management import AdminRepository
from app.repositories.estate import EstateRepository
from app.repositories.schedule import ScheduleRepository as ScheduleRepo
from app.repositories.user import UserRepository
from app.schemas.estate import (
    DeactivateEstateRequest,
    DeleteEstateResponse,
    EstateType,
    GetEstateResponse,
    ListEstateResponse,
    PublicEstateListResponse,
    PublicEstateSearchResponse,
    RegisterEstateRequest,
    RegisterEstateResponse,
    SearchEstateRequest,
    UpdateEstateRequest,
    UpdateEstateResponse,
)
from app.services.admin_management import AdminManagementService
from app.services.auth import get_current_user
from app.services.estate import EstateService

router = APIRouter()

_ESTATE_TYPE_COMMUNITY_LABEL = {
    "housing": "estate",
    "corporate": "organisation",
}


def get_estate_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> EstateService:
    return EstateService(
        estate_repository=EstateRepository(ahttp_client),
        user_repository=UserRepository(ahttp_client),
    )


def get_schedule_repo(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> ScheduleRepo:
    return ScheduleRepo(ahttp_client)


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


@router.get("/public/search", response_model=PublicEstateListResponse)
async def public_search_estates(
    search_query: Optional[str] = Query(
        None, description="Search by estate name or location"
    ),
    estate_type: Optional[EstateType] = Query(
        None, description="Filter by estate type"
    ),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(
        10, ge=1, le=100, description="Number of items per page"
    ),
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
):
    """Search estates without authentication. Returns limited public fields."""
    estate_repository = EstateRepository(ahttp_client)
    user_repository = UserRepository(ahttp_client)
    service = EstateService(estate_repository, user_repository)

    request = SearchEstateRequest(
        search_query=search_query,
        estate_type=estate_type,
        is_active=True,
        page=page,
        limit=limit,
    )
    result = await service.search_estates(request)

    public_items = [
        PublicEstateSearchResponse(
            id=item.id,
            name=item.name,
            location=item.location,
            estate_type=item.estate_type,
        )
        for item in result.items
    ]
    return PublicEstateListResponse(
        total=result.total,
        page=result.page,
        limit=result.limit,
        items=public_items,
    )


@router.post("/{estate_id}/deactivate")
async def deactivate_estate(
    estate_id: str,
    request: DeactivateEstateRequest,
    background_tasks: BackgroundTasks,
    service: EstateService = Depends(get_estate_service),
    schedule_repo: ScheduleRepo = Depends(get_schedule_repo),
    current_user: dict = Depends(get_current_user),
):
    """
    Deactivate an estate (root only). Reversible.

    - `deactivate_at` omitted or null → immediate deactivation.
    - `deactivate_at` is a future datetime → scheduled deactivation via Redis.
      Cannot exceed SCHEDULE_CLOSE_MAX_DAYS days from now.
    """
    if current_user["role"] != "root":
        raise HTTPException(
            status_code=403,
            detail="Only root can deactivate an estate.",
        )

    try:
        estate = await service.get_estate(estate_id)
        community_label = _ESTATE_TYPE_COMMUNITY_LABEL.get(
            estate.estate_type.value if estate.estate_type else "",
            "community",
        )
    except Exception:
        community_label = "community"

    if request.deactivate_at is None:
        await service.deactivate_estate(estate_id, current_user["id"])
        background_tasks.add_task(
            fire_notify,
            {
                "type": "ESTATE_DEACTIVATED",
                "title": f"{community_label.capitalize()} deactivated",
                "body": (
                    f"Your {community_label} has been deactivated"
                    " by the platform."
                ),
                "fan_out": {
                    "estate_id": estate_id,
                    "roles": ["admin", "primary_admin"],
                },
                "metadata": {"community_label": community_label},
            },
        )
        return {"success": True, "message": "Estate deactivated."}

    result = await service.schedule_deactivate_estate(
        estate_id=estate_id,
        actor_user_id=current_user["id"],
        deactivate_at=request.deactivate_at,
        schedule_repo=schedule_repo,
    )
    if result["primary_admin_id"]:
        background_tasks.add_task(
            fire_notify,
            {
                "type": "ESTATE_DEACTIVATION_SCHEDULED",
                "title": (
                    f"{community_label.capitalize()} deactivation scheduled"
                ),
                "body": (
                    f"Your {community_label} is scheduled to be deactivated"
                    f" on {result['deactivate_at'].strftime('%Y-%m-%d')}."
                ),
                "recipient_user_ids": [result["primary_admin_id"]],
                "metadata": {
                    "deactivate_at": result["deactivate_at"].isoformat(),
                    "community_label": community_label,
                },
            },
        )
    return {"success": True, "message": "Estate deactivation scheduled."}


@router.post("/{estate_id}/activate")
async def reactivate_estate(
    estate_id: str,
    background_tasks: BackgroundTasks,
    service: EstateService = Depends(get_estate_service),
    current_user: dict = Depends(get_current_user),
):
    """Reactivate a previously deactivated estate (root only)."""
    if current_user["role"] != "root":
        raise HTTPException(
            status_code=403,
            detail="Only root can reactivate an estate.",
        )

    await service.reactivate_estate(estate_id, current_user["id"])

    try:
        estate = await service.get_estate(estate_id)
        community_label = _ESTATE_TYPE_COMMUNITY_LABEL.get(
            estate.estate_type.value if estate.estate_type else "",
            "community",
        )
    except Exception:
        community_label = "community"

    background_tasks.add_task(
        fire_notify,
        {
            "type": "ESTATE_REACTIVATED",
            "title": f"{community_label.capitalize()} reactivated",
            "body": f"Your {community_label} has been reactivated.",
            "fan_out": {
                "estate_id": estate_id,
                "roles": ["admin", "primary_admin"],
            },
            "metadata": {"community_label": community_label},
        },
    )

    return {"success": True, "message": "Estate reactivated."}


@router.delete("/{estate_id}/deactivate")
async def cancel_estate_deactivation(
    estate_id: str,
    service: EstateService = Depends(get_estate_service),
    schedule_repo: ScheduleRepo = Depends(get_schedule_repo),
    current_user: dict = Depends(get_current_user),
):
    """
    Cancel a pending scheduled estate deactivation (root only).
    Returns 404 if no scheduled deactivation exists for this estate.
    """
    if current_user["role"] != "root":
        raise HTTPException(
            status_code=403,
            detail="Only root can cancel a scheduled estate deactivation.",
        )

    await service.cancel_scheduled_deactivation(estate_id, schedule_repo)
    return {
        "success": True,
        "message": "Scheduled estate deactivation cancelled.",
    }


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
