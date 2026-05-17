"""
Paid-tier narrative synthesis over incident cohorts.

Combines exploratory statistics (EDA) with truncated row snippets and requests a
structured JSON summary from an OpenAI-compatible chat API. Falls back to
category-frequency heuristics when ``OPENAI_API_KEY`` is unset or the call fails.
Does not alter TF-IDF/NMF topic assignments.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Best-effort parse of model output into a dict."""
    stripped = text.strip()
    m = _JSON_FENCE.search(stripped)
    if m:
        stripped = m.group(1).strip()
    try:
        out = json.loads(stripped)
        if isinstance(out, dict):
            return out
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            out = json.loads(stripped[start : end + 1])
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError:
            pass
    raise ValueError("Model output was not valid JSON object")


def _fallback_summary(
    eda: dict[str, Any],
    *,
    record_count: int,
) -> dict[str, Any]:
    cats = eda.get("category_distribution") or {}
    top_items = list(cats.items())[:5]
    return {
        "executive_summary": (
            f"Draft heuristic summary over {record_count} incident row(s). "
            f"Most frequent category labels (token counts): {top_items}. "
            "Configure OPENAI_API_KEY for narrative synthesis."
        ),
        "key_patterns": [
            f"Category label frequencies: {top_items}",
            f"Rows missing any category: {eda.get('rows_without_category', 0)}",
            (
                "Custom-only rows: "
                f"{eda.get('rows_with_custom_category_only', 0)}"
            ),
        ],
        "severity_assessment": (
            "No severity field in source data; infer urgency only from "
            "narratives and category mix."
        ),
        "recommended_actions": [
            "Align category taxonomy with operations for consistent tagging.",
            "Enable LLM summarization for richer synthesis.",
        ],
        "data_limitations": (
            "Heuristic fallback used (no LLM). " + (eda.get("note") or "")
        ),
    }


async def summarize_incidents_with_llm(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    records: list[dict[str, Any]],
    eda: dict[str, Any],
) -> tuple[dict[str, Any], str | None, bool]:
    """
    Produce a structured executive summary for a paid estate.

    Returns:
        Tuple of ``(summary_dict, model_name_or_none, llm_used)``. ``llm_used`` is
        ``True`` only when the remote chat API returned parseable JSON.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        fb = _fallback_summary(eda, record_count=len(records))
        return fb, None, False

    snippets: list[str] = []
    for r in records[:12]:
        title = str(r.get("title") or "").strip()
        narrative = str(r.get("narrative") or "").strip()
        cats_json = json.dumps(r.get("category"), ensure_ascii=False)
        custom = str(r.get("custom_category") or "").strip()
        head = f"- Title: {title}\n" if title else ""
        custom_line = f"  Custom category: {custom}\n" if custom else ""
        blob = (
            f"{head}"
            f"- Categories (enum array): {cats_json}\n"
            f"{custom_line}"
            f"  Narrative: {narrative[:450]}"
        )
        snippets.append(blob)

    user_prompt = (
        "Exploratory statistics (JSON):\n"
        f"{json.dumps(eda, ensure_ascii=False)}\n\n"
        "Representative incident rows (truncated):\n" + "\n".join(snippets)
    )

    payload = {
        "model": settings.OPENAI_CHAT_MODEL,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You summarise operational incident reports for estate "
                    "security and facilities teams. Each row has optional title, "
                    "enum category array, optional custom_category, and narrative. "
                    "Reply with ONLY a JSON "
                    "object with keys: executive_summary (string), "
                    "key_patterns (array of short strings), "
                    "severity_assessment (string; qualitative overall concern "
                    "from narratives/categories, not a stored severity field), "
                    "recommended_actions (array of short strings), "
                    "data_limitations (string). "
                    "Do not invent specific names or dates not present in the "
                    "input; mark uncertainty in data_limitations."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/v1/chat/completions"

    try:
        resp = await client.post(
            url, headers=headers, json=payload, timeout=60.0
        )
        resp.raise_for_status()
        body = resp.json()
        content = (
            body.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        parsed = _extract_json_object(content)
        return parsed, settings.OPENAI_CHAT_MODEL, True
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        logger.warning("LLM summarization failed, using fallback: %s", exc)
        fb = _fallback_summary(eda, record_count=len(records))
        fb["data_limitations"] = (
            str(fb.get("data_limitations") or "")
            + " LLM step failed; see logs."
        )
        return fb, settings.OPENAI_CHAT_MODEL, False
