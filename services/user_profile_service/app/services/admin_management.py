from app.repositories.admin_management import AdminRepository


class AdminManagementService:
    """
    Service for managing admin-related operations.
    """

    def __init__(
        self,
        admin_repository: AdminRepository,
    ):
        self.repository = admin_repository

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
