import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.exceptions import NotFoundError
from app.db.session import get_redis_connection
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    GetResponse,
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
        id: The unique ID of the item to retrieve.

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
