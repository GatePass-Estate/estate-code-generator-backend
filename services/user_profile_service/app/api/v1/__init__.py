from fastapi import APIRouter

from app.api.v1.endpoints.admin import router as admin_router
from app.api.v1.endpoints.broadcast import router as broadcast_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.estate import router as estate_router
from app.api.v1.endpoints.help import router as help_router
from app.api.v1.endpoints.household import router as household_router
from app.api.v1.endpoints.incident_report import (
    router as incident_report_router,
)
from app.api.v1.endpoints.internal import router as internal_router
from app.api.v1.endpoints.request import router as request_router
from app.api.v1.endpoints.user import router as user_router
from app.api.v1.endpoints.user_documents import (
    router as user_documents_router,
)

api_router = APIRouter()

api_router.include_router(user_router, prefix="/users", tags=["Users"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(estate_router, prefix="/estates", tags=["Estates"])
api_router.include_router(
    request_router, prefix="/requests", tags=["Requests"]
)
api_router.include_router(admin_router, prefix="/admins", tags=["Admins"])
api_router.include_router(
    incident_report_router,
    prefix="/incident-reports",
    tags=["Incident Reports"],
)
api_router.include_router(
    user_documents_router,
    prefix="/users/documents",
    tags=["User Documents"],
)
api_router.include_router(
    household_router,
    prefix="/households",
    tags=["Households"],
)
api_router.include_router(
    internal_router,
    prefix="/internal",
    tags=["Internal"],
)
api_router.include_router(help_router, prefix="/help", tags=["Help"])
api_router.include_router(
    broadcast_router, prefix="/broadcasts", tags=["Broadcasts"]
)
