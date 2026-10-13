"""OpenAI-compatible chat completions (OpenAI dev, Vertex prod)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from gatepass_llm.config import LlmSettings, settings

logger = logging.getLogger(__name__)

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def is_llm_configured(cfg: LlmSettings | None = None) -> bool:
    """
    Return whether the active stream (prod vs non-prod) can call an LLM.

    Prod requires ``GCP_PROJECT_ID``; non-prod requires ``OPENAI_API_KEY``.
    """
    cfg = cfg or settings
    if cfg.uses_vertex():
        return bool(cfg.GCP_PROJECT_ID and cfg.GCP_PROJECT_ID.strip())
    return bool(cfg.OPENAI_API_KEY)


def resolved_model_label(cfg: LlmSettings | None = None) -> str:
    """Model id string for the active stream (for cache / logging)."""
    cfg = cfg or settings
    if cfg.uses_vertex():
        return cfg.GCP_LLM_CHAT_MODEL
    return cfg.OPENAI_CHAT_MODEL


def _vertex_chat_completions_url(cfg: LlmSettings) -> str:
    project = (cfg.GCP_PROJECT_ID or "").strip()
    location = cfg.GCP_VERTEX_LOCATION.strip() or "global"
    host = (
        "aiplatform.googleapis.com"
        if location == "global"
        else f"{location}-aiplatform.googleapis.com"
    )
    return (
        f"https://{host}/v1/projects/{project}/locations/{location}"
        f"/endpoints/openapi/chat/completions"
    )


def _openai_chat_completions_url(cfg: LlmSettings) -> str:
    return f"{cfg.OPENAI_BASE_URL.rstrip('/')}/v1/chat/completions"


async def _gcp_bearer_token() -> str:
    def _refresh() -> str:
        import google.auth
        import google.auth.transport.requests

        creds, _ = google.auth.default(scopes=[_CLOUD_PLATFORM_SCOPE])
        creds.refresh(google.auth.transport.requests.Request())
        if not creds.token:
            raise RuntimeError(
                "Google Cloud credentials returned no access token"
            )
        return creds.token

    return await asyncio.to_thread(_refresh)


async def complete_json_chat(
    *,
    client: httpx.AsyncClient,
    system: str,
    user: str,
    temperature: float = 0.2,
    timeout: float = 60.0,
    cfg: LlmSettings | None = None,
) -> tuple[str, str]:
    """
    Request a JSON-object chat completion from the configured third-party LLM.

    Returns:
        ``(assistant_content, model_id)`` for the stream selected by ``ENV``.

    Raises:
        httpx.HTTPError: Transport / HTTP failure.
        RuntimeError: Missing configuration or auth for the active stream.
        ValueError: Response shape missing assistant content.
    """
    cfg = cfg or settings
    if not is_llm_configured(cfg):
        stream = "Vertex (prod)" if cfg.uses_vertex() else "OpenAI (non-prod)"
        raise RuntimeError(f"LLM not configured for {stream}")

    if cfg.uses_vertex():
        url = _vertex_chat_completions_url(cfg)
        token = await _gcp_bearer_token()
        model = cfg.GCP_LLM_CHAT_MODEL
    else:
        url = _openai_chat_completions_url(cfg)
        token = cfg.OPENAI_API_KEY or ""
        model = cfg.OPENAI_CHAT_MODEL

    payload: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = await client.post(
        url, headers=headers, json=payload, timeout=timeout
    )
    resp.raise_for_status()
    body = resp.json()
    content = (
        body.get("choices", [{}])[0].get("message", {}).get("content", "")
    )
    if not content:
        raise ValueError("Chat completion returned empty assistant content")
    return content, model
