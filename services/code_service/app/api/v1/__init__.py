from fastapi import APIRouter

from app.api.v1.endpoints.code_service import (
    router as codeservice_router,
)
from app.api.v1.endpoints.resident_log import (
    router as residentlog_router,
)
from app.api.v1.endpoints.visitor_log import (
    router as visitorlog_router,
)

api_router = APIRouter()

api_router.include_router(
    codeservice_router,
    prefix="/codeservice",
    tags=["AccessCode"],
)

api_router.include_router(
    residentlog_router,
    prefix="/codeservice/residentlog",
    tags=["ResidentLog"],
)

api_router.include_router(
    visitorlog_router,
    prefix="/codeservice/visitorlog",
    tags=["VisitorLog"],
)
