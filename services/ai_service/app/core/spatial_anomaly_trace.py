"""
Compact debug prints for spatial anomaly payload transformation.

Enable via ``SPATIAL_ANOMALY_PAYLOAD_DEBUG=true`` (default on when ``ENV=local``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

_PREFIX = "[spatial-anomaly]"
_MAX_LIST_PREVIEW = 3
_MAX_DICT_KEYS = 8
_MAX_STR = 120


def trace_enabled() -> bool:
    from app.core.config import settings

    return bool(settings.SPATIAL_ANOMALY_PAYLOAD_DEBUG)


def _short_id(value: Any) -> str:
    text = str(value)
    if len(text) > 12 and "-" in text:
        return f"…{text[-8:]}"
    return text


def _feature_dict(features: dict[str, Any]) -> str:
    if not features:
        return "(none)"
    parts = [
        f"{k}={_summarize(v, depth=2)}"
        for k, v in sorted(features.items())[:_MAX_DICT_KEYS]
    ]
    extra = len(features) - _MAX_DICT_KEYS
    tail = f" +{extra} more" if extra > 0 else ""
    return ", ".join(parts) + tail


def _historical_vectors(vectors: list[Any]) -> str:
    if not vectors:
        return "0 vectors"
    n = len(vectors)
    first = vectors[0] if isinstance(vectors[0], dict) else {}
    keys = len(first) if isinstance(first, dict) else 0
    preview = _feature_dict(first) if isinstance(first, dict) else "?"
    return f"{n} vector(s), {keys} feature(s)/row · sample: {preview}"


def _scope_weights(rows: list[Any]) -> str:
    if not rows:
        return "(none)"
    lines: list[str] = []
    for row in rows[:6]:
        if not isinstance(row, dict):
            continue
        scope = row.get("scope") or row.get("name") or "?"
        conf = row.get("history_confidence")
        eff = row.get("effective_weight")
        matched = row.get("matched_count")
        lines.append(f"{scope}: conf={conf} eff={eff} matched={matched}")
    if len(rows) > 6:
        lines.append(f"+{len(rows) - 6} more scopes")
    return " · ".join(lines)


def _feature_contributions(rows: list[Any]) -> str:
    if not rows:
        return "(none)"
    parts: list[str] = []
    for row in rows[:6]:
        if isinstance(row, dict):
            name = row.get("feature_name", "?")
            val = row.get("value")
            wt = row.get("weight")
            parts.append(f"{name}={val} w={wt}")
        else:
            name = getattr(row, "feature_name", "?")
            parts.append(f"{name}={getattr(row, 'value', '?')}")
    if len(rows) > 6:
        parts.append(f"+{len(rows) - 6} more")
    return ", ".join(parts)


def _summarize_analyze_response(obj: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    final = obj.get("final_score")
    threshold_note = ""
    is_anom = obj.get("is_anomalous")
    lines.append(
        f"final_score={final} · is_anomalous={is_anom}{threshold_note}"
    )
    per_scope = obj.get("per_scope_scores") or {}
    if isinstance(per_scope, dict) and per_scope:
        scope_bits = ", ".join(
            f"{k}={round(float(v), 3) if v is not None else v}"
            for k, v in sorted(per_scope.items())
        )
        lines.append(f"per_scope: {scope_bits}")
    transparency = obj.get("transparency") or {}
    if isinstance(transparency, dict):
        lines.append(f"ensemble: {transparency.get('ensemble_method')}")
        lines.append(
            f"scope_weights: {_scope_weights(transparency.get('scope_weights') or [])}"
        )
        scopes = transparency.get("scopes") or []
        if scopes:
            lines.append(f"transparency scopes: {len(scopes)}")
            for detail in scopes[:5]:
                if not isinstance(detail, dict):
                    continue
                lines.append(
                    f"  · {detail.get('label') or detail.get('scope')}: "
                    f"score={detail.get('score')} · "
                    f"{_feature_contributions(detail.get('feature_contributions') or [])}"
                )
    return lines


def _summarize_overview_response(obj: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    demo = obj.get("demographic") or {}
    if isinstance(demo, dict):
        lines.append(
            f"estate={demo.get('estate_name')} · users={demo.get('total_users')} · "
            f"guests={demo.get('total_guests')} · "
            f"anomalous_instances={demo.get('total_anomalous_instances')}"
        )
    evidence = obj.get("evidence_summary") or {}
    if isinstance(evidence, dict):
        lines.append(
            f"anomalous: residents={evidence.get('total_anomalous_residents_instances')} · "
            f"visitors={evidence.get('total_anomalous_visitors_instances')}"
        )
    overview = obj.get("anomaly_overview") or {}
    if isinstance(overview, dict):
        spider = overview.get("spider_plot") or []
        factors = overview.get("contributing_factors") or []
        lines.append(f"spider_plot: {len(spider)} feature(s)")
        for pt in spider[:4]:
            if isinstance(pt, dict):
                lines.append(
                    f"  · {pt.get('label') or pt.get('feature_name')}: "
                    f"normal={pt.get('normal_value')} weight={pt.get('weight')}"
                )
        lines.append(f"contributing_factors: {len(factors)} scope(s)")
        for factor in factors[:5]:
            if isinstance(factor, dict):
                lines.append(
                    f"  · {factor.get('label') or factor.get('name')}: "
                    f"normal={factor.get('normal_value')} · "
                    f"{len(factor.get('sub_factors') or [])} sub-factor(s)"
                )
    return lines


def _summarize_case_response(obj: dict[str, Any]) -> list[str]:
    lines = [
        f"prediction_id={_short_id(obj.get('prediction_id'))} · "
        f"final_score={obj.get('final_score')} · "
        f"severity={obj.get('severity')} · is_anomalous={obj.get('is_anomalous')}",
    ]
    overview = obj.get("anomaly_overview") or {}
    if isinstance(overview, dict):
        spider = overview.get("spider_plot") or []
        factors = overview.get("contributing_factors") or []
        lines.append(f"spider_plot: {len(spider)} point(s)")
        for pt in spider[:4]:
            if isinstance(pt, dict):
                lines.append(
                    f"  · {pt.get('label') or pt.get('feature_name')}: "
                    f"instance={pt.get('instance_value')} normal={pt.get('normal_value')}"
                )
        lines.append(f"contributing_factors: {len(factors)} scope(s)")
        for factor in factors[:5]:
            if not isinstance(factor, dict):
                continue
            subs = factor.get("sub_factors") or []
            lines.append(
                f"  · {factor.get('label') or factor.get('name')}: "
                f"instance={factor.get('instance_value')} · "
                f"{len(subs)} sub-factor(s)"
            )
    return lines


def _summarize(value: Any, *, depth: int = 0, key: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, UUID):
        return _short_id(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.4g}"

    if isinstance(value, str):
        if len(value) > _MAX_STR:
            return value[: _MAX_STR - 3] + "…"
        return value

    if depth >= 2:
        if isinstance(value, dict):
            return f"{{{len(value)} keys}}"
        if isinstance(value, (list, tuple)):
            return f"[{len(value)} items]"

    if isinstance(value, dict):
        if key in {"features", "feature_columns"} or all(
            isinstance(v, (int, float)) for v in value.values()
        ):
            return _feature_dict(value)
        if key in {"model_outputs", "per_scope_scores"}:
            return ", ".join(
                f"{k}={_summarize(v, depth=depth + 1)}"
                for k, v in sorted(value.items())
            )
        if key == "request":
            return ", ".join(
                f"{k}={_summarize(v, depth=depth + 1, key=k)}"
                for k, v in value.items()
            )
        parts = [
            f"{k}={_summarize(v, depth=depth + 1, key=k)}"
            for k, v in list(value.items())[:_MAX_DICT_KEYS]
        ]
        extra = len(value) - _MAX_DICT_KEYS
        if extra > 0:
            parts.append(f"+{extra} more")
        return ", ".join(parts)

    if isinstance(value, (list, tuple)):
        items = list(value)
        if not items:
            return "[]"
        if key in {"sample_vectors", "historical_sample"}:
            return _historical_vectors(items)
        if key in {"prev_log_ids", "scope_row_ids", "row_log_ids"}:
            preview = ", ".join(
                _short_id(x) for x in items[:_MAX_LIST_PREVIEW]
            )
            extra = len(items) - _MAX_LIST_PREVIEW
            return f"{len(items)} id(s): {preview}" + (
                f" +{extra} more" if extra > 0 else ""
            )
        if key in {"scope_weights", "contributing_factors"}:
            return _scope_weights(items)
        if key in {"feature_contributions", "transparency_scopes"}:
            return _feature_contributions(items)
        if all(isinstance(x, dict) for x in items[:3]):
            if key in {"historical_sample", "sample_vectors"}:
                return _historical_vectors(items)
            return f"{len(items)} row(s)"
        preview = ", ".join(
            _summarize(x, depth=depth + 1) for x in items[:_MAX_LIST_PREVIEW]
        )
        extra = len(items) - _MAX_LIST_PREVIEW
        return f"{len(items)} item(s): {preview}" + (
            f" +{extra} more" if extra > 0 else ""
        )

    return str(value)


def trace(stage: str, message: str = "", **fields: Any) -> None:
    """Print one compact pipeline stage line plus optional summarized fields."""
    if not trace_enabled():
        return
    header = f"{_PREFIX}[{stage}]"
    if message:
        header = f"{header} {message}"
    if not fields:
        print(header, flush=True)
        return
    if len(fields) == 1 and "features" in fields:
        val = fields["features"]
        print(
            f"{header} · {_feature_dict(val if isinstance(val, dict) else {})}",
            flush=True,
        )
        return
    parts = [f"{k}={_summarize(v, key=k)}" for k, v in fields.items()]
    print(f"{header} · " + " · ".join(parts), flush=True)


def trace_json(stage: str, label: str, obj: Any) -> None:
    """Print a human-readable summary of a large JSON payload."""
    if not trace_enabled():
        return
    print(f"{_PREFIX}[{stage}] {label}", flush=True)
    if not isinstance(obj, dict):
        print(f"{_PREFIX}[{stage}]   {_summarize(obj)}", flush=True)
        return

    if stage in {"analyze-out", "api-analyze-in"} or "final_score" in obj:
        lines = _summarize_analyze_response(obj)
    elif stage == "resultpage-overview-out":
        lines = _summarize_overview_response(obj)
    elif stage == "resultpage-case-out":
        lines = _summarize_case_response(obj)
    elif "code_validation" in obj:
        cv = obj.get("code_validation") or {}
        lines = [
            f"anomaly_type={obj.get('anomaly_type')} · "
            f"receiver={cv.get('receiver')} · "
            f"estate={_short_id(cv.get('estate_id'))} · "
            f"visitor_log={_short_id(cv.get('visitor_log_id'))} · "
            f"resident_log={_short_id(cv.get('resident_log_id'))}",
        ]
    else:
        lines = [
            f"{k}={_summarize(v, key=k)}" for k, v in list(obj.items())[:12]
        ]

    for line in lines:
        print(f"{_PREFIX}[{stage}]   {line}", flush=True)
