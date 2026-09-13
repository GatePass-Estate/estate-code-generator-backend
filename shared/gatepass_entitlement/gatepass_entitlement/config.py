"""Environment settings for catalog entitlement keys."""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    MAX_ACTIVE_USERS_KEY: str = os.getenv(
        "MAX_ACTIVE_USERS_KEY", "max_active_users"
    )
    EXTENDED_HISTORICAL_RECORD_KEY: str = os.getenv(
        "EXTENDED_HISTORICAL_RECORD_KEY", "extended_historical_record"
    )
    ACCESS_ANOMALY_DETECTION_TIER_1_KEY: str = os.getenv(
        "ACCESS_ANOMALY_DETECTION_TIER_1_KEY",
        "access_anomaly_detection_tier_1",
    )
    ACCESS_ANOMALY_DETECTION_TIER_2_KEY: str = os.getenv(
        "ACCESS_ANOMALY_DETECTION_TIER_2_KEY",
        "access_anomaly_detection_tier_2",
    )
    ACCESS_ANOMALY_DETECTION_TIER_3_KEY: str = os.getenv(
        "ACCESS_ANOMALY_DETECTION_TIER_3_KEY",
        "access_anomaly_detection_tier_3",
    )
    INCIDENT_REPORT_SUMMARY_TIER_1_KEY: str = os.getenv(
        "INCIDENT_REPORT_SUMMARY_TIER_1_KEY",
        "incident_report_summary_tier_1",
    )
    INCIDENT_REPORT_SUMMARY_TIER_2_KEY: str = os.getenv(
        "INCIDENT_REPORT_SUMMARY_TIER_2_KEY",
        "incident_report_summary_tier_2",
    )
    INCIDENT_REPORT_SUMMARY_TIER_3_KEY: str = os.getenv(
        "INCIDENT_REPORT_SUMMARY_TIER_3_KEY",
        "incident_report_summary_tier_3",
    )


settings = Settings()
