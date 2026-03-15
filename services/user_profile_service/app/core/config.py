import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Imports all the configuration settings for the API service
    """

    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "user-profile-service Service"
    APP_VERSION: str = "0.0.1"
    APP_DESCRIPTION: str = "user-profile-service Service for GatePass"
    ENV: str = os.getenv("ENV", "local")

    # Configuration for the RDB Database
    DB_SERVICE_URL: str = os.getenv("DB_SERVICE_URL")
    BASE_URL: str = os.getenv("BASE_URL")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    LOGIN_EXPIRE_MINUTES: int = int(os.getenv("LOGIN_EXPIRE_MINUTES", 10))
    TOS_VERSION: str = os.getenv("TOS_VERSION", "1.0.0")


settings = Settings()
