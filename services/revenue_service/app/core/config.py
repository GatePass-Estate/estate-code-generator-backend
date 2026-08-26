"""Application settings loaded from environment / .env.localdocker."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the revenue service."""

    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "revenue-service"
    APP_VERSION: str = "0.0.1"
    APP_DESCRIPTION: str = "Revenue Service for GatePass"
    ENV: str = os.getenv("ENV", "local")

    DB_SERVICE_URL: str = os.getenv("DB_SERVICE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    INTERNAL_API_KEY: str = os.getenv("INTERNAL_API_KEY", "")

    RENEWAL_GRACE_PERIOD_DAYS: int = int(
        os.getenv("RENEWAL_GRACE_PERIOD_DAYS", "7")
    )

    # Bounded retries for grant sync + compensation across db-service calls.
    REVENUE_TRANSIENT_RETRY_ATTEMPTS: int = int(
        os.getenv("REVENUE_TRANSIENT_RETRY_ATTEMPTS", "3")
    )
    REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS: float = float(
        os.getenv("REVENUE_TRANSIENT_RETRY_BASE_DELAY_SECONDS", "0.2")
    )

    # Unused in Phase 1 (Paystack stubbed)
    PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY", "")


settings = Settings()
