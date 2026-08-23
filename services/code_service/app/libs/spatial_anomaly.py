"""Best-effort spatial anomaly trigger after access-code validation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _str_field(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", None) or str(value)


async def trigger_spatial_anomaly_check(
    *,
    anomaly_type: str,
    record: dict,
    log_id: str,
    security_id: str,
    auth_token: str | None,
) -> dict[str, Any] | None:
    """
    Run spatial anomaly analyze after a visitor/resident log is persisted.

    Entitlement is enforced by ai-service. Not subscribed (403) → silent.
    Network or other failures → log and return ``None`` (never raise).

    Returns:
        ``{"prediction_result_id": str, "is_anomalous": bool}`` on success,
        otherwise ``None``.
    """
    estate_id = record.get("estate_id")
    if not estate_id or not log_id:
        return None

    if not auth_token:
        logger.error(
            "Spatial anomaly skipped: missing auth token "
            "estate_id=%s anomaly_type=%s",
            estate_id,
            anomaly_type,
        )
        return None

    ai_base = (settings.AI_SERVICE_URL or "").rstrip("/") + "/"

    code_validation: dict[str, Any] = {
        "user_id": str(record.get("user_id")),
        "security_id": str(security_id),
        "estate_id": str(estate_id),
        "hashed_code": record.get("hashed_code"),
        "valid_until": record.get("valid_until"),
        "is_expired": bool(record.get("is_expired", False)),
        "receiver": anomaly_type,
    }
    if anomaly_type == "visitor":
        code_validation["visitor_log_id"] = str(log_id)
        code_validation["visitor_fullname"] = record.get("visitor_fullname")
        code_validation["relationship_with_resident"] = _str_field(
            record.get("relationship_with_resident")
        )
        code_validation["gender"] = _str_field(record.get("gender"))
    else:
        code_validation["resident_log_id"] = str(log_id)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ai_base}api/v1/spatial-anomaly/analyze/{anomaly_type}",
                json={
                    "code_validation": code_validation,
                    "trigger": "realtime",
                },
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            if response.status_code == 403:
                # Not subscribed / entitlement denied — silent.
                return None
            if response.status_code == 422:
                # Insufficient history / preconditions — soft skip.
                logger.warning(
                    "Spatial anomaly skipped estate_id=%s anomaly_type=%s "
                    "detail=%s",
                    estate_id,
                    anomaly_type,
                    response.text,
                )
                return None
            if response.status_code >= 400:
                logger.error(
                    "Spatial anomaly analyze failed estate_id=%s "
                    "anomaly_type=%s status=%s body=%s",
                    estate_id,
                    anomaly_type,
                    response.status_code,
                    response.text,
                )
                return None

            data = response.json() if response.content else {}
            if not isinstance(data, dict):
                return None
            prediction_result_id = data.get("prediction_result_id")
            is_anomalous = data.get("is_anomalous")
            if prediction_result_id is None or is_anomalous is None:
                logger.error(
                    "Spatial anomaly response missing prediction metadata "
                    "estate_id=%s anomaly_type=%s body=%s",
                    estate_id,
                    anomaly_type,
                    data,
                )
                return None
            return {
                "prediction_result_id": str(prediction_result_id),
                "is_anomalous": bool(is_anomalous),
            }
    except Exception:
        logger.exception(
            "Spatial anomaly trigger failed estate_id=%s anomaly_type=%s",
            estate_id,
            anomaly_type,
        )
        return None
