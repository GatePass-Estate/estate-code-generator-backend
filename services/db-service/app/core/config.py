import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """
    Imports all the configuration settings for the API service
    """

    model_config = SettingsConfigDict(
        env_file=".env.localdocker", extra="ignore"
    )

    APP_NAME: str = "db-service Service"
    APP_VERSION: str = "0.0.1"
    APP_DESCRIPTION: str = "db-service Service for Estate Code Generator "
    ENV: str = os.getenv("ENV", "local")

    # Configuration for the RDB Database
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "estate_code_db")
    DB_PORT: str = os.getenv("DB_PORT", "5445")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_CONFIG: str | None = os.getenv("DB_CONFIG")

    @property
    def db_url(self) -> URL:
        if self.DB_CONFIG:
            return make_url(self.DB_CONFIG)
        return URL.create(
            "postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.DB_HOST,
            port=int(self.DB_PORT),
            database=self.POSTGRES_DB,
        )

    # GCS user documents (profile picture, ID card)
    GOOGLE_APPLICATION_CREDENTIALS: str | None = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    GCS_DOCUMENTS_BUCKET: str = os.getenv(
        "GCS_DOCUMENTS_BUCKET", "gatepass-user-documents-dev"
    )
    GCS_SIGNED_URL_EXPIRY_SECONDS: int = int(
        os.getenv("GCS_SIGNED_URL_EXPIRY_SECONDS", "300")
    )
    GCS_PROFILE_PICTURE_MAX_BYTES: int = int(
        os.getenv("GCS_PROFILE_PICTURE_MAX_BYTES", str(5 * 1024 * 1024))
    )
    GCS_ID_CARD_MAX_BYTES: int = int(
        os.getenv("GCS_ID_CARD_MAX_BYTES", str(10 * 1024 * 1024))
    )
    #: Max characters allowed on an AI marketplace rating comment.
    RATING_COMMENT_MAX_LENGTH: int = int(
        os.getenv("RATING_COMMENT_MAX_LENGTH", "1000")
    )
    #: Align with ai-service ``ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD``.
    ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD: float = 0.74
    #: ``final_score`` at or above this maps to high severity.
    SPATIAL_SEVERITY_HIGH_MIN: float = 0.8


settings = Settings()
