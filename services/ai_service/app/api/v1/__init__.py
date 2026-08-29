"""API v1: anomaly, incident, volume forecast, and AI marketplace."""

from fastapi import APIRouter

from app.api.v1.endpoints.incident_report import router as incident_router
from app.api.v1.endpoints.ai_market_place import (
    router as ai_market_place_router,
)
from app.api.v1.endpoints.spatial_anomaly import (
    router as spatial_anomaly_router,
)
from app.api.v1.endpoints.temporal_anomaly import (
    router as temporal_anomaly_router,
)
from app.api.v1.endpoints.volume_forecast import (
    router as volume_forecast_router,
)

api_router = APIRouter()
api_router.include_router(
    spatial_anomaly_router,
    prefix="/spatial-anomaly",
    tags=["Spatial Anomaly"],
)
api_router.include_router(
    temporal_anomaly_router,
    prefix="/temporal-anomaly",
    tags=["Temporal Anomaly (Matrix Profile)"],
)
api_router.include_router(
    incident_router,
    prefix="/incident-reports",
    tags=["Incident reports (TF-IDF/NMF + paid LLM)"],
)
api_router.include_router(
    volume_forecast_router,
    prefix="/volume-forecast",
    tags=["Volume forecast (ARIMA)"],
)
api_router.include_router(
    ai_market_place_router,
    prefix="/ai-marketplace",
    tags=["AI Marketplace"],
)
