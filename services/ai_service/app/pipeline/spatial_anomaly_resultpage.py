"""
Turn db-service overview data into the spatial-anomaly result-page payload.

This module does not query the database. db-service returns estate counts, a
random 30% sample of non-anomalous prediction JSON, and max feature/scope
values across *all* predictions in the window (anomalous included).

``overview_from_db_payload`` maps those counts onto ``demographic`` and
``evidence_summary``. It then calls ``build_anomaly_overview``, which
averages the sample into spider-plot points, top contributing factors, and
nested scope sub-factors.

Normal behaviour (``normal_value``) always comes from the non-anomalous
sample. ``scale`` is the period max for that feature or scope score.
``percentage`` is ``normal_value / scale * 100``. Spider plot and top
factors share the same top six features, ranked by mean weight.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain.features import (
    DAY_OF_WEEK,
    GUARD_NIGHT_VALIDATIONS,
    GUARD_TOTAL_VALIDATIONS,
    HOUR_OF_DAY,
    IS_WEEKEND,
    NIGHT_VISIT_FLAG,
    RELATIONSHIP_FREQUENCY,
    RELATIONSHIP_TRANSITION,
    RESIDENT_VISIT_FREQUENCY,
    TIME_SINCE_LAST_VISIT,
    VISIT_HOUR_BUCKET,
    VISIT_INTERARRIVAL_TIME,
    VISITOR_TOTAL_VISITS,
    VISITOR_WEEKLY_FREQUENCY,
)
from app.domain.scopes import AnalysisScope
from app.models.spatial_anomaly_resultpage import (
    AnomalyOverview,
    ContributingFactor,
    Demographic,
    EvidenceSummary,
    RatioShare,
    ResultPageOverviewResponse,
    SpiderPlotPoint,
    SubFactor,
)

SPIDER_TOP_N = 6

SCOPE_DESCRIPTIONS = {
    AnalysisScope.VISITOR.value: (
        "Visitor-centred timing, frequency, and relationship patterns."
    ),
    AnalysisScope.RESIDENT.value: (
        "Resident-centred visit timing and frequency patterns."
    ),
    AnalysisScope.SECURITY.value: (
        "Guard validation volume and night-shift patterns."
    ),
    AnalysisScope.ESTATE_WIDE.value: (
        "Estate-wide visit timing, frequency, and validation patterns."
    ),
}

FEATURE_DESCRIPTIONS = {
    HOUR_OF_DAY: "Hour of day when the visit was validated (0-23).",
    DAY_OF_WEEK: "Day of week of the visit (0=Monday through 6=Sunday).",
    IS_WEEKEND: "Whether the visit fell on a weekend (1) or weekday (0).",
    VISIT_HOUR_BUCKET: "Coarse bucket of the visit hour.",
    TIME_SINCE_LAST_VISIT: "Elapsed time since this actor's previous visit.",
    VISIT_INTERARRIVAL_TIME: "Gap between consecutive visits in the cohort.",
    NIGHT_VISIT_FLAG: "Whether the visit occurred during night hours.",
    VISITOR_TOTAL_VISITS: "Lifetime visit count for this visitor.",
    VISITOR_WEEKLY_FREQUENCY: "Average weekly visit rate for this visitor.",
    RESIDENT_VISIT_FREQUENCY: "Average visit rate for this resident.",
    GUARD_TOTAL_VALIDATIONS: "Total validations performed by the guard.",
    GUARD_NIGHT_VALIDATIONS: "Night-hour validations performed by the guard.",
    RELATIONSHIP_FREQUENCY: (
        "How often this resident-visitor relation appears."
    ),
    RELATIONSHIP_TRANSITION: "Whether the stated relationship changed.",
}

_SCOPE_ORDER = [s.value for s in AnalysisScope]


def _unwrap(raw: Any) -> dict[str, Any]:
    """Return the inner prediction dict, or ``raw`` if already unwrapped."""
    if isinstance(raw, dict) and isinstance(raw.get("result"), dict):
        return raw["result"]
    return raw if isinstance(raw, dict) else {}


def _mean(values: list[float]) -> float | None:
    """Arithmetic mean rounded to six decimals, or None if empty."""
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _describe_feature(name: str) -> str:
    """Human-readable copy for a feature key; falls back to the name."""
    return FEATURE_DESCRIPTIONS.get(name, name.replace("_", " ").capitalize())


def _describe_scope(name: str) -> str:
    """Human-readable copy for an analysis scope; falls back to the name."""
    return SCOPE_DESCRIPTIONS.get(name, name.replace("_", " ").capitalize())


def _to_float(value: Any) -> float | None:
    """Parse a numeric JSON value; return None when missing or invalid."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scale_fields(
    normal: float | None, raw_max: float | None
) -> tuple[float | None, float | None]:
    """
    Pair a sample mean with period-max scale and percentage of scale.

    ``scale`` is the max of that feature or scope across all predictions
    in the window. ``percentage`` is ``normal / scale * 100``.
    """
    if raw_max is None:
        return None, None
    scale = round(float(raw_max), 6)
    if normal is None:
        return scale, None
    if scale == 0:
        return scale, 0.0
    return scale, round(100.0 * normal / scale, 2)


