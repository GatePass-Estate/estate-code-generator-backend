"""OpenAI-compatible chat completions (OpenAI dev, Vertex prod)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from gatepass_llm.config import LlmSettings, settings

logger = logging.getLogger(__name__)

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def _not_configured_reason(cfg: LlmSettings) -> str | None:
    if cfg.uses_vertex():
        if not (cfg.GCP_PROJECT_ID and cfg.GCP_PROJECT_ID.strip()):
            return "ENV=prod requires GCP_PROJECT_ID for Vertex"
        return None
    if not cfg.OPENAI_API_KEY:
        return "non-prod requires OPENAI_API_KEY for OpenAI"
    return None


def log_llm_configuration(cfg: LlmSettings | None = None) -> bool:
    """
    Log LLM readiness and return whether a chat call can proceed.

    Prod requires ``GCP_PROJECT_ID``; non-prod requires ``OPENAI_API_KEY``.
    """
    cfg = cfg or settings
    reason = _not_configured_reason(cfg)
    if reason:
        logger.info("LLM not configured: %s", reason)
        return False
    logger.info("LLM configured, using model %s", resolved_model_label(cfg))
    return True


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
    reason = _not_configured_reason(cfg)
    if reason:
        raise RuntimeError(f"LLM not configured: {reason}")

    if cfg.uses_vertex():
        url = _vertex_chat_completions_url(cfg)
        model = cfg.GCP_LLM_CHAT_MODEL
        token = await _gcp_bearer_token()
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

    try:
        resp = await client.post(
            url, headers=headers, json=payload, timeout=timeout
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "LLM chat HTTP %s: %s",
            exc.response.status_code,
            (exc.response.text or "")[:300],
        )
        raise
    except httpx.HTTPError as exc:
        logger.warning("LLM chat request failed: %s", exc)
        raise

    body = resp.json()
    content = (
        body.get("choices", [{}])[0].get("message", {}).get("content", "")
    )
    if not content:
        logger.warning("LLM chat returned empty assistant content")
        raise ValueError("Chat completion returned empty assistant content")
    return content, model
