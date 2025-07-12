import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4

from app.core.exceptions import NotFoundError
from app.db.session import get_redis_connection
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    GetResponse,
    ListResponse,
)
from app.services.cache_service.cache_handler import (
    CacheHandlerService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    redis_session: redis.Redis = Depends(get_redis_connection),
) -> Service:
    """
    Get an instance of Service.

    Returns:
        Service: Instance of Service
    """
    return Service(redis_session=redis_session)


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
async def create(
    request: CreateRequest,
    service: Service = Depends(get_service),
) -> CreateResponse:
    """
    Creates a new record in the database if it doesn't exist, otherwise
    updates the existing record.

    Arguments:
        request: The request model to CREATE a new record.

    Returns:
        The response model to CREATE a new record.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        return await service.create(request=request)
    except Exception as e:
        logger.exception(
            "An unexpected error happened while creating the item"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/{code}",
    response_model=GetResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Retrieved the item"},
    },
    description="Get an item by ID",
)
async def get(
    code: str,
    service: Service = Depends(get_service),
) -> GetResponse:
    """
    Get an item by its unique ID from the database.

    Arguments:
        code: The generated access code to be retrieved.

    Returns:
        A GET response model containing reference to the retrieved item.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        return await service.get(code=code)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting the item")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/all/{user_id}",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved items"},
    },
    description="Get items by user ID",
)
async def get_all_items_by_user(
    user_id: UUID4,
    estate_id: UUID4,
    service: Service = Depends(get_service),
) -> ListResponse:
    """
    Get all item linked to a given user ID.

    Arguments:
        user_id: The user ID to be retrieved for.
        estate_id: The estate ID to be retrieved for.

    Returns:
        A List response model containing reference to the retrieved items.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        return await service.get_all_items_by_user(
            user_id=user_id, estate_id=estate_id
        )
    except Exception as e:
        logger.exception("An unexpected error happened while getting items")
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
) -> bool:
    """
    Delete an item by code from the cache.

    Arguments:
        code: The generated access code to be deleted.

    Returns:
        A boolean indicating whether the item was deleted successfully.

    Raises:
        HTTPException: If there is an internal server error or item not found.
    """
    try:
        return await service.delete(code=code)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while deleting the item"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
