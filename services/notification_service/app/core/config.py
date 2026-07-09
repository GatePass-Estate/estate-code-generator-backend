import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "notification-service"
    APP_VERSION: str = "0.0.1"
    APP_DESCRIPTION: str = "Notification Service for GatePass"
    ENV: str = os.getenv("ENV", "local")

    DB_SERVICE_URL: str = os.getenv("DB_SERVICE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    # Internal API key — shared secret for service-to-service calls
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

    # FCM credentials — full JSON string of the Firebase service account
    FCM_CREDENTIALS_JSON: str = os.getenv("FCM_CREDENTIALS_JSON", "")

    # Notifications older than this (days) are excluded from list/unread-count
    NOTIFICATION_MAX_AGE_DAYS: int = int(
        os.getenv("NOTIFICATION_MAX_AGE_DAYS", 90)
    )

    # Minimum age (days) allowed when calling the purge endpoint
    NOTIFICATION_PURGE_MIN_AGE_DAYS: int = int(
        os.getenv("NOTIFICATION_PURGE_MIN_AGE_DAYS", 90)
    )

    FRONTEND_BASE_URL: str = os.getenv(
        "FRONTEND_BASE_URL", "https://app.gatepassng.com"
    )

    # Email / SMTP configuration
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "GatePass")
    MAIL_SERVER: str = os.getenv("MAIL_SERVER", "")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", 587))
    MAIL_SSL_TLS: bool = os.getenv("MAIL_SSL_TLS", "false").lower() == "true"
    MAIL_STARTTLS: bool = os.getenv("MAIL_STARTTLS", "true").lower() == "true"
    # When true, emails are logged but not actually sent.
    # Set MAIL_DEV_MODE=true in .env during local development.
    MAIL_DEV_MODE: bool = os.getenv("MAIL_DEV_MODE", "true").lower() == "true"


settings = Settings()
