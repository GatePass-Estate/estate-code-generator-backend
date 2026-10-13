"""Parse structured JSON from model chat output."""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def extract_json_object(text: str) -> dict[str, Any]:
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
