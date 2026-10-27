"""FastAPI app for the AI service: anomaly, incident, volume APIs."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.libs.http_handler import handler

logger = logging.getLogger("ai-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = httpx.AsyncClient(timeout=30.0)
    handler.set_client(client)
    yield
    await client.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    root_path="/ai",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    """Build OpenAPI schema with bearer auth; relax security on public paths."""
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        routes=app.routes,
        servers=[{"url": "/"}],
    )
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    openapi_schema["security"] = [{"HTTPBearer": []}]
    for path in openapi_schema.get("paths", {}):
        if path in ("/", "/healthz"):
            for method in openapi_schema["paths"][path]:
                openapi_schema["paths"][path][method]["security"] = []
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/")
async def root():
    """Service identity and version for shallow health checks."""
    return JSONResponse(
        content={
            "service": "ai-service",
            "status": "ok",
            "version": settings.APP_VERSION,
        }
    )


@app.get("/healthz", status_code=200)
async def healthz():
    """Liveness probe for orchestrators and load balancers."""
    return JSONResponse(content={"status": "ok"})


app.include_router(api_router, prefix="/api/v1")
