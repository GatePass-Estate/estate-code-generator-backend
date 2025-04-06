from fastapi import APIRouter

from app.api.v1.endpoints.code_service.access_code import (
    router as accesscode_router,
)
from app.api.v1.endpoints.code_service.visitor_log import (
    router as visitorlog_router,
)

api_router = APIRouter()

api_router.include_router(
    accesscode_router,
    prefix="/codeservice/accesscode",
    tags=["AccessCode"],
)

api_router.include_router(
    visitorlog_router,
    prefix="/codeservice/visitorlog",
    tags=["VisitorLog"],
)
