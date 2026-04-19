"""Feature-store column mapping and cohort helpers (no HTTP)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.domain.scopes import AnalysisScope

logger = logging.getLogger(__name__)

# ``AnalysisScope`` -> JSON column on ``core.logfeatureengineering``.
FEATURE_JSON_COLUMN: dict[AnalysisScope, str] = {
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
