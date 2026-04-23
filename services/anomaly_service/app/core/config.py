"""Environment-backed settings for the anomaly service."""

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

    DB_SERVICE_URL: str = os.getenv("DB_SERVICE_URL", "http://localhost:9032/")
    SECRET_KEY: str | None = os.getenv("SECRET_KEY")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    USER_PROFILE_SERVICE_URL: str = os.getenv(
        "USER_PROFILE_SERVICE_URL", "http://user-profile-service:9034/"
    )
    CODE_SERVICE_URL: str = os.getenv(
        "CODE_SERVICE_URL", "http://code-service:9033/"
    )
    #: Ensemble score at or above this marks the focal row ``is_anomalous`` in the feature store.
    ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD: float = 0.5


#: Process-wide :class:`Settings` instance (loaded once at import).
settings = Settings()
