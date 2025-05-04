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

    @field_validator("REDIS_URL", mode="before")
    def assemble_db_url(cls, v, info: ValidationInfo):
        return (
            f"redis://{info.data['REDIS_HOST']}:"
            f"{info.data['REDIS_PORT']}/{info.data['REDIS_DB']}"
        )


settings = Settings()
