"""Incident result-page mapping, membership, and summary gating."""

from uuid import UUID, uuid4

import pytest

from app.domain.ai_summary import incident_lookup_key
from app.models.incident_resultpage import IncidentLlmSummary
from app.pipeline.incident_resultpage import (
    attach_category_eda,
    build_inhouse_incident_summary,
    overview_from_parts,
)


def test_incident_lookup_key_uses_estate_and_open_bounds():
    estate_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    assert incident_lookup_key(estate_id, None, None) == (
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:open:open"
    )


def test_overview_from_parts_builds_ratio_and_trends():
    records = [
        {
            "category": ["theft"],
            "custom_category": None,
            "title": "Gate",
            "narrative": "Forced gate",
            "occurred_at": "2026-04-01T08:00:00Z",
        },
        {
            "category": ["noise_disturbance"],
            "custom_category": None,
            "title": "Noise",
            "narrative": "Loud music",
            "occurred_at": "2026-04-01T14:00:00Z",
        },
    ]
    payload = overview_from_parts(
        db_overview={
            "estate_name": "Lakeside",
            "state": "Lagos",
            "country": "Nigeria",
            "total_reports": 2,
            "resident_report_count": 2,
            "security_report_count": 0,
        },
        records=records,
    )
    assert payload.demographic.estate_name == "Lakeside"
    assert payload.demographic.ratio["resident"].percentage == 100.0
    assert payload.demographic.ratio["security"].count == 0
    assert payload.eda.categories.top_1 is not None
    assert payload.eda.categories.top_1.category == "theft"
    assert "2 incident reports" in payload.eda.trends_detected
    assert payload.eda.stats["record_count"] == 2
    assert payload.has_tier1_summary is False
    assert payload.has_tier2_summary is False


def test_overview_from_parts_passes_summary_cache_flags():
    payload = overview_from_parts(
        db_overview={
            "estate_name": "Lakeside",
            "state": "Lagos",
            "country": "Nigeria",
            "total_reports": 0,
            "resident_report_count": 0,
            "security_report_count": 0,
        },
        records=[],
        has_tier1_summary=True,
        has_tier2_summary=False,
    )
    assert payload.has_tier1_summary is True
    assert payload.has_tier2_summary is False


def test_inhouse_and_llm_share_the_same_category_eda():
    records = [
        {
            "category": ["theft"],
            "custom_category": None,
            "title": "Gate",
            "narrative": "Forced gate at night",
            "occurred_at": "2026-04-01T21:00:00Z",
        }
    ]
    inhouse = build_inhouse_incident_summary(records)
    llm = attach_category_eda(
        IncidentLlmSummary(executive_summary="LLM text"),
        inhouse.category_eda,
    )
    assert inhouse.category_eda.top_1 is not None
    assert llm.category_eda == inhouse.category_eda
    assert inhouse.topics.get("method") == "tfidf_nmf"
    assert inhouse.executive_summary


def test_drop_all_filter_treats_all_as_unfiltered():
    from app.api.v1.endpoints.incident_resultpage import _parse_enum_filter
    from app.domain.incident_category import (
        IncidentCategory,
        drop_all_filter,
    )
    from app.models.incident_resultpage import ReporterUserType

    assert drop_all_filter(None) is None
    assert drop_all_filter([]) is None
    assert drop_all_filter(["all"]) is None
    assert drop_all_filter(["ALL", "theft"]) is None
    assert drop_all_filter("all") is None
    assert drop_all_filter(["theft", "noise_disturbance"]) == [
        "theft",
        "noise_disturbance",
    ]
    assert _parse_enum_filter(["all"], IncidentCategory, "category") is None
    assert _parse_enum_filter(["ALL"], ReporterUserType, "user_type") is None
    assert _parse_enum_filter(["theft"], IncidentCategory, "category") == [
        "theft"
    ]


def test_require_estate_membership_allows_matching_estate():
    from gatepass_rbac import require_estate_membership

    estate_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    require_estate_membership({"estate_id": str(estate_id)}, estate_id)


def test_require_estate_membership_rejects_mismatch_and_missing():
    from fastapi import HTTPException
    from gatepass_rbac import require_estate_membership

    estate_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    other = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    with pytest.raises(HTTPException) as mismatch:
        require_estate_membership({"estate_id": str(other)}, estate_id)
    assert mismatch.value.status_code == 403

    with pytest.raises(HTTPException) as missing:
        require_estate_membership({"estate_id": None}, estate_id)
    assert missing.value.status_code == 403


def test_require_estate_membership_skips_root():
    from gatepass_rbac import require_estate_membership

    estate_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    require_estate_membership({"role": "root", "estate_id": None}, estate_id)


