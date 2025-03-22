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

    APP_NAME: str = "db-service Service"
    APP_VERSION: str = "0.0.1"
    APP_DESCRIPTION: str = "db-service Service for Estace Code Generator "
    ENV: str = os.getenv("ENV", "local")

    # Configuration for the RDB Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "estate_code_db")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_CONFIG: str = os.getenv(
        "DB_CONFIG",
        f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}",
    )

    @field_validator("DB_CONFIG", mode="before")
    def assemble_db_url(cls, v, info: ValidationInfo):
        return (
            f"postgresql+asyncpg://{info.data['POSTGRES_USER']}:"
            f"{info.data['POSTGRES_PASSWORD']}@{info.data['DB_HOST']}:"
            f"{info.data['DB_PORT']}/{info.data['POSTGRES_DB']}"
        )


settings = Settings()
