"""API v1: anomaly detection, incident intelligence, and volume forecasting."""

from fastapi import APIRouter

from app.api.v1.endpoints.anomaly import router as anomaly_router
from app.api.v1.endpoints.incident_report import router as incident_router
from app.api.v1.endpoints.volume_forecast import (
    router as volume_forecast_router,
)

api_router = APIRouter()
api_router.include_router(anomaly_router, prefix="/anomaly", tags=["Anomaly"])
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
