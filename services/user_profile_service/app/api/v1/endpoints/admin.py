from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_notify
from gatepass_rbac import check_permission
from app.repositories.user import UserRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.admin_management import AdminRepository
from app.repositories.user_documents import UserDocumentsRepository
from app.services.user import UserService
from app.services.admin_management import AdminManagementService
from app.services.auth import get_current_user

router = APIRouter()


def _get_admin_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> AdminManagementService:
    user_repo = UserRepository(ahttp_client)
    estate_repo = EstateRepository(ahttp_client)
    household_repo = HouseholdRepository(ahttp_client)
    admin_repo = AdminRepository(ahttp_client)
    docs_repo = UserDocumentsRepository(ahttp_client)

    user_service = UserService(
        user_repo, estate_repo, household_repo, admin_repo
    )
    return AdminManagementService(
        admin_repository=admin_repo,
        user_service=user_service,
        estate_repository=estate_repo,
        docs_repository=docs_repo,
    )


@router.post("/promote")
async def promote_user_to_admin(
    user_id: str,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
    admin_service: AdminManagementService = Depends(_get_admin_service),
) -> dict:
    """
    Promote an existing user to admin role.
    Only primary_admin and root users can promote users to admin.
    Permission required: can_register_admin
    """
    if not await check_permission(
        ahttp_client, current_user["role"], "can_register_admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to promote users to admin.",
        )

    result = await admin_service.promote_to_admin(
        user_id=user_id,
        current_user=current_user,
    )

    background_tasks.add_task(
        fire_notify,
        {
            "type": "ROLE_PROMOTED",
            "title": "Your role has been updated",
            "body": "You have been promoted to admin.",
            "recipient_user_ids": [user_id],
            "metadata": {
                "new_role": "admin",
                "estate_id": result["estate_id"],
                "estate_name": result["estate_name"],
            },
        },
    )

    return {
        "user_id": result["user_id"],
        "role": result["role"],
        "estate_id": result["estate_id"],
        "message": result["message"],
    }


@router.post("/demote")
async def demote_admin_to_resident(
    user_id: str,
    background_tasks: BackgroundTasks,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
    admin_service: AdminManagementService = Depends(_get_admin_service),
) -> dict:
    """
    Demote an admin to resident role.
    Only primary_admin and root users can demote admins.
    Permission required: can_register_admin
    """
    if not await check_permission(
        ahttp_client, current_user["role"], "can_register_admin"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to demote admins."
        )

    result = await admin_service.demote_to_resident(
        user_id=user_id,
        current_user=current_user,
    )

    background_tasks.add_task(
        fire_notify,
        {
            "type": "ROLE_DEMOTED",
            "title": "Your role has been updated",
            "body": "Your admin role has been removed.",
            "recipient_user_ids": [user_id],
            "metadata": {
                "new_role": "resident",
                "estate_id": result["estate_id"],
                "estate_name": result["estate_name"],
            },
        },
    )

    return {
        "user_id": result["user_id"],
        "role": result["role"],
        "estate_id": result["estate_id"],
        "message": result["message"],
    }
