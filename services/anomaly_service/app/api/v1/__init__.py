"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints.anomaly import router as anomaly_router

api_router = APIRouter()
api_router.include_router(anomaly_router, prefix="/anomaly", tags=["Anomaly"])
