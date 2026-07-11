import logging

from fastapi import HTTPException

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
from app.schemas.user import UpdateUserRequest

logger = logging.getLogger(__name__)


class HouseholdService:
    """
    Business logic for household management.

    Methods:
        create_household: Creates a new household.
        search_households: Lists households for an estate.
        get_household: Retrieves a household by ID.
        set_household_head: Assigns a user as household head.
    """

    def __init__(
        self,
        household_repo: HouseholdRepository,
        user_repo: UserRepository,
    ) -> None:
        self.household_repo = household_repo
        self.user_repo = user_repo

    async def create_household(
        self, request: CreateHouseholdRequest
    ) -> CreateHouseholdResponse:
        """
        Creates a new household, optionally assigning an initial head.

        If head_user_id is provided, validates that the user exists and
        belongs to the same estate.

        Args:
            request: The create household request.

        Returns:
            CreateHouseholdResponse: The created household record.

        Raises:
            HTTPException: If the head user is not found or mismatched.
        """
        if request.head_user_id:
            head_user = await self.user_repo.get_user_by_id(
                str(request.head_user_id)
            )
            if not head_user:
                raise HTTPException(
                    status_code=404, detail="Head user not found."
                )
            if str(head_user.estate_id) != str(request.estate_id):
                raise HTTPException(
                    status_code=400,
                    detail="Head user does not belong to this estate.",
                )

        return await self.household_repo.create_household(request)

    async def search_households(
        self,
        estate_id: str,
        name: str | None = None,
        head_user_id: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> SearchHouseholdsResponse:
        """
        Lists households for an estate with optional filters.

        Args:
            estate_id: The estate to search within.
            name: Optional substring match on household name.
            head_user_id: Optional filter by head user.
            page: Page number.
            limit: Items per page.

        Returns:
            SearchHouseholdsResponse: Paginated household list.
        """
        return await self.household_repo.search_households(
            estate_id=estate_id,
            name=name,
            head_user_id=head_user_id,
            page=page,
            limit=limit,
        )

    async def get_household(
        self,
        household_id: str,
        actor_estate_id: str | None = None,
    ) -> HouseholdItem:
        """
        Retrieves a household by ID.

        Args:
            household_id: The household ID.
            actor_estate_id: If provided, raises 403 if the household does
                not belong to this estate.

        Returns:
            HouseholdItem: The household record.

        Raises:
            HTTPException: If the household is not found or estate mismatch.
        """
        household = await self.household_repo.get_household_by_id(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found.")
        if actor_estate_id and str(household.estate_id) != actor_estate_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "You can only access households within your own estate."
                ),
            )
        return household

    async def set_household_head(
        self,
        household_id: str,
        request: SetHouseholdHeadRequest,
        actor_estate_id: str | None = None,
    ) -> dict:
        """
        Assigns a user as the head of a household.

        Validates the household exists and the user belongs to the same
        estate.

        Args:
            household_id: The household to update.
            request: Contains the user_id to assign as head.

        Returns:
            dict: Success confirmation.

        Raises:
            HTTPException: If household or user not found, or estate
                mismatch.
        """
        household = await self.household_repo.get_household_by_id(household_id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found.")
        if actor_estate_id and str(household.estate_id) != actor_estate_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "You can only manage households within your own estate."
                ),
            )

        user = await self.user_repo.get_user_by_id(str(request.user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        if str(user.estate_id) != str(household.estate_id):
            raise HTTPException(
                status_code=400,
                detail="User does not belong to the household's estate.",
            )

        await self.household_repo.update_household(
            household_id, {"head_user_id": str(request.user_id)}
        )
        return {"success": True, "message": "Household head assigned."}

    async def transfer_user(
        self,
        payload: UpdateHouseholdRequest,
        actor_estate_id: str | None = None,
    ) -> UpdateHouseholdResponse:
        """
        Transfers a user to a different household within the same estate.

        If the user was the head of their previous household, that
        household's head_user_id is cleared and admins are notified.

        Args:
            payload: Contains user_id and the target household_id.

        Returns:
            UpdateHouseholdResponse: Success confirmation.

        Raises:
            HTTPException: If user or household not found, or estate
                mismatch.
        """
        user = await self.user_repo.get_user_by_id(str(payload.user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        if actor_estate_id and str(user.estate_id) != actor_estate_id:
            raise HTTPException(
                status_code=403,
                detail=("You can only manage users within your own estate."),
            )

        new_household = await self.household_repo.get_household_by_id(
            str(payload.household_id)
        )
        if not new_household:
            raise HTTPException(status_code=404, detail="Household not found.")

        if str(new_household.estate_id) != str(user.estate_id):
            raise HTTPException(
                status_code=400,
                detail="Household does not belong to user's estate.",
            )

        old_household_id = (
            str(user.household_id) if user.household_id else None
        )

        await self.user_repo.update_user(
            user_id=str(user.id),
            data=UpdateUserRequest(household_id=str(payload.household_id)),
        )

        # Clear head if user was head of their old household
        if old_household_id:
            try:
                old_hh = await self.household_repo.get_household_by_id(
                    old_household_id
                )
                if old_hh and old_hh.head_user_id == str(user.id):
                    await self.household_repo.update_household(
                        old_household_id, {"head_user_id": None}
                    )
                    await self.notify_admins_headless_household(
                        household_id=old_household_id,
                        household_name=old_hh.name or "",
                        estate_id=str(old_hh.estate_id)
                        if old_hh.estate_id
                        else "",
                    )
            except Exception:
                logger.exception(
                    "Failed to clear head from old household %s",
                    old_household_id,
                )

        return UpdateHouseholdResponse(
            success=True, message="Household updated."
        )

    async def notify_admins_headless_household(
        self,
        household_id: str,
        household_name: str,
        estate_id: str,
    ) -> None:
        """
        Sends a HOUSEHOLD_NEEDS_HEAD in-app notification to all active
        admins/primary_admins for the given estate.

        Args:
            household_id: The household that lost its head.
            household_name: Display name of the household.
            estate_id: The estate the household belongs to.
        """
        from app.libs.notify import fire_notify

        try:
            await fire_notify(
                {
                    "type": "HOUSEHOLD_NEEDS_HEAD",
                    "title": "Household needs a head",
                    "body": (
                        f"'{household_name}' no longer has a head. "
                        "Please assign one."
                    ),
                    "fan_out": {
                        "estate_id": estate_id,
                        "roles": ["admin", "primary_admin"],
                    },
                    "metadata": {"household_id": household_id},
                }
            )
        except Exception:
            logger.exception(
                "Failed to notify admins of headless household %s",
                household_id,
            )
