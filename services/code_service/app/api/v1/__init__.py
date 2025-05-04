from fastapi import APIRouter

from app.api.v1.endpoints.code_service import (
    router as codeservice_router,
)

api_router = APIRouter()

api_router.include_router(
    codeservice_router,
    prefix="/codeservice",
    tags=["AccessCode"],
)
