import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    DB_SERVICE_URL: str = os.getenv("DB_SERVICE_URL", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")


settings = Settings()
