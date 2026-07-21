import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import UUID4

from app.core.exceptions import NotFoundError, ScheduleError
from app.libs.auth import get_current_user, get_user_details
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.libs.notify import fire_notify
from app.libs.role_permissions import check_permission, check_status
from app.schemas.code_service import (
    CreateRequestResident,
    CreateRequestVisitor,
    CreateResponse,
    ExtendResponse,
    FreezeResponse,
    GetResponseResident,
    GetResponseVisitor,
    ListResponse,
    Receiver,
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
        400: {"description": "Validity period exceeds allowed schedule"},
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
    Generate a visitor or resident access code.

    Visitor requests may include optional ``validity_period`` (total UTC
    range) and ``validity_window`` (daily hours). Omitted period defaults to
    one hour from creation. The total validity period may not start or end
    more than 2 weeks from the current time.

    Raises:
        HTTPException: 400 if the validity period exceeds 2 weeks; 500 otherwise.
    """
    try:
        # Option 1: Direct enum validation
        receiver = Receiver(receiver)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid receiver type. Must be one of: "
                f"{[r.value for r in Receiver]}"
            ),
        )

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
    except ScheduleError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
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
    code: str,
    background_tasks: BackgroundTasks,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> GetResponseResident | GetResponseVisitor:
    """
    Get an item by its unique ID from the database.

    Arguments:
        code: The generated access code to be validated.

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
        result = await service.validate(code=code, user_details=user_details)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"{e}") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting the item")
        raise HTTPException(
            status_code=500, detail="Internal server error!"
        ) from e

    now = datetime.now(timezone.utc).isoformat()
    resident_id = str(result.user_id)

    if isinstance(result, GetResponseVisitor) and result.is_valid:
        background_tasks.add_task(
            fire_notify,
            {
                "type": "GUEST_CODE_USED",
                "title": "Visitor arrived",
                "body": (
                    f"{result.visitor_fullname} has arrived at your estate."
                ),
                "recipient_user_ids": [resident_id],
                "metadata": {
                    "visitor_name": result.visitor_fullname,
                    "code_id": result.hashed_code,
                    "visit_time": now,
                },
            },
        )
    elif isinstance(result, GetResponseResident) and result.is_valid:
        background_tasks.add_task(
            fire_notify,
            {
                "type": "RESIDENT_CODE_USED",
                "title": "Access code used",
                "body": "Your resident access code was scanned.",
                "recipient_user_ids": [resident_id],
                "metadata": {
                    "code_id": code,
                    "access_time": now,
                },
            },
        )

    return result


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
    upcoming: bool = False,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> ListResponse | GetResponseResident:
    """
    Get all items linked to a given user ID.

    Arguments:
        user_id: The user ID to be retrieved for.
        recevier: The status of the code owner (visitor and resident)
        upcoming: When true, return only visitor codes whose validity period
            has not started yet. Only valid with receiver=visitor.

    Returns:
        A List response model containing reference to the retrieved items if
        the recever is 'visitor', or a single item if the receiver is
        'resident'.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        # Option 1: Direct enum validation
        receiver = Receiver(receiver)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid receiver type. Must be one of: "
                f"{[r.value for r in Receiver]}"
            ),
        )

    if upcoming and receiver != Receiver.VISITOR:
        raise HTTPException(
            status_code=400,
            detail="The upcoming filter is only supported for visitor codes.",
        )

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
            user_id=user_id,
            receiver=receiver,
            user_details=user_details,
            upcoming=upcoming,
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


@router.patch(
    "/{code}/extend",
    response_model=ExtendResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Extend attempted"},
    },
    description="Extend a visitor access code by one hour",
)
async def extend_code(
    code: str,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> ExtendResponse:
    user_details = await get_user_details(
        service.ahttp_client, current_user["id"]
    )
    requester_role = current_user["role"]

    if not await check_status(user_details):
        raise HTTPException(
            status_code=403, detail="Your account is not verified yet."
        )

    if not await check_permission(
        service.ahttp_client, requester_role, "can_generate_code"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to extend codes.",
        )

    try:
        logger.info(
            "Extend visitor code requested code=%s requester_id=%s",
            code,
            user_details.get("id"),
        )
        return await service.extend_code(code=code, user_details=user_details)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"{e}") from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while extending the code"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.patch(
    "/{code}/freeze",
    response_model=FreezeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Freeze toggled"},
    },
    description="Toggle freeze/pause on a visitor access code",
)
async def freeze_code(
    code: str,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> FreezeResponse:
    user_details = await get_user_details(
        service.ahttp_client, current_user["id"]
    )
    requester_role = current_user["role"]

    if not await check_status(user_details):
        raise HTTPException(
            status_code=403, detail="Your account is not verified yet."
        )

    if not await check_permission(
        service.ahttp_client, requester_role, "can_generate_code"
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to freeze codes.",
        )

    try:
        logger.info(
            "Freeze visitor code requested code=%s requester_id=%s",
            code,
            user_details.get("id"),
        )
        return await service.toggle_freeze_code(
            code=code, user_details=user_details
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"{e}") from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while freezing the code"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.patch(
    "/resident/{user_id}",
    response_model=CreateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Resident code not found"},
        200: {"description": "Resident code updated successfully"},
    },
    description="Update a resident's access code",
)
async def update_resident_code(
    user_id: UUID4,
    service: Service = Depends(get_service),
    current_user: dict = Depends(get_current_user),
) -> CreateResponse:
    """
    Update a resident's access code by generating a new one.

    Arguments:
        user_id: The user ID of the resident whose code needs to be updated.

    Returns:
        The response model containing the new access code details.

    Raises:
        HTTPException: If there is an internal server error or resident code
        not found
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

    # Check permission to update codes
    if not await check_permission(
        service.ahttp_client, requester_role, "can_generate_code"
    ):
        raise HTTPException(
            status_code=403, detail="You are not authorized to update codes."
        )

    try:
        return await service.update_resident_code(
            user_id=user_id, user_details=user_details
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=f"{e}") from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while updating resident code"
            f"\nError: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