def build_anomaly_overview(
    sample: list[dict[str, Any]],
    *,
    feature_max_values: dict[str, float] | None = None,
    scope_max_scores: dict[str, float] | None = None,
    scope_feature_max_values: dict[str, dict[str, float]] | None = None,
) -> AnomalyOverview:
    """
    Average a non-anomalous sample into spider-plot and factor sections.

    Walks ``transparency.scopes`` on each sample payload. Feature values
    and weights are collected globally (spider plot) and per scope
    (contributing factors). Scope ``score`` is averaged into each
    factor's ``normal_value``.

    Ranking uses mean weight, highest first; features with a null mean
    weight sort last, then reverse feature name. ``spider_plot`` and
    ``top_contributing_factors`` are the same top
    ``SPIDER_TOP_N`` (6) points.

    Scale maps are period maxima from *all* predictions, not the sample:
    ``feature_max_values`` for spider points, ``scope_max_scores`` for
    factor-level scores, ``scope_feature_max_values`` for sub-factors.

    Arguments:
        sample: Non-anomalous prediction JSON (wrapped or unwrapped).
        feature_max_values: Global max feature value in the window.
        scope_max_scores: Max scope score in the window.
        scope_feature_max_values: Max feature value per scope.

    Returns:
        ``AnomalyOverview`` with spider plot, top factors, and nested
        contributing factors.
    """
    # 1. Collect sample values: scope scores, per-scope features, and
    #    global features. Means of these lists are expected-normal.
    scope_scores: dict[str, list[float]] = defaultdict(list)
    scope_feats: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: {"values": [], "weights": []})
    )
    global_feats: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"values": [], "weights": []}
    )

    for raw in sample:
        payload = _unwrap(raw)
        scopes = (payload.get("transparency") or {}).get("scopes") or []
        if not isinstance(scopes, list):
            continue
        for detail in scopes:
            if not isinstance(detail, dict):
                continue
            scope = detail.get("scope")
            if not isinstance(scope, str) or not scope:
                continue
            score = _to_float(detail.get("score"))
            if score is not None:
                # mean → contributing_factors[].normal_value
                scope_scores[scope].append(score)
            for fc in detail.get("feature_contributions") or []:
                if not isinstance(fc, dict):
                    continue
                name = fc.get("feature_name")
                if not isinstance(name, str) or not name:
                    continue
                value = _to_float(fc.get("value"))
                weight = _to_float(fc.get("weight"))
                if value is not None:
                    # per-scope mean → sub_factors[].normal_value
                    # global mean → spider_plot[].normal_value
                    scope_feats[scope][name]["values"].append(value)
                    global_feats[name]["values"].append(value)
                if weight is not None:
                    # global mean rank → spider_plot / top factors
                    scope_feats[scope][name]["weights"].append(weight)
                    global_feats[name]["weights"].append(weight)

    # 2. Average globally, attach period-max scale, rank by weight, keep
    #    the top six for spider_plot and top_contributing_factors.
    spider_points: list[SpiderPlotPoint] = []
    feature_max_values = feature_max_values or {}
    scope_max_scores = scope_max_scores or {}
    scope_feature_max_values = scope_feature_max_values or {}
    for name, buckets in global_feats.items():
        normal = _mean(buckets["values"])
        scale, pct = _scale_fields(normal, feature_max_values.get(name))
        spider_points.append(
            SpiderPlotPoint(
                feature_name=name,
                description=_describe_feature(name),
                weight=_mean(buckets["weights"]),
                normal_value=normal,
                scale=scale,
                percentage=pct,
            )
        )
    spider_points.sort(
        key=lambda p: (
            p.weight is not None,
            p.weight if p.weight is not None else 0.0,
            p.feature_name,
        ),
        reverse=True,
    )
    top = spider_points[:SPIDER_TOP_N]

    # 3. Average per analysis scope. Sub-factors use that scope's feature
    #    max; the factor itself uses the max scope score. Known scopes
    #    keep canonical order; any others append alphabetically.
    factors: list[ContributingFactor] = []
    seen: set[str] = set()
    ordered_scopes = list(_SCOPE_ORDER) + sorted(
        k for k in scope_feats if k not in _SCOPE_ORDER
    )
    for scope in ordered_scopes:
        feats = scope_feats.get(scope)
        if not feats or scope in seen:
            continue
        seen.add(scope)
        scope_maxes = scope_feature_max_values.get(scope) or {}
        sub_factors = []
        for fname, buckets in sorted(feats.items()):
            normal = _mean(buckets["values"])
            scale, pct = _scale_fields(normal, scope_maxes.get(fname))
            sub_factors.append(
                SubFactor(
                    feature_name=fname,
                    description=_describe_feature(fname),
                    normal_value=normal,
                    weight=_mean(buckets["weights"]),
                    scale=scale,
                    percentage=pct,
                )
            )
        weights = [s.weight for s in sub_factors if s.weight is not None]
        scope_normal = _mean(scope_scores.get(scope, []))
        scale, pct = _scale_fields(scope_normal, scope_max_scores.get(scope))
        factors.append(
            ContributingFactor(
                name=scope,
                description=_describe_scope(scope),
                normal_value=scope_normal,
                weight=_mean(weights) if weights else None,
                scale=scale,
                percentage=pct,
                sub_factors=sub_factors,
            )
        )

    return AnomalyOverview(
        spider_plot=top,
        top_contributing_factors=top,
        contributing_factors=factors,
    )


