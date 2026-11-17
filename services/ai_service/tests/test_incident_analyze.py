"""Tests for date-window incident analyze (tier-gated topics + LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from gatepass_entitlement import (
    INCIDENT_REPORT_SUMMARY_TIER_1_KEY,
    INCIDENT_REPORT_SUMMARY_TIER_2_KEY,
    INCIDENT_REPORT_SUMMARY_TIER_3_KEY,
    resolve_incident_entitlements,
)
from app.pipeline.incident_report_orchestrator import (
    IncidentReportOrchestrator,
)

_SAMPLE_RECORDS = [
    {
        "id": str(uuid4()),
        "title": "Gate issue",
        "category": ["security"],
        "custom_category": None,
        "narrative": "Unauthorized vehicle at main gate.",
        "occurred_at": "2026-04-01T10:00:00Z",
    },
    {
        "id": str(uuid4()),
        "title": "Noise",
        "category": ["noise_disturbance"],
        "custom_category": None,
        "narrative": "Loud music after quiet hours.",
        "occurred_at": "2026-04-02T11:00:00Z",
    },
    {
        "id": str(uuid4()),
        "title": "Delivery",
        "category": ["dispute"],
        "custom_category": None,
        "narrative": "Argument with security at reception.",
        "occurred_at": "2026-04-03T12:00:00Z",
    },
]


@pytest.mark.asyncio
async def test_resolve_incident_entitlements_maps_three_keys():
    async def _allowed(*_args, feature_key: str, **_kwargs):
        return feature_key == INCIDENT_REPORT_SUMMARY_TIER_1_KEY

    with patch(
        "gatepass_entitlement.ai.is_ai_feature_allowed",
        new=_allowed,
    ):
        page, inhouse, llm = await resolve_incident_entitlements(
            "http://revenue-service",
            estate_id=uuid4(),
        )
    assert (page, inhouse, llm) == (True, False, False)

    async def _tier3(*_args, feature_key: str, **_kwargs):
        return feature_key == INCIDENT_REPORT_SUMMARY_TIER_3_KEY

    with patch(
        "gatepass_entitlement.ai.is_ai_feature_allowed",
        new=_tier3,
    ):
        page, inhouse, llm = await resolve_incident_entitlements(
            "http://revenue-service",
            estate_id=uuid4(),
        )
    assert (page, inhouse, llm) == (True, True, True)
    assert INCIDENT_REPORT_SUMMARY_TIER_2_KEY.startswith(
        "incident_report_summary"
    )


def _entitlements(page: bool, inhouse: bool, llm: bool):
    async def _inner(*_args, **_kwargs):
        return page, inhouse, llm

    return _inner


@pytest.mark.asyncio
async def test_analyze_tier3_runs_topics_and_llm():
    orch = IncidentReportOrchestrator()
    client = AsyncMock()
    estate_id = uuid4()

    with (
        patch(
            "app.pipeline.incident_report_orchestrator.load_incident_reports_for_estate",
            new_callable=AsyncMock,
            return_value=_SAMPLE_RECORDS,
        ),
        patch(
            "app.pipeline.incident_report_orchestrator.resolve_incident_entitlements",
            new=_entitlements(True, True, True),
        ),
        patch(
            "app.pipeline.incident_report_orchestrator.summarize_incidents_with_llm",
            new_callable=AsyncMock,
            return_value=(
                {
                    "executive_summary": "Test summary",
                    "key_patterns": [],
                    "severity_assessment": "",
                    "recommended_actions": [],
                    "data_limitations": "",
                },
                "gpt-4o-mini",
                True,
            ),
        ),
    ):
        result = await orch.analyze(
            client=client,
            estate_id=estate_id,
        )

    assert result["entitled_tier"] == "tier2"
    assert result["topics"]["n_topics"] >= 1
    assert result["summary"]["structured_summary"]["executive_summary"]


@pytest.mark.asyncio
async def test_analyze_tier2_only_skips_llm():
    orch = IncidentReportOrchestrator()
    client = AsyncMock()
    estate_id = uuid4()

    with (
        patch(
            "app.pipeline.incident_report_orchestrator.load_incident_reports_for_estate",
            new_callable=AsyncMock,
            return_value=_SAMPLE_RECORDS,
        ),
        patch(
            "app.pipeline.incident_report_orchestrator.resolve_incident_entitlements",
            new=_entitlements(True, True, False),
        ),
        patch(
            "app.pipeline.incident_report_orchestrator.summarize_incidents_with_llm",
            new_callable=AsyncMock,
        ) as mock_llm,
    ):
        result = await orch.analyze(
            client=client,
            estate_id=estate_id,
        )

    mock_llm.assert_not_called()
    assert result["entitled_tier"] == "tier1"
    assert result["topics"]["report_text"] or result["topics"].get("note")
    assert result["summary"] == {}


@pytest.mark.asyncio
async def test_analyze_basic_only_skips_summaries():
    orch = IncidentReportOrchestrator()
    client = AsyncMock()
    estate_id = uuid4()

    with (
        patch(
            "app.pipeline.incident_report_orchestrator.load_incident_reports_for_estate",
            new_callable=AsyncMock,
            return_value=_SAMPLE_RECORDS,
        ),
        patch(
            "app.pipeline.incident_report_orchestrator.resolve_incident_entitlements",
            new=_entitlements(True, False, False),
        ),
        patch(
            "app.pipeline.incident_report_orchestrator.summarize_incidents_with_llm",
            new_callable=AsyncMock,
        ) as mock_llm,
    ):
        result = await orch.analyze(
            client=client,
            estate_id=estate_id,
        )

    mock_llm.assert_not_called()
    assert result["entitled_tier"] is None
    assert result["topics"] == {}
    assert result["summary"] == {}
