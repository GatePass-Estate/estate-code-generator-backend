"""Aggregate API v1 routers for the revenue service."""

from fastapi import APIRouter

from app.api.v1.endpoints.ai_features import router as ai_features_router
from app.api.v1.endpoints.checkout import router as checkout_router
from app.api.v1.endpoints.entitlements import router as entitlements_router
from app.api.v1.endpoints.subscriptions import router as subscriptions_router
from app.api.v1.endpoints.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(
    entitlements_router,
    prefix="/entitlements",
    tags=["entitlements"],
)
api_router.include_router(
    ai_features_router,
    prefix="/ai-features",
    tags=["ai-features"],
)
api_router.include_router(
    checkout_router,
    prefix="/checkout",
    tags=["checkout"],
)
api_router.include_router(
    webhooks_router,
    prefix="/webhooks",
    tags=["webhooks"],
)
api_router.include_router(
    subscriptions_router,
    prefix="/subscriptions",
    tags=["subscriptions"],
)