def _ratio_share(count: int, whole: int) -> RatioShare:
    """Count plus that count as a percentage of ``whole`` (0 if empty)."""
    pct = round(100.0 * count / whole, 2) if whole else 0.0
    return RatioShare(count=count, percentage=pct)


def overview_from_db_payload(
    data: dict[str, Any],
) -> ResultPageOverviewResponse:
    """
    Map a db-service overview dict onto the public result-page payload.

    Counts pass through with light coercion. ``total_users`` is
    resident-side users plus unique guests (not subscription seats).
    ``ratio`` percentages use guest + resident + security as the
    denominator. ``normal_sample`` and the three max maps are sanitized
    then handed to ``build_anomaly_overview``.

    Arguments:
        data: Raw overview JSON from db-service (estate identity,
            counts, ``normal_sample``, ``feature_max_values``,
            ``scope_max_scores``, ``scope_feature_max_values``).

    Returns:
        ``ResultPageOverviewResponse`` with demographic, evidence
        summary, and anomaly overview.
    """
    # 1. Coerce instance counts and demographic role counts from SQL.
    anom_res = int(data.get("total_anomalous_residents_instances") or 0)
    anom_vis = int(data.get("total_anomalous_visitors_instances") or 0)
    guests = int(data.get("total_guests") or 0)
    residents = int(data.get("resident_count") or 0)
    security = int(data.get("security_count") or 0)
    whole = guests + residents + security  # ratio percentage denominator

    # 2. Sanitize the 30% non-anomalous sample and period-max maps.
    sample = data.get("normal_sample") or []
    if not isinstance(sample, list):
        sample = []
    feature_max = data.get("feature_max_values") or {}
    scope_max = data.get("scope_max_scores") or {}
    scope_feat_max = data.get("scope_feature_max_values") or {}
    if not isinstance(feature_max, dict):
        feature_max = {}
    if not isinstance(scope_max, dict):
        scope_max = {}
    if not isinstance(scope_feat_max, dict):
        scope_feat_max = {}

    # 3. Assemble demographic + evidence, then average the sample into
    #    spider_plot / top_contributing_factors / contributing_factors.
    return ResultPageOverviewResponse(
        demographic=Demographic(
            estate_name=str(data.get("estate_name") or ""),
            state=data.get("state"),
            country=data.get("country"),
            total_users=residents + guests,  # not paid seats
            total_guests=guests,
            ratio={
                "guest": _ratio_share(guests, whole),
                "resident": _ratio_share(residents, whole),
                "security": _ratio_share(security, whole),
            },
            total_anomalous_instances=int(
                data.get("total_anomalous_instances") or anom_res + anom_vis
            ),
            total_high_risk_instances=int(
                data.get("total_high_risk_instances") or 0
            ),
        ),
        evidence_summary=EvidenceSummary(
            total_anomalous_residents_instances=anom_res,
            total_anomalous_visitors_instances=anom_vis,
        ),
        anomaly_overview=build_anomaly_overview(
            [x for x in sample if isinstance(x, dict)],
            feature_max_values={
                str(k): float(v)
                for k, v in feature_max.items()
                if isinstance(v, (int, float))
            },
            scope_max_scores={
                str(k): float(v)
                for k, v in scope_max.items()
                if isinstance(v, (int, float))
            },
            scope_feature_max_values={
                str(sk): {
                    str(fk): float(fv)
                    for fk, fv in (sv or {}).items()
                    if isinstance(fv, (int, float))
                }
                for sk, sv in scope_feat_max.items()
                if isinstance(sv, dict)
            },
        ),
    )
