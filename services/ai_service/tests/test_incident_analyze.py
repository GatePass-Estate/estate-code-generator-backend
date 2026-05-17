"""Tests for merged incident analyze (payment-gated summary)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

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
async def test_analyze_payment_active_runs_summary_and_topics():
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
            "app.pipeline.incident_report_orchestrator.fetch_estate_payment_active",
            new_callable=AsyncMock,
            return_value=True,
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
            max_records=50,
        )

    assert result["estate_payment_active"] is True
    assert result["topics"]["n_topics"] >= 1
    assert result["summary"]["structured_summary"]["executive_summary"]


@pytest.mark.asyncio
async def test_analyze_payment_inactive_empty_summary():
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
            "app.pipeline.incident_report_orchestrator.fetch_estate_payment_active",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.pipeline.incident_report_orchestrator.summarize_incidents_with_llm",
            new_callable=AsyncMock,
        ) as mock_llm,
    ):
        result = await orch.analyze(
            client=client,
            estate_id=estate_id,
            max_records=50,
        )

    mock_llm.assert_not_called()
    assert result["estate_payment_active"] is False
    assert result["topics"]["report_text"]
    assert result["summary"]["structured_summary"]["executive_summary"] == ""
    assert result["summary"]["llm_used"] is False
