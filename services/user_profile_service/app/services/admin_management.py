from fastapi import HTTPException

from app.repositories.admin_management import AdminRepository
from app.repositories.estate import EstateRepository
from app.repositories.user_documents import UserDocumentsRepository
from gatepass_rbac import require_estate_membership
from app.schemas.user import Role, UpdateUserRequest
from app.services.user import UserService


class AdminManagementService:
    """
    Service for managing admin-related operations.
    """

    def __init__(
        self,
        admin_repository: AdminRepository,
        user_service: UserService | None = None,
        estate_repository: EstateRepository | None = None,
        docs_repository: UserDocumentsRepository | None = None,
    ):
        self.repository = admin_repository
        self._user_service = user_service
        self._estate_repository = estate_repository
        self._docs_repository = docs_repository

    async def create_admin(self, admin_data: dict) -> dict:
        """
        Creates a new admin user.
        """
        return await self.repository.create_admin_record(admin_data)

    async def get_admin_from_user_id(self, user_id: str) -> dict:
        """
        Retrieves admin details from user ID.
        """
        return await self.repository.get_admin_from_user_id(user_id)

    async def transfer_admin_records(
        self,
        estate_id: str,
        new_primary_admin: str,
    ) -> dict:
        """
        Updates an existing admin user.
        """
        response = await self.repository.get_primary_admin_from_estate_id(
            estate_id
        )
        admin_id = response["id"]
        await self.repository.update_admin_record(
            admin_id, {"is_primary": False}
        )
        response = await self.repository.get_admin_from_user_id(
            new_primary_admin
        )
        admin_id = response["id"]
        await self.repository.update_admin_record(
            admin_id, {"is_primary": True}
        )

    async def promote_to_admin(self, user_id: str, current_user: dict) -> dict:
        """
        Promote a resident to admin. Validates eligibility, checks estate
        membership, and creates the admin_management record.

        Returns a dict with user_id, role, estate_id, estate_name, message.
        """
        user = await self._user_service.get_user(user_id)

        if user.is_deleted:
            raise HTTPException(
                status_code=404, detail="User not found or has been deleted."
            )

        if user.role in [Role.ADMIN, Role.PRIMARY_ADMIN]:
            raise HTTPException(
                status_code=400,
                detail=f"User is already a {user.role}.",
            )

        if user.role != Role.RESIDENT:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Only users with resident role can be promoted to admin. "
                    f"Current role: {user.role}."
                ),
            )

        require_estate_membership(
            current_user,
            str(user.estate_id),
            detail="You can only promote users from your own estate.",
        )

        active_id = await self._docs_repository.get_active_by_user_and_type(
            user_id, "id_card"
        )
        if not active_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "User must have an approved ID card "
                    "before being promoted to admin."
                ),
            )

        await self._user_service.update_user(
            user_id, UpdateUserRequest(role=Role.ADMIN)
        )

        estate_id = str(user.estate_id)
        await self.create_admin(
            {
                "estate_id": estate_id,
                "user_id": user_id,
                "is_primary": False,
            }
        )

        estate = await self._estate_repository.get_estate_by_id(estate_id)
        return {
            "user_id": user_id,
            "role": "admin",
            "estate_id": estate_id,
            "estate_name": estate.name,
            "message": "User successfully promoted to admin.",
        }

    async def demote_to_resident(
        self, user_id: str, current_user: dict
    ) -> dict:
        """
        Demote an admin to resident. Validates eligibility, checks estate
        membership, and removes the admin_management record.

        Returns a dict with user_id, role, estate_id, estate_name, message.
        """
        user = await self._user_service.get_user(user_id)

        if user.is_deleted:
            raise HTTPException(
                status_code=404, detail="User not found or has been deleted."
            )

        if user.role != Role.ADMIN:
            if user.role == Role.PRIMARY_ADMIN:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cannot demote primary_admin. "
                        "Use transfer admin endpoint instead."
                    ),
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "User is not an admin. " f"Current role: {user.role}."
                    ),
                )

        require_estate_membership(
            current_user,
            str(user.estate_id),
            detail="You can only demote admins from your own estate.",
        )

        await self._user_service.update_user(
            user_id, UpdateUserRequest(role=Role.RESIDENT)
        )

        admin_record = await self.get_admin_from_user_id(user_id)
        await self.repository.delete_admin_record(admin_record["id"])

        estate_id = str(user.estate_id)
        estate = await self._estate_repository.get_estate_by_id(estate_id)
        return {
            "user_id": user_id,
            "role": "resident",
            "estate_id": estate_id,
            "estate_name": estate.name,
            "message": "Admin successfully demoted to resident.",
        }
