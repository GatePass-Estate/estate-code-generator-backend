import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from gatepass_scheduler import scheduled_http_job

from app.api.v1 import api_router
from app.core.config import settings

logger = logging.getLogger("cache-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ups_task = asyncio.create_task(
        scheduled_http_job(
            url=settings.USER_PROFILE_CRON_URL,
            internal_api_key=settings.INTERNAL_API_KEY,
            hour=settings.CRON_HOUR,
            name="user-profile-daily-cron",
        )
    )
    revenue_task = asyncio.create_task(
        scheduled_http_job(
            url=settings.REVENUE_CRON_URL,
            internal_api_key=settings.INTERNAL_API_KEY,
            hour=settings.REVENUE_CRON_HOUR,
            name="revenue-daily-expiry",
        )
    )
    logger.info(
        "Scheduler started: user-profile-daily-cron at %02d:00 UTC",
        settings.CRON_HOUR,
    )
    logger.info(
        "Scheduler started: revenue-daily-expiry at %02d:00 UTC",
        settings.REVENUE_CRON_HOUR,
    )
    yield
    for task in (ups_task, revenue_task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    logger.info("Schedulers stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# To enable jwt authentication in swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        routes=app.routes,
        servers=[{"url": "/"}],
    )

    # Add security scheme
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token",
        }
    }

    # Apply security globally
    openapi_schema["security"] = [{"OAuth2PasswordBearer": []}]

    # Remove security requirement from healthz endpoint
    for path in openapi_schema["paths"]:
        if path == "/healthz":
            for method in openapi_schema["paths"][path]:
                openapi_schema["paths"][path][method]["security"] = []

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/healthz", status_code=200)
async def healthz():
    return JSONResponse(content={"status": "ok"})


app.include_router(api_router, prefix="/api/v1")
