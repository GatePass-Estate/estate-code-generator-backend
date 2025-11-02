from fastapi import APIRouter

from app.api.v1.endpoints.user import router as user_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.estate import router as estate_router
from app.api.v1.endpoints.request import router as request_router

api_router = APIRouter()

api_router.include_router(user_router, prefix="/users", tags=["Users"])

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])

api_router.include_router(estate_router, prefix="/estates", tags=["Estates"])

api_router.include_router(
    request_router, prefix="/requests", tags=["Requests"]
)
