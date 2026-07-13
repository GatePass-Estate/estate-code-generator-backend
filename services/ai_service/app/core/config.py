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

    # --- Spatial K-means detector (app/pipeline/spatial_anomaly_models/kmeans_model.py) ---
    #: Upper bound on K-means clusters (actual = min of this and history size).
    SPATIAL_KMEANS_MAX_CLUSTERS: int = 8
    #: Fixed seed so repeated fits on the same history are deterministic.
    SPATIAL_KMEANS_RANDOM_STATE: int = 42
    #: Percentile of historical min-centroid distances used as the focal denominator.
    SPATIAL_KMEANS_HIST_DISTANCE_PERCENTILE: float = 95.0

    # --- Spatial DBSCAN detector (app/pipeline/spatial_anomaly_models/dbscan_model.py) ---
    #: Neighbourhood radius used when history is too small to derive one from data.
    SPATIAL_DBSCAN_FALLBACK_EPS: float = 0.75
    #: Lower bound on DBSCAN ``min_samples``.
    SPATIAL_DBSCAN_MIN_SAMPLES_FLOOR: int = 2
    #: Upper bound on DBSCAN ``min_samples`` (actual = clamped by history size).
    SPATIAL_DBSCAN_MIN_SAMPLES_CAP: int = 5
    #: Score for an in-cluster focal when no historical noise exists.
    SPATIAL_DBSCAN_INCLUSTER_BASELINE: float = 0.05
    #: Base term of the distance-to-noise blend for an in-cluster focal.
    SPATIAL_DBSCAN_NOISE_BLEND_BASE: float = 0.15
    #: Scale term of the distance-to-noise blend for an in-cluster focal.
    SPATIAL_DBSCAN_NOISE_BLEND_SCALE: float = 0.85

    # --- Spatial LOF detector (app/pipeline/spatial_anomaly_models/lof_model.py) ---
    #: Upper bound on LOF neighbours (actual = clamped to history size - 1).
    SPATIAL_LOF_MAX_NEIGHBORS: int = 20
    #: sklearn ``LocalOutlierFactor`` contamination ("auto" or a float in (0, 0.5]).
    SPATIAL_LOF_CONTAMINATION: float | str = "auto"
    #: Minimum score floor for an inlier focal.
    SPATIAL_LOF_INLIER_BASELINE: float = 0.05
    #: Maximum score an inlier focal can reach (below the anomalous band).
    SPATIAL_LOF_INLIER_MAX: float = 0.5
    #: How strongly the relative decision-function gap lifts an inlier score.
    SPATIAL_LOF_INLIER_UPLIFT_SCALE: float = 0.45

    #: Temporal (Matrix Profile) discord score at or above this flags ``is_anomalous``.
    TEMPORAL_ANOMALY_SCORE_THRESHOLD: float = 0.5
    #: Matrix Profile subsequence length in days (default: one week).
    TEMPORAL_SUBSEQUENCE_WINDOW_DAYS: int = 7
    #: History must span at least this many subsequence windows or a 422 is returned.
    TEMPORAL_MIN_HISTORY_WINDOW_MULTIPLE: int = 3

    #: Optional OpenAI-compatible chat API for incident summarisation.
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str = os.getenv(
        "OPENAI_BASE_URL", "https://api.openai.com"
    )


#: Process-wide :class:`Settings` instance (loaded once at import).
settings = Settings()
