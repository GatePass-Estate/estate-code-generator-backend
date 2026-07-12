"""Environment-backed settings for the AI service."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime config for anomaly, incident, and volume-forecast pipelines."""

    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "ai-service"
    APP_VERSION: str = "0.1.0-draft"
    APP_DESCRIPTION: str = (
        "AI service: visit anomaly detection, incident report intelligence "
        "(TF-IDF+NMF topic modelling, payment-gated LLM summaries), and "
        "ARIMA validation-volume forecasting"
    )
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

    #: Optional OpenAI-compatible chat API for incident summarisation.
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str = os.getenv(
        "OPENAI_BASE_URL", "https://api.openai.com"
    )


#: Process-wide :class:`Settings` instance (loaded once at import).
settings = Settings()
