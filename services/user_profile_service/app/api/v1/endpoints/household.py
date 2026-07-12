import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_notify
from app.libs.role_permissions import check_permission
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.user import UserRepository
from app.schemas.household import (
    CreateHouseholdRequest,
    CreateHouseholdResponse,
    HouseholdItem,
    SearchHouseholdsResponse,
    SetHouseholdHeadRequest,
    UpdateHouseholdRequest,
    UpdateHouseholdResponse,
)
from app.services.auth import get_current_user
from app.services.household import HouseholdService

_ESTATE_TYPE_GROUP_LABEL = {
    "housing": "household",
    "corporate": "department",
}

logger = logging.getLogger(__name__)

router = APIRouter()


async def _resolve_group_label(
    user_id: str,
    user_repo: UserRepository,
    estate_repo: EstateRepository,
) -> str:
    """Return the group label for the estate the user belongs to."""
    try:
        user = await user_repo.get_user_by_id(user_id)
        estate = await estate_repo.get_estate_by_id(str(user.estate_id))
        return _ESTATE_TYPE_GROUP_LABEL.get(
            estate.estate_type.value if estate.estate_type else "",
            "household",
        )
    except Exception:
        return "household"


def _get_service(ahttp_client: AsyncHttpHandler) -> HouseholdService:
    return HouseholdService(
        household_repo=HouseholdRepository(ahttp_client),
        user_repo=UserRepository(ahttp_client),
    )


async def _require_household_permission(
    ahttp_client: AsyncHttpHandler,
    current_user: dict,
) -> None:
    """Raises 403 if the requester lacks can_add_household_member."""
    if not await check_permission(
        ahttp_client, current_user["role"], "can_add_household_member"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to manage households.",
        )


def _resolve_estate_id(
    current_user: dict, provided: Optional[str] = None
) -> str:
    """
    Returns the estate_id to scope the operation to.
    - Non-root: always their own estate_id from the token.
    - Root: must explicitly provide estate_id.
    """
    if current_user["role"] == "root":
        if not provided:
            raise HTTPException(
                status_code=400,
                detail="estate_id is required for root users.",
            )
        return provided
    return current_user["estate_id"]


def _actor_estate_id(current_user: dict) -> str | None:
    """Returns estate_id for non-root users, None for root (no restriction)."""
    if current_user["role"] == "root":
        return None
    return current_user["estate_id"]


@router.post("", response_model=CreateHouseholdResponse, status_code=201)
async def create_household(
    request: CreateHouseholdRequest,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
) -> CreateHouseholdResponse:
    """
    Creates a new household.

    Non-root users always create within their own estate regardless of
    any estate_id in the request body.
    """
    await _require_household_permission(ahttp_client, current_user)
    estate_id = _resolve_estate_id(
        current_user, str(request.estate_id) if request.estate_id else None
    )
    request.estate_id = estate_id  # type: ignore[assignment]
    service = _get_service(ahttp_client)
    return await service.create_household(request)


@router.get("/search", response_model=SearchHouseholdsResponse)
async def search_households(
    estate_id: Optional[str] = None,
    name: Optional[str] = None,
    head_user_id: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
) -> SearchHouseholdsResponse:
    """
    Lists households with optional filters.

    Non-root users are always scoped to their own estate.
    Root users must provide estate_id.
    """
    await _require_household_permission(ahttp_client, current_user)
    scoped_estate_id = _resolve_estate_id(current_user, estate_id)
    service = _get_service(ahttp_client)
    return await service.search_households(
        estate_id=scoped_estate_id,
        name=name,
        head_user_id=head_user_id,
        page=page,
        limit=limit,
    )


@router.get("/{household_id}", response_model=HouseholdItem)
async def get_household(
    household_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
) -> HouseholdItem:
    """
    Retrieves a household by ID.

    Non-root users can only fetch households within their own estate.
    """
    await _require_household_permission(ahttp_client, current_user)
    service = _get_service(ahttp_client)
    return await service.get_household(
        household_id, actor_estate_id=_actor_estate_id(current_user)
    )


@router.post("/{household_id}/head")
async def set_household_head(
    household_id: str,
    request: SetHouseholdHeadRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Assigns a user as the head of a household.

    Non-root users can only manage households within their own estate.
    Sends an in-app notification to the new head after assignment.
    """
    await _require_household_permission(ahttp_client, current_user)
    service = _get_service(ahttp_client)
    group_label = await _resolve_group_label(
        str(request.user_id),
        service.user_repo,
        EstateRepository(ahttp_client),
    )

    result = await service.set_household_head(
        household_id,
        request,
        actor_estate_id=_actor_estate_id(current_user),
    )

    background_tasks.add_task(
        fire_notify,
        {
            "type": "HOUSEHOLD_HEAD_ASSIGNED",
            "title": f"You are now a {group_label} head",
            "body": (
                f"You have been assigned as the head of your {group_label}."
            ),
            "recipient_user_ids": [str(request.user_id)],
            "metadata": {
                "household_id": household_id,
                "group_label": group_label,
            },
        },
    )
    return result


@router.post("/transfer", response_model=UpdateHouseholdResponse)
async def transfer_user_household(
    payload: UpdateHouseholdRequest,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
) -> UpdateHouseholdResponse:
    """
    Transfers a user to a different household within the same estate.

    Non-root users can only transfer users within their own estate.
    Notifies the user of the transfer. If the user was a household head,
    the old household's head is cleared and admins are notified in-app
    (handled inside the service).
    """
    await _require_household_permission(ahttp_client, current_user)

    service = _get_service(ahttp_client)
    group_label = await _resolve_group_label(
        str(payload.user_id),
        service.user_repo,
        EstateRepository(ahttp_client),
    )

    result = await service.transfer_user(
        payload,
        actor_estate_id=_actor_estate_id(current_user),
        group_label=group_label,
    )

    background_tasks.add_task(
        fire_notify,
        {
            "type": "HOUSEHOLD_TRANSFERRED",
            "title": f"{group_label.capitalize()} updated",
            "body": f"You have been moved to a new {group_label}.",
            "recipient_user_ids": [str(payload.user_id)],
            "metadata": {"group_label": group_label},
        },
    )
    return result
