"""Feature-store column mapping and cohort helpers (no HTTP)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.core.feature_config import active_feature_set_for_scope
from app.domain.scopes import AnalysisScope

logger = logging.getLogger(__name__)

# ``AnalysisScope`` -> JSON column on ``core.logfeatureengineering``.
FEATURE_JSON_COLUMN: dict[AnalysisScope, str] = {
    AnalysisScope.TEMPORAL: "features_temporal",
    AnalysisScope.VISITOR: "features_visitor_specific",
    AnalysisScope.RESIDENT: "features_resident_specific",
    AnalysisScope.SECURITY: "features_security_specific",
    AnalysisScope.ESTATE_WIDE: "features_estate_wide",
}


def previous_anchor_log_ids(
    scope_rows: list[dict[str, Any]],
    focal_record: dict[str, Any],
) -> list[UUID]:
    """
    Collect ``id`` values from ``scope_rows`` except the focal anchor row.

    Non-UUID ids are skipped with a warning. Used to batch-load engineered
    features for the cohort preceding the current validation.
    """
    fid = focal_record.get("id")
    focal_s = None if fid is None else str(fid)
    out: list[UUID] = []
    for r in scope_rows:
        rid = r.get("id")
        if rid is None:
            continue
        if focal_s is not None and str(rid) == focal_s:
            continue
        try:
            out.append(rid if isinstance(rid, UUID) else UUID(str(rid)))
        except ValueError:
            logger.warning("Skipping non-UUID log id %r", rid)
    return out


def historical_vectors_for_scope(
    stored_items: list[dict[str, Any]],
    scope: AnalysisScope,
) -> list[dict[str, float]]:
    """
    Extract the JSON feature blob for ``scope`` from each db-service row.

    Rows marked ``is_anomalous`` (when present) are skipped so they are not
    used as reference vectors. Rows missing the column or with a non-dict
    value are skipped. Floats are coerced for downstream numpy / sklearn use.
    """
    col = FEATURE_JSON_COLUMN[scope]
    vectors: list[dict[str, float]] = []
    for row in stored_items:
        if row.get("is_anomalous") is True:
            continue
        blob = row.get(col)
        if not isinstance(blob, dict):
            continue
        vectors.append({str(k): float(v) for k, v in blob.items()})
    return vectors


def filter_vectors_by_active_keys(
    vectors: list[dict[str, float]],
    active_keys: frozenset[str],
) -> tuple[list[dict[str, float]], int]:
    """
    Keep only vectors whose keys exactly match ``active_keys``.

    Legacy rows with inactive or partial schemas are excluded so sklearn
    preprocessing does not union keys and zero-impute mismatched dimensions.

    Returns:
        ``(matched_vectors, excluded_count)``
    """
    if not active_keys:
        return [], len(vectors)
    matched: list[dict[str, float]] = []
    excluded = 0
    for vector in vectors:
        if frozenset(vector.keys()) == active_keys:
            matched.append(vector)
        else:
            excluded += 1
    if excluded:
        logger.debug(
            "Excluded %s historical vector(s) with schema mismatch "
            "(expected keys=%s)",
            excluded,
            sorted(active_keys),
        )
    return matched, excluded


def historical_vectors_for_scope_matching_active(
    stored_items: list[dict[str, Any]],
    scope: AnalysisScope,
) -> tuple[list[dict[str, float]], int]:
    """
    Load scope vectors and retain only rows matching the active feature schema.
    """
    raw = historical_vectors_for_scope(stored_items, scope)
    active = active_feature_set_for_scope(scope)
    return filter_vectors_by_active_keys(raw, active)
