import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime config; extend with API keys and DB URLs as the pipeline is implemented."""

    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "anomaly-service"
    APP_VERSION: str = "0.1.0-draft"
    APP_DESCRIPTION: str = "Visit anomaly detection API (draft)"
    ENV: str = os.getenv("ENV", "local")

    DB_SERVICE_URL: str = os.getenv(
        "DB_SERVICE_URL", "http://db-service:9032/"
    )
    USER_PROFILE_SERVICE_URL: str = os.getenv(
        "USER_PROFILE_SERVICE_URL", "http://user-profile-service:9034/"
    )
    CODE_SERVICE_URL: str = os.getenv(
        "CODE_SERVICE_URL", "http://code-service:9033/"
    )


settings = Settings()
