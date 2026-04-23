"""Persisted feature vectors in db-service (batch lookup + focal upsert)."""

from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import UUID

import httpx

from app.core.config import Settings
from app.core.exceptions import FeatureStoreError
from app.domain.anomaly_types import AnomalyType
from app.domain.log_feature_store import FEATURE_JSON_COLUMN
from app.domain.log_kind import LogKind
from app.integrations.db_service_logs import _db_url
from app.models.schemas import CodeValidationPayload

logger = logging.getLogger(__name__)

_SCOPE_VALUE_TO_UPSERT_KEY: dict[str, str] = {
    scope.value: col for scope, col in FEATURE_JSON_COLUMN.items()
}


def log_kind_from_slices_source(
    source: Literal["visitor_log", "resident_log"],
) -> LogKind:
    """
    Map log slice origin to the ``LogKind`` used for feature-store FK filters.

    Visitor log slices use visitor log ids; resident log slices use resident log ids.
    """
    return LogKind.VISITOR if source == "visitor_log" else LogKind.RESIDENT


async def batch_lookup_engineered_features(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    log_ids: list[UUID],
    anomaly_type: AnomalyType,
    log_kind: LogKind,
) -> list[dict[str, Any]]:
    """
    POST ``/logfeatureengineering/batch-lookup`` and return raw row dicts.

    Raises:
        FeatureStoreError: On transport failure or non-success HTTP status.
    """
    if not log_ids:
        return []
    url = _db_url(
        settings, "api/v1/codeservice/logfeatureengineering/batch-lookup"
    )
    payload = {
        "log_ids": [str(x) for x in log_ids],
        "anomaly_type": anomaly_type.value,
        "log_kind": log_kind.value,
    }
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise FeatureStoreError(
            f"db-service feature batch-lookup failed: {exc}",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise FeatureStoreError(
            f"db-service feature batch-lookup HTTP error: {exc}",
            status_code=502,
        ) from exc
    data = response.json()
    items = data.get("items") or []
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


async def upsert_focal_engineered_features(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    code_validation: CodeValidationPayload,
    anomaly_type: AnomalyType,
    features_by_scope_value: dict[str, dict[str, float]],
    log_kind: LogKind,
    is_anomalous: bool,
) -> None:
    """
    POST ``/logfeatureengineering/upsert`` for the focal log anchor.

    Merges per-scope feature dicts into the JSON columns for keys present in
    ``features_by_scope_value``. Raises :class:`FeatureStoreError` on failure.
    """
    url = _db_url(settings, "api/v1/codeservice/logfeatureengineering/upsert")
    body: dict[str, Any] = {
        "anomaly_type": anomaly_type.value,
        "log_kind": log_kind.value,
        "is_anomalous": is_anomalous,
    }
    if code_validation.visitor_log_id is not None:
        body["visitor_log_id"] = str(code_validation.visitor_log_id)
    else:
        body["resident_log_id"] = str(code_validation.resident_log_id)
    for scope_val, feats in features_by_scope_value.items():
        key = _SCOPE_VALUE_TO_UPSERT_KEY.get(scope_val)
        if key is not None:
            body[key] = feats
    try:
        response = await client.post(url, json=body)
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise FeatureStoreError(
            f"db-service feature upsert failed: {exc}",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise FeatureStoreError(
            f"db-service feature upsert HTTP error: {exc}",
            status_code=502,
        ) from exc
