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

from app.core.scope_config import scopes_for_anomaly_type
from app.domain.anomaly_types import AnomalyType
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
    CaseAnomalyOverview,
    CaseContributingFactor,
    CaseResultsResponse,
    CaseSpiderPlotPoint,
    CaseSubFactor,
    ContributingFactor,
    Demographic,
    EvidenceSummary,
    RatioShare,
    ResultPageOverviewResponse,
    Severity,
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


def _severity_of(score: float | None) -> Severity | None:
    """Map final_score onto low / medium / high."""
    if score is None:
        return None
    if score >= 0.8:
        return Severity.HIGH
    if score >= 0.5:
        return Severity.MEDIUM
    return Severity.LOW


def _float_map(raw: Any) -> dict[str, float]:
    """Keep numeric dict entries as floats."""
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): float(v) for k, v in raw.items() if isinstance(v, (int, float))
    }


def _scope_float_map(raw: Any) -> dict[str, dict[str, float]]:
    """Keep nested numeric dict entries as floats."""
    if not isinstance(raw, dict):
        return {}
    return {
        str(sk): _float_map(sv)
        for sk, sv in raw.items()
        if isinstance(sv, dict)
    }


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
    spider_limit: int | None = SPIDER_TOP_N,
) -> AnomalyOverview:
    """
    Average a non-anomalous sample into spider-plot and factor sections.

    Walks ``transparency.scopes`` on each sample payload. Feature values
    and weights are collected globally (spider plot) and per scope
    (contributing factors). Scope ``score`` is averaged into each
    factor's ``normal_value``.

    Ranking uses mean weight, highest first; features with a null mean
    weight sort last, then reverse feature name. ``spider_plot`` and
    ``top_contributing_factors`` are the same top ``spider_limit``
    points (default ``SPIDER_TOP_N`` / 6). Pass ``spider_limit=None``
    to keep every ranked feature. ``contributing_factors`` always lists
    all four analysis scopes in canonical order. Sub-factors are the
    union of sample features and period-max keys for that scope.

    Scale maps are period maxima from *all* predictions, not the sample:
    ``feature_max_values`` for spider points, ``scope_max_scores`` for
    factor-level scores, ``scope_feature_max_values`` for sub-factors.

    Arguments:
        sample: Non-anomalous prediction JSON (wrapped or unwrapped).
        feature_max_values: Global max feature value in the window.
        scope_max_scores: Max scope score in the window.
        scope_feature_max_values: Max feature value per scope.
        spider_limit: How many ranked features to keep; ``None`` keeps
            the full ranked list.

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
    top = (
        spider_points if spider_limit is None else spider_points[:spider_limit]
    )

    # 3. Average per analysis scope. First-level always includes all four
    #    known scopes (empty sample still yields four sections). Extra
    #    unknown scopes from the sample append alphabetically.
    factors: list[ContributingFactor] = []
    seen: set[str] = set()
    ordered_scopes = list(_SCOPE_ORDER) + sorted(
        k for k in scope_feats if k not in _SCOPE_ORDER
    )
    for scope in ordered_scopes:
        if scope in seen:
            continue
        seen.add(scope)
        feats = scope_feats.get(scope) or {}
        scope_maxes = scope_feature_max_values.get(scope) or {}
        # Sample means plus period-max keys so a scope is not empty when
        # the 30% draw missed it but the window still has that scope.
        feat_names = sorted(set(feats) | set(scope_maxes))
        sub_factors = []
        for fname in feat_names:
            buckets = feats.get(fname) or {
                "values": [],
                "weights": [],
            }
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
            feature_max_values=_float_map(feature_max),
            scope_max_scores=_float_map(scope_max),
            scope_feature_max_values=_scope_float_map(scope_feat_max),
        ),
    )


def _instance_maps(
    raw: dict[str, Any],
) -> tuple[dict[str, float], dict[str, float], dict[str, dict[str, float]]]:
    """Feature values, scope scores, and per-scope features for one payload."""
    payload = _unwrap(raw)
    global_vals: dict[str, float] = {}
    scope_scores: dict[str, float] = {}
    scope_feats: dict[str, dict[str, float]] = {}
    scopes = (payload.get("transparency") or {}).get("scopes") or []
    if not isinstance(scopes, list):
        return global_vals, scope_scores, scope_feats
    for detail in scopes:
        if not isinstance(detail, dict):
            continue
        scope = detail.get("scope")
        if not isinstance(scope, str) or not scope:
            continue
        score = _to_float(detail.get("score"))
        if score is not None:
            # → contributing_factors[].instance_value
            scope_scores[scope] = score
        feat_store = scope_feats.setdefault(scope, {})
        for fc in detail.get("feature_contributions") or []:
            if not isinstance(fc, dict):
                continue
            name = fc.get("feature_name")
            if not isinstance(name, str) or not name:
                continue
            value = _to_float(fc.get("value"))
            if value is None:
                continue
            # per-scope → sub_factors[].instance_value
            feat_store[name] = value
            # global max across scopes → spider_plot[].instance_value
            prev = global_vals.get(name)
            global_vals[name] = value if prev is None else max(prev, value)
    return global_vals, scope_scores, scope_feats


def _anomaly_type_of(
    instance: dict[str, Any],
    prediction_type: str | None = None,
) -> AnomalyType | None:
    """Resolve ``AnomalyType`` from stored result JSON or row type."""
    payload = _unwrap(instance)
    raw = payload.get("anomaly_type")
    # Prefer the flag stored on the prediction JSON (same as analyze).
    if isinstance(raw, str) and raw:
        try:
            return AnomalyType(raw)
        except ValueError:
            pass
    # Fallback: db-service PredictionType enum on the row.
    if prediction_type == "ResidentAnomalyRealtime":
        return AnomalyType.RESIDENT
    if prediction_type == "VisitorAnomalyRealtime":
        return AnomalyType.VISITOR
    return None


def _case_factor_scopes(
    instance: dict[str, Any],
    *,
    prediction_type: str | None = None,
) -> list[str]:
    """
    Scopes to emit for this case.

    Same resolver as spatial analyze: ``scopes_for_anomaly_type``.
    Unknown type falls back to all four scopes (first-level set).
    """
    anomaly_type = _anomaly_type_of(instance, prediction_type)
    if anomaly_type is None:
        # Unknown type: same four sections as first-level overview.
        return list(_SCOPE_ORDER)
    # Visitor → all four; resident → drop visitor_specific.
    return [s.value for s in scopes_for_anomaly_type(anomaly_type)]


def build_case_anomaly_overview(
    instance: dict[str, Any],
    sample: list[dict[str, Any]],
    *,
    feature_max_values: dict[str, float] | None = None,
    scope_max_scores: dict[str, float] | None = None,
    scope_feature_max_values: dict[str, dict[str, float]] | None = None,
    prediction_type: str | None = None,
) -> CaseAnomalyOverview:
    """
    Overlay one prediction on expected-normal spider and factor charts.

    Expected-normal values come from ``build_anomaly_overview`` on the
    30% non-anomalous sample. Instance values come from this prediction.
    Scale is the period max (all predictions). Percentages are value /
    scale * 100. Spider ranking walks the full sample-ranked list and
    keeps only features that this instance actually has, up to
    ``SPIDER_TOP_N``. Remaining slots, if any, are filled from other
    instance features. Contributing-factor sections use
    ``scopes_for_anomaly_type`` for this prediction's type (visitor:
    all four; resident: omit visitor-specific). When the sample is
    empty, spider ranking uses the instance itself and ``normal_value``
    is left unset.

    Arguments:
        instance: Selected prediction JSON (wrapped or unwrapped).
        sample: Non-anomalous sample for expected-normal behaviour.
        feature_max_values: Global max feature value in the window.
        scope_max_scores: Max scope score in the window.
        scope_feature_max_values: Max feature value per scope.
        prediction_type: Row ``prediction_type`` when ``anomaly_type``
            is missing from the stored result JSON.

    Returns:
        Case spider plot (normal + instance + max) and contributing
        factors (instance + max).
    """
    feature_max_values = feature_max_values or {}
    scope_max_scores = scope_max_scores or {}
    scope_feature_max_values = scope_feature_max_values or {}
    # 1. Instance maps: global feature values, scope scores, per-scope
    #    features. Expected-normal is the first-level sample overview
    #    (full ranked list). Empty sample → rank from this instance.
    inst_g, inst_s, inst_sf = _instance_maps(instance)
    normal = build_anomaly_overview(
        sample,
        feature_max_values=feature_max_values,
        scope_max_scores=scope_max_scores,
        scope_feature_max_values=scope_feature_max_values,
        spider_limit=None,
    )
    use_instance_as_rank = not normal.spider_plot
    rank_overview = (
        build_anomaly_overview(
            [instance],
            feature_max_values=feature_max_values,
            scope_max_scores=scope_max_scores,
            scope_feature_max_values=scope_feature_max_values,
            spider_limit=None,
        )
        if use_instance_as_rank
        else normal
    )

    # 2. Spider: walk sample rank, skip features this instance lacks,
    #    keep up to SPIDER_TOP_N. Fill leftovers from instance-only
    #    features so the top six never have a null instance_value.
    spider: list[CaseSpiderPlotPoint] = []
    seen: set[str] = set()
    for p in rank_overview.spider_plot:
        inst = inst_g.get(p.feature_name)
        if inst is None:
            continue
        _, inst_pct = _scale_fields(inst, p.scale)
        spider.append(
            CaseSpiderPlotPoint(
                feature_name=p.feature_name,
                description=p.description,
                weight=p.weight,
                normal_value=None if use_instance_as_rank else p.normal_value,
                instance_value=inst,
                scale=p.scale,
                percentage=None if use_instance_as_rank else p.percentage,
                instance_percentage=inst_pct,
            )
        )
        seen.add(p.feature_name)
        if len(spider) >= SPIDER_TOP_N:
            break
    if len(spider) < SPIDER_TOP_N:
        leftover = sorted(
            (n for n, v in inst_g.items() if n not in seen and v is not None),
            reverse=True,
        )
        for name in leftover:
            inst = inst_g[name]
            scale, inst_pct = _scale_fields(inst, feature_max_values.get(name))
            spider.append(
                CaseSpiderPlotPoint(
                    feature_name=name,
                    description=_describe_feature(name),
                    weight=None,
                    normal_value=None,
                    instance_value=inst,
                    scale=scale,
                    percentage=None,
                    instance_percentage=inst_pct,
                )
            )
            if len(spider) >= SPIDER_TOP_N:
                break

    # 3. Contributing factors: sections from scopes_for_anomaly_type
    #    (not the sample). Overlay instance scores; skip sub-factors
    #    this instance does not have, then append remaining instance
    #    features for that scope.
    factor_by_name = {f.name: f for f in rank_overview.contributing_factors}
    factors: list[CaseContributingFactor] = []
    for scope in _case_factor_scopes(
        instance, prediction_type=prediction_type
    ):
        src = factor_by_name.get(scope)
        inst_score = inst_s.get(scope)
        inst_feats = inst_sf.get(scope) or {}
        raw_max = src.scale if src is not None else scope_max_scores.get(scope)
        scale, pct = _scale_fields(inst_score, raw_max)
        src_subs = src.sub_factors if src is not None else []
        period_feat_max = scope_feature_max_values.get(scope) or {}
        subs: list[CaseSubFactor] = []
        seen_sub: set[str] = set()
        for s in src_subs:
            inst_v = inst_feats.get(s.feature_name)
            if inst_v is None:
                # Sample listed this feature; this instance did not.
                continue
            _s_scale, s_pct = _scale_fields(inst_v, s.scale)
            subs.append(
                CaseSubFactor(
                    feature_name=s.feature_name,
                    description=s.description,
                    instance_value=inst_v,
                    scale=s.scale,
                    percentage=s_pct,
                )
            )
            seen_sub.add(s.feature_name)
        # Instance features not in the sample ranking for this scope.
        for fname in sorted(inst_feats):
            if fname in seen_sub:
                continue
            inst_v = inst_feats[fname]
            s_scale, s_pct = _scale_fields(inst_v, period_feat_max.get(fname))
            subs.append(
                CaseSubFactor(
                    feature_name=fname,
                    description=_describe_feature(fname),
                    instance_value=inst_v,
                    scale=s_scale,
                    percentage=s_pct,
                )
            )
        factors.append(
            CaseContributingFactor(
                name=scope,
                description=(
                    src.description
                    if src is not None
                    else _describe_scope(scope)
                ),
                instance_value=inst_score,
                scale=scale,
                percentage=pct,
                sub_factors=subs,
            )
        )
    return CaseAnomalyOverview(
        spider_plot=spider, contributing_factors=factors
    )


def case_results_from_db_payload(
    data: dict[str, Any],
    *,
    prediction_id: str,
) -> CaseResultsResponse:
    """
    Map a db-service case-detail dict onto the public case-results payload.

    Sanitizes period-max maps, overlays the instance on expected-normal
    behaviour, and derives severity from ``final_score``.

    Arguments:
        data: Raw case-detail JSON from db-service (``result``,
            ``normal_sample``, period-max maps, ``prediction_id``).
        prediction_id: Fallback id when the payload omits it.

    Returns:
        ``CaseResultsResponse`` with score, severity, and overview.
    """
    result = data.get("result") or {}
    if not isinstance(result, dict):
        result = {}
    sample = data.get("normal_sample") or []
    if not isinstance(sample, list):
        sample = []
    # Overlay instance on expected-normal; pass row prediction_type so
    # factor sections follow scopes_for_anomaly_type.
    overview = build_case_anomaly_overview(
        result,
        [x for x in sample if isinstance(x, dict)],
        feature_max_values=_float_map(data.get("feature_max_values")),
        scope_max_scores=_float_map(data.get("scope_max_scores")),
        scope_feature_max_values=_scope_float_map(
            data.get("scope_feature_max_values")
        ),
        prediction_type=(
            str(data["prediction_type"])
            if data.get("prediction_type")
            else None
        ),
    )
    inner = _unwrap(result)
    score_f = _to_float(inner.get("final_score"))
    anomalous = None
    if "is_anomalous" in inner:
        anomalous = bool(inner.get("is_anomalous"))
    return CaseResultsResponse(
        prediction_id=str(data.get("prediction_id") or prediction_id),
        final_score=score_f,
        is_anomalous=anomalous,
        severity=_severity_of(score_f),
        anomaly_overview=overview,
    )
