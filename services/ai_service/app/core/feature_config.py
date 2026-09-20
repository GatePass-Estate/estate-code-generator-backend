"""
Active feature sets per analysis scope and human-readable labels.

Inactive features remain in ``app.domain.features`` and pipeline helpers for
legacy stored rows and future reuse; only keys listed in ``ACTIVE_FEATURES``
are engineered at runtime and used to filter historical vectors (exact-key
match).
"""

from __future__ import annotations

from app.domain import features as feat
from app.domain.scopes import AnalysisScope

# Retired from active scoring but preserved in code and stored JSON.
INACTIVE_FEATURES: frozenset[str] = frozenset(
    {
        feat.VISITOR_TOTAL_VISITS,
        feat.GUARD_TOTAL_VALIDATIONS,
        feat.GUARD_NIGHT_VALIDATIONS,
        feat.TIME_SINCE_LAST_VISIT,
        feat.RELATIONSHIP_FREQUENCY,
    }
)

# Focal clock/calendar features — slice-invariant, scored once in TEMPORAL.
_TEMPORAL_FEATURES: tuple[str, ...] = (
    feat.HOUR_OF_DAY,
    feat.DAY_OF_WEEK,
    feat.IS_WEEKEND,
    feat.VISIT_HOUR_BUCKET,
    feat.NIGHT_VISIT_FLAG,
)

ACTIVE_FEATURES: dict[AnalysisScope, tuple[str, ...]] = {
    AnalysisScope.TEMPORAL: _TEMPORAL_FEATURES,
    AnalysisScope.VISITOR: (
        feat.VISITOR_TIME_SINCE_LAST_VISIT,
        feat.VISIT_INTERARRIVAL_TIME,
        feat.VISITOR_WEEKLY_FREQUENCY,
        feat.RELATIONSHIP_TRANSITION,
    ),
    AnalysisScope.RESIDENT: (
        feat.RESIDENT_TIME_SINCE_LAST_VISIT,
        feat.VISIT_INTERARRIVAL_TIME,
        feat.RESIDENT_VISIT_FREQUENCY,
    ),
    AnalysisScope.SECURITY: (
        feat.GUARD_NIGHT_VALIDATION_FREQUENCY,
        feat.GUARD_NIGHT_VALIDATION_SHARE,
    ),
    AnalysisScope.ESTATE_WIDE: (
        feat.VISIT_INTERARRIVAL_TIME,
        feat.RESIDENT_TIME_SINCE_LAST_VISIT,
        feat.RESIDENT_VISIT_FREQUENCY,
        feat.VISITOR_WEEKLY_FREQUENCY,
        feat.GUARD_NIGHT_VALIDATION_FREQUENCY,
        feat.GUARD_NIGHT_VALIDATION_SHARE,
    ),
}

FEATURE_LABELS: dict[str, str] = {
    feat.HOUR_OF_DAY: "Hour of the Day",
    feat.DAY_OF_WEEK: "Day of the Week",
    feat.IS_WEEKEND: "Weekend Visit",
    feat.VISIT_HOUR_BUCKET: "Visit Hour Bucket",
    feat.TIME_SINCE_LAST_VISIT: "Time Since Last Visit",
    feat.VISITOR_TIME_SINCE_LAST_VISIT: "Visitor Time Since Last Visit",
    feat.RESIDENT_TIME_SINCE_LAST_VISIT: "Resident Time Since Last Visit",
    feat.VISIT_INTERARRIVAL_TIME: "Visit Interarrival Time",
    feat.NIGHT_VISIT_FLAG: "Night Visit",
    feat.VISITOR_TOTAL_VISITS: "Visitor Total Visits",
    feat.VISITOR_WEEKLY_FREQUENCY: "Visitor Weekly Frequency",
    feat.RESIDENT_VISIT_FREQUENCY: "Resident Visit Frequency",
    feat.GUARD_TOTAL_VALIDATIONS: "Guard Total Validations",
    feat.GUARD_NIGHT_VALIDATIONS: "Guard Night Validations",
    feat.GUARD_NIGHT_VALIDATION_FREQUENCY: "Guard Night Validation Frequency",
    feat.GUARD_NIGHT_VALIDATION_SHARE: "Guard Night Validation Share",
    feat.RELATIONSHIP_FREQUENCY: "Relationship Frequency",
    feat.RELATIONSHIP_TRANSITION: "Relationship Transition",
}


def active_features_for_scope(scope: AnalysisScope) -> tuple[str, ...]:
    """Ordered active feature keys for ``scope``."""
    return ACTIVE_FEATURES[scope]


def active_feature_set_for_scope(scope: AnalysisScope) -> frozenset[str]:
    """Active feature keys as a set (for historical-vector matching)."""
    return frozenset(ACTIVE_FEATURES[scope])


SCOPE_LABELS: dict[str, str] = {
    AnalysisScope.TEMPORAL.value: "Temporal",
    AnalysisScope.VISITOR.value: "Visitor",
    AnalysisScope.RESIDENT.value: "Resident",
    AnalysisScope.SECURITY.value: "Security",
    AnalysisScope.ESTATE_WIDE.value: "Estate Wide",
}


def feature_label(feature_name: str) -> str:
    """Human-readable label; falls back to title-cased key."""
    if feature_name in FEATURE_LABELS:
        return FEATURE_LABELS[feature_name]
    return feature_name.replace("_", " ").title()


def scope_label(scope_name: str) -> str:
    """Short human-readable scope label; falls back to title-cased key."""
    if scope_name in SCOPE_LABELS:
        return SCOPE_LABELS[scope_name]
    return scope_name.replace("_", " ").title()


def is_active_feature(feature_name: str) -> bool:
    """True when ``feature_name`` is active in at least one scope."""
    return feature_name not in INACTIVE_FEATURES and any(
        feature_name in keys for keys in ACTIVE_FEATURES.values()
    )
