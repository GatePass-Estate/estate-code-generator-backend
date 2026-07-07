from fastapi import APIRouter

from app.api.v1.endpoints.device_tokens import router as device_tokens_router
from app.api.v1.endpoints.internal import router as internal_router
from app.api.v1.endpoints.maintenance import router as maintenance_router
from app.api.v1.endpoints.notifications import router as notifications_router
from app.api.v1.endpoints.preferences import router as preferences_router

api_router = APIRouter()

api_router.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["notifications"],
)
api_router.include_router(
    device_tokens_router,
    prefix="/notifications/device-tokens",
    tags=["device-tokens"],
)
api_router.include_router(
    preferences_router,
    prefix="/notifications/preferences",
    tags=["preferences"],
)
api_router.include_router(
    internal_router,
    prefix="/internal",
    tags=["internal"],
)
api_router.include_router(
    maintenance_router,
    prefix="/maintenance",
    tags=["maintenance"],
)
