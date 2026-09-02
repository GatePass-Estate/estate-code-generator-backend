"""In-house and third-party summaries for a selected prediction case."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.models.spatial_anomaly_resultpage import InhouseSummary, LlmSummary
from app.pipeline.incident_llm_summarizer import _extract_json_object
from app.pipeline.spatial_anomaly_resultpage import (
    _describe_feature,
    _describe_scope,
    _to_float,
    _unwrap,
)

logger = logging.getLogger(__name__)

_SEVERITY_HIGH = 0.8
_SEVERITY_MEDIUM = 0.5


def _severity_label(score: float | None) -> str:
    """Map final_score onto low / medium / high wording."""
    if score is None:
        return "unknown"
    if score >= _SEVERITY_HIGH:
        return "high"
    if score >= _SEVERITY_MEDIUM:
        return "medium"
    return "low"


def build_inhouse_summary(raw: dict[str, Any]) -> InhouseSummary:
    """
    Format a deterministic executive summary and detailed insight.

    Fed only by the stored prediction payload: score, anomalous flag,
    and per-scope feature contributions. No LLM call.
    """
    payload = _unwrap(raw)
    # 1. One-line verdict from score, anomalous flag, and type.
    score = _to_float(payload.get("final_score"))
    anomalous = bool(payload.get("is_anomalous"))
    anomaly_type = str(payload.get("anomaly_type") or "unknown")
    verdict = "anomalous" if anomalous else "within expected behaviour"
    severity = _severity_label(score)
    score_txt = f"{score:.3f}" if score is not None else "n/a"
    executive = (
        f"This {anomaly_type} prediction is {verdict} "
        f"with a final score of {score_txt} ({severity} severity). "
        "The sections below list each analysis scope and the features "
        "that contributed to that score."
    )

    # 2. Per-scope readout: score then top feature contributions by
    #    weight (null weights last). No LLM.
    lines: list[str] = []
    scopes = (payload.get("transparency") or {}).get("scopes") or []
    if not isinstance(scopes, list) or not scopes:
        lines.append("No scope-level transparency was stored for this case.")
    else:
        for detail in scopes:
            if not isinstance(detail, dict):
                continue
            scope = detail.get("scope")
            if not isinstance(scope, str) or not scope:
                continue
            s_score = _to_float(detail.get("score"))
            s_txt = f"{s_score:.3f}" if s_score is not None else "n/a"
            lines.append(f"{_describe_scope(scope)} (scope score {s_txt})")
            contribs = detail.get("feature_contributions") or []
            if not isinstance(contribs, list) or not contribs:
                lines.append("  No feature contributions recorded.")
                continue
            ranked = sorted(
                [
                    fc
                    for fc in contribs
                    if isinstance(fc, dict) and fc.get("feature_name")
                ],
                key=lambda fc: (
                    _to_float(fc.get("weight")) is not None,
                    _to_float(fc.get("weight")) or 0.0,
                ),
                reverse=True,
            )
            for fc in ranked[:8]:
                fname = str(fc.get("feature_name"))
                value = _to_float(fc.get("value"))
                weight = _to_float(fc.get("weight"))
                v_txt = f"{value:.3f}" if value is not None else "n/a"
                w_txt = f"{weight:.3f}" if weight is not None else "n/a"
                lines.append(
                    f"  - {_describe_feature(fname)}: value {v_txt}, "
                    f"weight {w_txt}"
                )
    return InhouseSummary(
        executive_summary=executive,
        detailed_insight="\n".join(lines),
    )


def _fallback_llm_summary(inhouse: InhouseSummary) -> LlmSummary:
    """Heuristic LLM stand-in when the chat API is unset or fails."""
    return LlmSummary(
        executive_summary=inhouse.executive_summary,
        detailed_insight=inhouse.detailed_insight,
        risk_drivers=[
            "LLM narrative unavailable; in-house report used as fallback."
        ],
        recommended_actions=[
            "Review the in-house detailed insight for this case.",
            "Enable OPENAI_API_KEY for a deeper third-party summary.",
        ],
        data_limitations=(
            "Heuristic fallback used (no LLM or the chat call failed)."
        ),
    )


async def summarize_case_with_llm(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    payload: dict[str, Any],
    inhouse: InhouseSummary,
) -> tuple[LlmSummary, bool]:
    """
    Ask the incident-report chat API for a deeper case narrative.

    Returns ``(summary, llm_used)``. ``llm_used`` is True only when the
    remote API returned parseable JSON.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return _fallback_llm_summary(inhouse), False

    # Compact payload + in-house report; same chat path as incident
    # summaries. Parse JSON or fall back.
    compact = _unwrap(payload)
    user_prompt = (
        "In-house (tier-1) report:\n"
        f"Executive summary: {inhouse.executive_summary}\n\n"
        f"Detailed insight:\n{inhouse.detailed_insight}\n\n"
        "Full prediction payload (JSON):\n"
        f"{json.dumps(compact, ensure_ascii=False, default=str)[:12000]}"
    )
    system = (
        "You are an estate security analyst writing a second-level "
        "anomaly case report. The in-house report is a mechanical "
        "readout of scores and features. Your job is deeper: interpret "
        "what the pattern implies for visitor/resident/security risk, "
        "which drivers matter most, and what operators should do next. "
        "Do not invent people, dates, or locations that are not in the "
        "payload. Reply with ONLY a JSON object with keys: "
        "executive_summary (string, 2-4 sentences), "
        "detailed_insight (string, multi-paragraph narrative), "
        "risk_drivers (array of short strings), "
        "recommended_actions (array of short strings), "
        "data_limitations (string). "
        "Go beyond restating feature names; explain operational meaning."
    )
    body = {
        "model": settings.OPENAI_CHAT_MODEL,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/v1/chat/completions"
    try:
        resp = await client.post(url, headers=headers, json=body, timeout=60.0)
        resp.raise_for_status()
        content = (
            resp.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _extract_json_object(content)
        drivers = parsed.get("risk_drivers") or []
        actions = parsed.get("recommended_actions") or []
        if not isinstance(drivers, list):
            drivers = [str(drivers)]
        if not isinstance(actions, list):
            actions = [str(actions)]
        return (
            LlmSummary(
                executive_summary=str(
                    parsed.get("executive_summary")
                    or inhouse.executive_summary
                ),
                detailed_insight=str(
                    parsed.get("detailed_insight") or inhouse.detailed_insight
                ),
                risk_drivers=[str(x) for x in drivers],
                recommended_actions=[str(x) for x in actions],
                data_limitations=(
                    str(parsed["data_limitations"])
                    if parsed.get("data_limitations") is not None
                    else None
                ),
            ),
            True,
        )
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        logger.warning("Case LLM summarization failed: %s", exc)
        return _fallback_llm_summary(inhouse), False
