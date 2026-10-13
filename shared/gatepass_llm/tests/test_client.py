"""Tests for LLM stream routing."""

from gatepass_llm.client import log_llm_configuration, resolved_model_label
from gatepass_llm.config import LlmSettings


def test_non_prod_requires_openai_key():
    cfg = LlmSettings(
        ENV="local",
        OPENAI_API_KEY=None,
        GCP_PROJECT_ID="gatepass-461616",
    )
    assert cfg.uses_vertex() is False
    assert log_llm_configuration(cfg) is False

    cfg_ok = cfg.model_copy(update={"OPENAI_API_KEY": "sk-test"})
    assert log_llm_configuration(cfg_ok) is True
    assert resolved_model_label(cfg_ok) == cfg_ok.OPENAI_CHAT_MODEL


def test_prod_requires_gcp_project():
    cfg = LlmSettings(
        ENV="prod",
        OPENAI_API_KEY="sk-test",
        GCP_PROJECT_ID=None,
    )
    assert cfg.uses_vertex() is True
    assert log_llm_configuration(cfg) is False

    cfg_ok = cfg.model_copy(update={"GCP_PROJECT_ID": "gatepass-461616"})
    assert log_llm_configuration(cfg_ok) is True
    assert resolved_model_label(cfg_ok) == cfg_ok.GCP_LLM_CHAT_MODEL


def test_env_prod_is_case_insensitive():
    cfg = LlmSettings(ENV="PROD", GCP_PROJECT_ID="p")
    assert cfg.uses_vertex() is True
