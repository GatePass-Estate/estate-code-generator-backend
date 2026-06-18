import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Imports all the configuration settings for the API service
    """

    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "code-service Service"
    APP_VERSION: str = "0.0.1"
    APP_DESCRIPTION: str = "code-service Service for Estace Code Generator "
    ENV: str = os.getenv("ENV", "local")

    # Configuration for the RDB Database
    CACHE_SERVICE_URL: str = os.getenv("CACHE_SERVICE_URL")
    DB_SERVICE_URL: str = os.getenv("DB_SERVICE_URL")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    LOGIN_EXPIRE_MINUTES: int = int(os.getenv("LOGIN_EXPIRE_MINUTES", 10))
    RESIDENT_CODE_EXPIRY_DAYS: int = int(
        os.getenv("RESIDENT_CODE_EXPIRY_DAYS", 30)
    )


settings = Settings()
