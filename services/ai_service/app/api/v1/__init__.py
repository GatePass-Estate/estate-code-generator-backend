"""API v1: visit anomaly detection and incident report intelligence."""

from fastapi import APIRouter

from app.api.v1.endpoints.anomaly import router as anomaly_router
from app.api.v1.endpoints.incident_report import router as incident_router

api_router = APIRouter()
api_router.include_router(anomaly_router, prefix="/anomaly", tags=["Anomaly"])
api_router.include_router(
    incident_router,
    prefix="/incident-reports",
    tags=["Incident reports"],
)
