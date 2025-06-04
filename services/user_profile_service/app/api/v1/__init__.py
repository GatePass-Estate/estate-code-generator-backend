from fastapi import APIRouter

from app.api.v1.endpoints.user_profile_service import router as user_router
from app.api.v1.endpoints.auth import router as auth_router

api_router = APIRouter()

api_router.include_router(user_router, prefix="/users", tags=["Users"])

api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
