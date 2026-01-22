from fastapi import APIRouter, Depends, HTTPException
from app.schemas.user import Role
from app.libs.http_handler import get_http_handler, AsyncHttpHandler
from app.libs.role_permissions import check_permission
from app.repositories.user import UserRepository
from app.repositories.estate import EstateRepository
from app.repositories.household import HouseholdRepository
from app.repositories.admin_management import AdminRepository
from app.services.user import UserService
from app.services.admin_management import AdminManagementService
from app.services.auth import get_current_user
from app.schemas.user import UpdateUserRequest

router = APIRouter()


@router.post("/promote")
async def promote_user_to_admin(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Promote an existing user to admin role.
    Only primary_admin and root users can promote users to admin.

    Permission required: can_register_admin

    Args:
        user_id: ID of the user to promote to admin
        ahttp_client: HTTP client for service communication
        current_user: Authenticated user making the request

    Returns:
        dict: Promotion confirmation with user_id, role, estate_id, and message

    Raises:
        HTTPException 403: If user lacks permission to create admins
        HTTPException 404: If user not found or is deleted
        HTTPException 400: If user is already an admin or primary_admin
        HTTPException 403: If trying to promote user from different estate
    """
    requester_role = current_user["role"]

    # Check permission to register admins
    if not await check_permission(
        ahttp_client, requester_role, "can_register_admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to promote users to admin.",
        )

    # Initialize repositories and services
    user_repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)

    user_service = UserService(
        user_repository,
        estate_repository,
        household_repository,
        admin_repository,
    )
    admin_service = AdminManagementService(admin_repository)

    # Get the user to be promoted
    user_to_promote = await user_service.get_user(user_id)

    # Check if user is deleted
    if user_to_promote.is_deleted:
        raise HTTPException(
            status_code=404, detail="User not found or has been deleted."
        )

    # Check if user is already an admin or primary_admin
    if user_to_promote.role in [Role.ADMIN, Role.PRIMARY_ADMIN]:
        raise HTTPException(
            status_code=400,
            detail=f"User is already a {user_to_promote.role}.",
        )

    # Non-root users can only promote users from their own estate
    if requester_role != Role.ROOT:
        requester_user_id = current_user["id"]
        requester_estate_id = await user_service.get_estate_id_by_user_id(
            requester_user_id
        )

        if requester_estate_id != str(user_to_promote.estate_id):
            raise HTTPException(
                status_code=403,
                detail="You can only promote users from your own estate.",
            )

    # Update user role to admin

    update_request = UpdateUserRequest(role=Role.ADMIN)
    await user_service.update_user(user_id, update_request)

    # Create admin_management record
    await admin_service.create_admin(
        {
            "estate_id": str(user_to_promote.estate_id),
            "user_id": user_id,
            "is_primary": False,
        }
    )

    return {
        "user_id": user_id,
        "role": "admin",
        "estate_id": str(user_to_promote.estate_id),
        "message": "User successfully promoted to admin.",
    }


@router.post("/demote")
async def demote_admin_to_resident(
    user_id: str,
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Demote an admin to resident role.
    Only primary_admin and root users can demote admins.

    Permission required: can_register_admin

    Args:
        user_id: ID of the admin user to demote to resident
        ahttp_client: HTTP client for service communication
        current_user: Authenticated user making the request

    Returns:
        dict: Demotion confirmation with user_id, role, estate_id, and message

    Raises:
        HTTPException 403: If user lacks permission to manage admins
        HTTPException 404: If user not found or is deleted
        HTTPException 400: If user is not an admin
        HTTPException 400: If trying to demote a primary_admin
        HTTPException 403: If trying to demote admin from different estate
    """
    requester_role = current_user["role"]

    # Check permission to register admins (same permission for demotion)
    if not await check_permission(
        ahttp_client, requester_role, "can_register_admin"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to demote admins."
        )

    # Initialize repositories and services
    user_repository = UserRepository(ahttp_client)
    estate_repository = EstateRepository(ahttp_client)
    household_repository = HouseholdRepository(ahttp_client)
    admin_repository = AdminRepository(ahttp_client)

    user_service = UserService(
        user_repository,
        estate_repository,
        household_repository,
        admin_repository,
    )
    admin_service = AdminManagementService(admin_repository)

    # Get the user to be demoted
    user_to_demote = await user_service.get_user(user_id)

    # Check if user is deleted
    if user_to_demote.is_deleted:
        raise HTTPException(
            status_code=404, detail="User not found or has been deleted."
        )

    # Check if user is an admin (not primary_admin or other roles)
    if user_to_demote.role != Role.ADMIN:
        if user_to_demote.role == Role.PRIMARY_ADMIN:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot demote primary_admin."
                    "Use transfer admin endpoint instead."
                ),
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "User is not an admin."
                    f"Current role: {user_to_demote.role}."
                ),
            )

    # Non-root users can only demote admins from their own estate
    if requester_role != Role.ROOT:
        requester_user_id = current_user["id"]
        requester_estate_id = await user_service.get_estate_id_by_user_id(
            requester_user_id
        )

        if requester_estate_id != str(user_to_demote.estate_id):
            raise HTTPException(
                status_code=403,
                detail="You can only demote admins from your own estate.",
            )

    # Update user role to resident

    update_request = UpdateUserRequest(role=Role.RESIDENT)
    await user_service.update_user(user_id, update_request)

    # Get admin_management record and delete it
    admin_record = await admin_service.get_admin_from_user_id(user_id)
    await admin_repository.delete_admin_record(admin_record["id"])

    return {
        "user_id": user_id,
        "role": "resident",
        "estate_id": str(user_to_demote.estate_id),
        "message": "Admin successfully demoted to resident.",
    }
