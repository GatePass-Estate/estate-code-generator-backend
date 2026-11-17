import logging

from app.repositories.cache_service.schedule_handler import ScheduleRepository
from app.schemas.cache_service.schedule_schema import (
    ScheduleAddRequest,
    ScheduleAddResponse,
    ScheduleDueResponse,
    ScheduleRemoveRequest,
)

logger = logging.getLogger(__name__)


class ScheduleService:
    """Service layer for scheduled-task sorted-set operations."""

    def __init__(self, repository: ScheduleRepository) -> None:
        self.repository = repository

    async def add(self, request: ScheduleAddRequest) -> ScheduleAddResponse:
        return await self.repository.add(request)

    async def get_due(self, key: str) -> ScheduleDueResponse:
        return await self.repository.get_due(key)

    async def remove(self, key: str, request: ScheduleRemoveRequest) -> bool:
        return await self.repository.remove(key, request)

    async def remove_by_field(
        self, key: str, field_name: str, field_value: str
    ) -> bool:
        return await self.repository.remove_by_field(
            key, field_name, field_value
        )
