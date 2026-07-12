from fastapi import APIRouter

from app.api.v1.endpoints.cache_handler import (
    router as cachehandler_router,
)
from app.api.v1.endpoints.schedule_handler import (
    router as schedule_router,
)

api_router = APIRouter()

api_router.include_router(
    cachehandler_router,
    prefix="/cacheservice/cachehandler",
    tags=["AccessCode"],
)
api_router.include_router(
    schedule_router,
    prefix="/cacheservice/schedules",
    tags=["Schedules"],
)
