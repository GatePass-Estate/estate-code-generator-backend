import os

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Imports all the configuration settings for the API service
    """

    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "cache-service Service"
    APP_VERSION: str = "0.0.1"
    APP_DESCRIPTION: str = "cache-service Service for Estace Code Generator "
    ENV: str = os.getenv("ENV", "local")

    # Environment variables for Redis connection (defaulting to localhost for
    # local testing)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "7380"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    )

    # Maximum visitor code validity horizon from creation time
    # (default: 14 days).
    VISITOR_CODE_MAX_VALIDITY_DAYS: int = int(
        os.getenv("VISITOR_CODE_MAX_VALIDITY_DAYS", "14")
    )

    # Maximum span between validity period start and end (default: 7 days).
    VISITOR_CODE_MAX_PERIOD_LENGTH_DAYS: int = int(
        os.getenv("VISITOR_CODE_MAX_PERIOD_LENGTH_DAYS", "7")
    )

    # Scheduler — internal API key shared across services
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")
    # Hour (UTC, 0-23) at which the daily cron runs
    CRON_HOUR: int = int(os.getenv("CRON_HOUR", 0))
    # Full URL of the user-profile-service daily cron endpoint
    USER_PROFILE_CRON_URL: str = os.getenv(
        "USER_PROFILE_CRON_URL",
        "http://user-profile-service:9034/api/v1/internal/cron/daily",
    )

    @field_validator("REDIS_URL", mode="before")
    def assemble_db_url(cls, v, info: ValidationInfo):
        return (
            f"redis://{info.data['REDIS_HOST']}:"
            f"{info.data['REDIS_PORT']}/{info.data['REDIS_DB']}"
        )


settings = Settings()
