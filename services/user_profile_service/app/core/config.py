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
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    LOGIN_EXPIRE_MINUTES: int = int(os.getenv("LOGIN_EXPIRE_MINUTES", 60))
    SESSION_EXPIRE_DAYS: int = int(os.getenv("SESSION_EXPIRE_DAYS", 30))
    TOS_VERSION: str = os.getenv("TOS_VERSION", "1.0.0")
    TOTP_ENCRYPTION_KEY: str = os.getenv("TOTP_ENCRYPTION_KEY", "")
    # Days before a 2FA-verified session on the same IP is no longer "familiar"
    TWO_FA_FAMILIAR_IP_DAYS: int = int(
        os.getenv("TWO_FA_FAMILIAR_IP_DAYS", 30)
    )
    # Days before 2FA is forced again regardless of IP familiarity
    TWO_FA_FORCE_REAUTH_DAYS: int = int(
        os.getenv("TWO_FA_FORCE_REAUTH_DAYS", 60)
    )
    # Hours a resident must wait between admin reminders on a pending request
    EDIT_REQUEST_REMIND_COOLDOWN_HOURS: int = int(
        os.getenv("EDIT_REQUEST_REMIND_COOLDOWN_HOURS", 24)
    )

    # Notification service
    NOTIFICATION_SERVICE_URL: str = os.getenv("NOTIFICATION_SERVICE_URL", "")
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")
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

    # GCS user documents (profile picture, ID card)
    GCS_PROFILE_PICTURE_MAX_BYTES: int = int(
        os.getenv("GCS_PROFILE_PICTURE_MAX_BYTES", str(5 * 1024 * 1024))
    )
    GCS_ID_CARD_MAX_BYTES: int = int(
        os.getenv("GCS_ID_CARD_MAX_BYTES", str(10 * 1024 * 1024))
    )


settings = Settings()
