import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4

from app.core.exceptions import NotFoundError
from app.libs.auth import get_current_user, get_user_details
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.role_permissions import check_permission, check_status
from app.schemas.code_service import (
    CreateRequestResident,
    CreateRequestVisitor,
    CreateResponse,
    GetResponseResident,
    GetResponseVisitor,
    ListResponse,
)
from app.services.code_service import (
    CodeService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> Service:
    """
    Get an instance of Service.

    Returns:
        Service: Instance of Service
    """
    return Service(ahttp_client=ahttp_client)


@router.post(
    "",
    response_model=CreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "item saved successfully"},
    },
    description="Create a new item",
)
async def generate(
    receiver: str,
    request: CreateRequestVisitor | CreateRequestResident,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> CreateResponse:
    """
    Creates a new record in the database if it doesn't exist, otherwise
    updates the existing record.

    Arguments:
        request: The request model to CREATE a new record.
        receiver: The status of the code owner (visitor or resident).

    Returns:
        The response model to CREATE a new record.

    Raises:
        HTTPException: If there is an internal server error
    """
    # Extract complete user_details
    user_details = await get_user_details(
        service.ahttp_client, current_user["id"]
    )

    # Extract role of the requester
    requester_role = current_user["role"]

    if not await check_status(user_details):
        raise HTTPException(
            status_code=403, detail="Your account is not verified yet."
        )

    # Check permission to register users
    if not await check_permission(
        service.ahttp_client, requester_role, "can_generate_code"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to generate codes."
        )

    try:
        return await service.generate(
            request=request, receiver=receiver, user_details=user_details
        )
    except Exception as e:
        logger.exception(
            f"An unexpected error happened while creating the item\nError: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/{code}",
    response_model=GetResponseResident | GetResponseVisitor,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Retrieved the item"},
    },
    description="Get an item by ID",
)
async def validate(
    receiver: str,
    code: str,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> GetResponseResident | GetResponseVisitor:
    """
    Get an item by its unique ID from the database.

    Arguments:
        code: The generated access code to be validated.
        recevier: The status of the code owner (visitor and resident)

    Returns:
        A GET response model containing reference to the retrieved item.

    Raises:
        HTTPException: If there is an internal server error
    """
    # Extract complete user_details
    user_details = await get_user_details(
        service.ahttp_client, current_user["id"]
    )

    # Extract role of the requester
    requester_role = current_user["role"]

    if not await check_status(user_details):
        raise HTTPException(
            status_code=403, detail="Your account is not verified yet."
        )

    # Check permission to register users
    if not await check_permission(
        service.ahttp_client, requester_role, "can_validate_code"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to validate codes."
        )

    try:
        return await service.validate(
            code=code, receiver=receiver, user_details=user_details
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"{e}") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting the item")
        raise HTTPException(
            status_code=500, detail="Internal server error!"
        ) from e


@router.get(
    "/all/{user_id}",
    response_model=ListResponse | GetResponseResident,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Retrieved items"},
    },
    description="Get items by user ID",
)
async def get_all_codes_by_user(
    user_id: UUID4,
    receiver: str,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> ListResponse | GetResponseResident:
    """
    Get all items linked to a given user ID.

    Arguments:
        user_id: The user ID to be retrieved for.
        recevier: The status of the code owner (visitor and resident)

    Returns:
        A List response model containing reference to the retrieved items if
        the recever is 'visitor', or a single item if the receiver is
        'resident'.

    Raises:
        HTTPException: If there is an internal server error
    """
    # Extract complete user_details
    user_details = await get_user_details(
        service.ahttp_client, current_user["id"]
    )

    # Extract role of the requester
    requester_role = current_user["role"]

    if not await check_status(user_details):
        raise HTTPException(
            status_code=403, detail="Your account is not verified yet."
        )

    # Check permission to register users
    if not await check_permission(
        service.ahttp_client, requester_role, "can_generate_code"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to get all codes for this user.",
        )

    try:
        return await service.get_items_by_user(
            user_id=user_id, receiver=receiver, user_details=user_details
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"{e}") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting the item")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/{code}",
    response_model=bool,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Retrieved the item"},
    },
    description="Delete an item by code",
)
async def delete(
    code: str,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> bool:
    """
    Delete an item by its associated code in the cache.

    Arguments:
        code: The generated access code to be deleted.

    Returns:
        A boolean indicating whether the item was deleted successfully.

    Raises:
        HTTPException: If there is an internal server error
    """
    # Extract complete user_details
    user_details = await get_user_details(
        service.ahttp_client, current_user["id"]
    )

    # Extract role of the requester
    requester_role = current_user["role"]

    if not await check_status(user_details):
        raise HTTPException(
            status_code=403, detail="Your account is not verified yet."
        )

    # Check permission to register users
    if not await check_permission(
        service.ahttp_client, requester_role, "can_generate_code"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to delete codes.",
        )

    try:
        return await service.delete(code=code, user_details=user_details)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting the item")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
