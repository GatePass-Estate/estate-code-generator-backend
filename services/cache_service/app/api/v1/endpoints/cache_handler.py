import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4

from app.core.exceptions import NotFoundError
from app.db.session import get_redis_connection
from app.schemas.cache_service.cache_schema import (
    CreateRequest,
    CreateResponse,
    ExtendResponse,
    FreezeResponse,
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
    description="Create a visitor access code in Redis",
)
async def create(
    request: CreateRequest,
    service: Service = Depends(get_service),
) -> CreateResponse:
    """
    Cache a new visitor access code.

    Persists lifecycle fields, resolves optional ``validity_period`` and
    ``validity_window``, and sets Redis TTL from the total period end.
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
    "/{code}/raw",
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Retrieved raw item"},
    },
    description="Get a cached item without validity filtering",
)
async def get_raw(
    code: str,
    service: Service = Depends(get_service),
) -> dict:
    """Return a cached visitor record without validity filtering."""
    try:
        record = await service.get_raw(code=code)
        logger.info("API raw visitor code fetched code=%s", code)
        return record
    except NotFoundError as e:
        logger.warning("API raw visitor code not found code=%s", code)
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting raw item")
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
    description="Add one hour to the visitor code total validity period end",
)
async def extend(
    code: str,
    service: Service = Depends(get_service),
) -> ExtendResponse:
    """
    Extend a visitor code once by adding one hour to ``validity_period.end``.

    Returns ``success=false`` when the code has already been extended.
    """
    try:
        result = await service.extend(code=code)
        logger.info(
            "API extend completed code=%s success=%s", code, result.success
        )
        return result
    except NotFoundError as e:
        logger.warning("API extend not found code=%s", code)
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while extending the item"
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
    description="Toggle freeze/pause on a visitor code",
)
async def freeze(
    code: str,
    service: Service = Depends(get_service),
) -> FreezeResponse:
    """
    Toggle the frozen/paused state of a visitor access code.

    Freeze does not change ``validity_period`` or ``validity_window``.
    """
    try:
        result = await service.toggle_freeze(code=code)
        logger.info(
            "API freeze toggle completed code=%s frozen=%s is_valid=%s",
            code,
            result.frozen,
            result.is_valid,
        )
        return result
    except NotFoundError as e:
        logger.warning("API freeze toggle not found code=%s", code)
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while freezing the item"
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
    description="Validate a visitor access code",
)
async def get(
    code: str,
    service: Service = Depends(get_service),
) -> GetResponse:
    """
    Validate and return a visitor access code from Redis.

    Applies total validity period, daily validity window, and freeze checks.
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