@pytest.mark.asyncio
async def test_overview_reads_summary_cache_flags(monkeypatch):
    from app.services.incident_resultpage import IncidentResultPageService

    async def _overview(*_args, **_kwargs):
        return {
            "estate_name": "Lakeside",
            "state": "Lagos",
            "country": "Nigeria",
            "total_reports": 0,
            "resident_report_count": 0,
            "security_report_count": 0,
        }

    async def _records(*_args, **_kwargs):
        return []

    async def _cache(*_args, **_kwargs):
        return {
            "has_tier1_summary": True,
            "has_tier2_summary": False,
            "ai_summary": {"tier1": {"executive_summary": "topics"}},
        }

    monkeypatch.setattr(
        "app.services.incident_resultpage.fetch_incident_overview",
        _overview,
    )
    monkeypatch.setattr(
        "app.services.incident_resultpage.load_incident_reports_for_estate",
        _records,
    )
    monkeypatch.setattr(
        "app.services.incident_resultpage.fetch_ai_summary",
        _cache,
    )
    service = IncidentResultPageService()
    payload = await service.get_overview(
        estate_id=uuid4(),
        from_date=None,
        to_date=None,
    )
    assert payload.has_tier1_summary is True
    assert payload.has_tier2_summary is False


@pytest.mark.asyncio
async def test_get_summary_denies_when_estate_has_no_grant(monkeypatch):
    from app.core.exceptions import EntitlementDeniedError
    from app.services.incident_resultpage import IncidentResultPageService

    async def _denied(*_args, **_kwargs):
        return False, False, False

    monkeypatch.setattr(
        "app.services.incident_resultpage.resolve_incident_entitlements",
        _denied,
    )
    service = IncidentResultPageService()
    with pytest.raises(EntitlementDeniedError) as denied:
        await service.get_summary(
            estate_id=uuid4(),
            from_date=None,
            to_date=None,
        )
    assert denied.value.status_code == 403
    assert "not entitled" in denied.value.message.lower()


@pytest.mark.asyncio
async def test_get_summary_basic_only_is_denied(monkeypatch):
    from app.core.exceptions import EntitlementDeniedError
    from app.services.incident_resultpage import IncidentResultPageService

    async def _basic_only(*_args, **_kwargs):
        return True, False, False

    monkeypatch.setattr(
        "app.services.incident_resultpage.resolve_incident_entitlements",
        _basic_only,
    )
    service = IncidentResultPageService()
    with pytest.raises(EntitlementDeniedError) as denied:
        await service.get_summary(
            estate_id=uuid4(),
            from_date=None,
            to_date=None,
        )
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_get_summary_tier2_only_skips_llm(monkeypatch):
    from app.services.incident_resultpage import IncidentResultPageService

    async def _tier2_only(*_args, **_kwargs):
        return True, True, False

    async def _no_cache(*_args, **_kwargs):
        return None

    async def _records(*_args, **_kwargs):
        return [
            {
                "category": ["theft"],
                "custom_category": None,
                "title": "Gate",
                "narrative": "Forced gate at night after patrol.",
                "occurred_at": "2026-04-01T21:00:00Z",
            },
            {
                "category": ["noise_disturbance"],
                "custom_category": None,
                "title": "Noise",
                "narrative": "Loud music from block B until late.",
                "occurred_at": "2026-04-02T14:00:00Z",
            },
            {
                "category": ["maintenance"],
                "custom_category": None,
                "title": "Light",
                "narrative": "Streetlight out on palm avenue.",
                "occurred_at": "2026-04-03T19:00:00Z",
            },
        ]

    upsert_calls: list[dict] = []

    async def _upsert(*_args, **kwargs):
        upsert_calls.append(kwargs)
        return {}

    llm_called = False

    async def _llm(*_args, **_kwargs):
        nonlocal llm_called
        llm_called = True
        return ({}, None, False)

    monkeypatch.setattr(
        "app.services.incident_resultpage.resolve_incident_entitlements",
        _tier2_only,
    )
    monkeypatch.setattr(
        "app.services.incident_resultpage.fetch_ai_summary",
        _no_cache,
    )
    monkeypatch.setattr(
        "app.services.incident_resultpage.load_incident_reports_for_estate",
        _records,
    )
    monkeypatch.setattr(
        "app.services.incident_resultpage.upsert_ai_summary",
        _upsert,
    )
    monkeypatch.setattr(
        "app.services.incident_resultpage.summarize_incidents_with_llm",
        _llm,
    )
    service = IncidentResultPageService()
    result = await service.get_summary(
        estate_id=uuid4(),
        from_date=None,
        to_date=None,
    )
    assert result.entitled_tier == "tier1"
    assert result.tier1 is not None
    assert result.tier1.topics.get("method") == "tfidf_nmf"
    assert result.tier2 is None
    assert llm_called is False
    assert upsert_calls and upsert_calls[0].get("tier2") is None
    assert upsert_calls[0].get("tier1")
