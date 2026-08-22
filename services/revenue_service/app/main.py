"""Revenue service FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings

logger = logging.getLogger("revenue-service")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    root_path="/revenue",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    """
    Build and cache the OpenAPI schema with JWT bearer security.

    Returns:
        dict: The OpenAPI schema for this service.
    """
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
        "OAuth2PasswordBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste your access token here",
        }
    }

    openapi_schema["security"] = [{"OAuth2PasswordBearer": []}]

    for path in openapi_schema["paths"]:
        if path in ("/", "/healthz"):
            for method in openapi_schema["paths"][path]:
                openapi_schema["paths"][path][method]["security"] = []

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/")
async def root():
    """Return a simple service identity probe."""
    return JSONResponse(content={"service": "revenue-service", "status": "ok"})


@app.get("/healthz", status_code=200)
async def health_check():
    """Liveness probe used by orchestration and load balancers."""
    return JSONResponse(content={"status": "ok"})


app.include_router(api_router, prefix="/api/v1")
