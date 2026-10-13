"""
Paid-tier narrative synthesis over incident cohorts.

Combines exploratory statistics (EDA) with truncated row snippets and requests a
structured JSON summary via :mod:`gatepass_llm`. Falls back to category-frequency
heuristics when LLM is unset or the call fails. Does not alter TF-IDF/NMF topics.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from gatepass_llm import (
    complete_json_chat,
    extract_json_object,
    log_llm_configuration,
    resolved_model_label,
)

from app.core.config import Settings

logger = logging.getLogger(__name__)


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
            "Configure third-party LLM credentials for narrative synthesis."
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
    model_label = resolved_model_label()
    if not log_llm_configuration():
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

    system_content = (
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
    )

    try:
        content, model = await complete_json_chat(
            client=client,
            system=system_content,
            user=user_prompt,
            temperature=0.2,
            timeout=60.0,
        )
        parsed = extract_json_object(content)
        return parsed, model, True
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        IndexError,
        RuntimeError,
    ) as exc:
        logger.warning(
            "Incident summary using heuristic fallback; LLM call failed: %s",
            exc,
        )
        fb = _fallback_summary(eda, record_count=len(records))
        fb["data_limitations"] = (
            str(fb.get("data_limitations") or "")
            + " LLM step failed; see logs."
        )
        return fb, model_label, False
