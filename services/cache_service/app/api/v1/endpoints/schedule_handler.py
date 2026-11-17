import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status

from app.db.session import get_redis_connection
from app.repositories.cache_service.schedule_handler import ScheduleRepository
from app.schemas.cache_service.schedule_schema import (
    ScheduleAddRequest,
    ScheduleAddResponse,
    ScheduleDueResponse,
    ScheduleRemoveRequest,
)
from app.services.cache_service.schedule_handler import ScheduleService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    redis_session: redis.Redis = Depends(get_redis_connection),
) -> ScheduleService:
    return ScheduleService(
        repository=ScheduleRepository(session=redis_session)
    )


@router.post(
    "",
    response_model=ScheduleAddResponse,
    status_code=status.HTTP_201_CREATED,
    description="Add an entry to a scheduled-task sorted set",
)
async def add_schedule(
    request: ScheduleAddRequest,
    service: ScheduleService = Depends(get_service),
) -> ScheduleAddResponse:
    """Add a task to the sorted set with a Unix-timestamp score."""
    try:
        return await service.add(request)
    except Exception as e:
        logger.exception("Unexpected error in add_schedule")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/{key}/due",
    response_model=ScheduleDueResponse,
    status_code=status.HTTP_200_OK,
    description="Get all tasks due now or in the past for a given key",
)
async def get_due_schedules(
    key: str,
    service: ScheduleService = Depends(get_service),
) -> ScheduleDueResponse:
    """Return members whose score (Unix timestamp) <= now."""
    try:
        return await service.get_due(key)
    except Exception as e:
        logger.exception("Unexpected error in get_due_schedules key=%s", key)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/{key}",
    response_model=bool,
    status_code=status.HTTP_200_OK,
    description="Remove a specific member from a scheduled-task sorted set",
)
async def remove_schedule(
    key: str,
    request: ScheduleRemoveRequest,
    service: ScheduleService = Depends(get_service),
) -> bool:
    """Remove a member from the sorted set. Returns True if it existed."""
    try:
        return await service.remove(key, request)
    except Exception as e:
        logger.exception("Unexpected error in remove_schedule key=%s", key)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/{key}/by-field",
    response_model=bool,
    status_code=status.HTTP_200_OK,
    description=(
        "Remove the first member whose JSON payload contains the given "
        "field=value pair"
    ),
)
async def remove_schedule_by_field(
    key: str,
    field_name: str,
    field_value: str,
    service: ScheduleService = Depends(get_service),
) -> bool:
    """
    Scan the sorted set and remove the member with matching JSON field.
    Returns True if a member was removed.
    """
    try:
        return await service.remove_by_field(key, field_name, field_value)
    except Exception as e:
        logger.exception(
            "Unexpected error in remove_schedule_by_field key=%s", key
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
