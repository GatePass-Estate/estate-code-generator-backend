"""Per-scope log history fetch behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.config import Settings
from app.domain.scopes import AnalysisScope
from app.integrations.db_service_logs import load_log_records_for_analysis
from app.models.code_validation import CodeValidationPayload, Receiver


def _payload(*, visitor_log_id: UUID | None, resident_log_id: UUID | None):
    return CodeValidationPayload(
        user_id=UUID("ea544461-05f0-43f0-b207-066d5f128a07"),
        security_id=UUID("5eaaf13e-d9e2-4e01-a65d-277fb55623b0"),
        estate_id=UUID("6eb0c18d-5505-4601-a211-1584b6a5bc31"),
        hashed_code="ABC123",
        valid_until="2026-10-01T00:00:00Z",
        is_expired=False,
        receiver=Receiver.VISITOR if visitor_log_id else Receiver.RESIDENT,
        visitor_log_id=visitor_log_id,
        resident_log_id=resident_log_id,
    )


@pytest.mark.asyncio
async def test_visitor_log_scope_searches_skip_temporal_history():
    visitor_log_id = UUID("51c43fa0-5432-4b39-94da-5299581c3537")
    estate_id = "6eb0c18d-5505-4601-a211-1584b6a5bc31"
    user_id = "ea544461-05f0-43f0-b207-066d5f128a07"
    security_id = "5eaaf13e-d9e2-4e01-a65d-277fb55623b0"
    anchor = {
        "id": str(visitor_log_id),
        "visitor_fullname": "Jane Guest",
        "visit_time": "2026-09-20T10:00:00Z",
        "created_at": "2026-09-20T10:00:01Z",
    }
    cfg = Settings(SPATIAL_SCOPE_HISTORY_LIMIT=40)
    search_calls: list[dict] = []

    async def fake_get(_client, url, *, params=None):
        if url.endswith(f"/visitorlog/{visitor_log_id}"):
            return anchor
        search_calls.append(dict(params or {}))
        return {"items": [{"id": str(visitor_log_id), **anchor}], "total": 1}

    with (
        patch(
            "app.integrations.db_service_logs._get_json",
            new=AsyncMock(side_effect=fake_get),
        ),
        patch(
            "app.integrations.db_service_logs._wrangled_scope_rows",
            new=AsyncMock(side_effect=lambda records, _anchor: records),
        ),
        patch(
            "app.integrations.db_service_logs._wrangled_focal_only",
            new=AsyncMock(return_value=[anchor]),
        ),
    ):
        slices = await load_log_records_for_analysis(
            AsyncMock(),
            cfg,
            _payload(visitor_log_id=visitor_log_id, resident_log_id=None),
        )

    assert len(search_calls) == 4
    assert slices.temporal == [anchor]
    assert slices.temporal is not slices.resident_specific
    assert (
        slices.rows_for_history_lookup(AnalysisScope.TEMPORAL)
        == slices.resident_specific
    )
    assert any(
        c.get("estate_id") == estate_id and c.get("user_id") == user_id
        for c in search_calls
    )
    assert any(
        c.get("estate_id") == estate_id and "user_id" not in c
        for c in search_calls
    )
    assert any(c.get("visitor_fullname") == "Jane Guest" for c in search_calls)
    assert any(
        c.get("estate_id") == estate_id and c.get("security_id") == security_id
        for c in search_calls
    )


@pytest.mark.asyncio
async def test_resident_log_temporal_focal_only_no_visitor_search():
    resident_log_id = UUID("4098dbb3-e3f7-4b4d-ab4a-d209d9f0b890")
    estate_id = "6eb0c18d-5505-4601-a211-1584b6a5bc31"
    user_id = "ea544461-05f0-43f0-b207-066d5f128a07"
    security_id = "5eaaf13e-d9e2-4e01-a65d-277fb55623b0"
    anchor = {
        "id": str(resident_log_id),
        "hashed_code": "RES123",
        "access_time": "2026-09-20T10:00:00Z",
        "created_at": "2026-09-20T10:00:01Z",
    }
    cfg = Settings(SPATIAL_SCOPE_HISTORY_LIMIT=40)
    search_calls: list[dict] = []

    async def fake_get(_client, url, *, params=None):
        if url.endswith(f"/residentlog/{resident_log_id}"):
            return anchor
        search_calls.append(dict(params or {}))
        return {"items": [{"id": str(resident_log_id), **anchor}], "total": 1}

    with (
        patch(
            "app.integrations.db_service_logs._get_json",
            new=AsyncMock(side_effect=fake_get),
        ),
        patch(
            "app.integrations.db_service_logs._wrangled_scope_rows",
            new=AsyncMock(side_effect=lambda records, _anchor: records),
        ),
        patch(
            "app.integrations.db_service_logs._wrangled_focal_only",
            new=AsyncMock(return_value=[anchor]),
        ),
    ):
        slices = await load_log_records_for_analysis(
            AsyncMock(),
            cfg,
            _payload(visitor_log_id=None, resident_log_id=resident_log_id),
        )

    assert len(search_calls) == 3
    assert slices.temporal == [anchor]
    assert slices.visitor_specific == []
    assert (
        slices.rows_for_history_lookup(AnalysisScope.TEMPORAL)
        == slices.resident_specific
    )
    assert "hashed_code" not in {
        k
        for c in search_calls
        for k in c
        if k not in ("to_date", "limit", "page")
    }
    assert any(
        c.get("estate_id") == estate_id and c.get("user_id") == user_id
        for c in search_calls
    )
    assert any(
        c.get("estate_id") == estate_id and "user_id" not in c
        for c in search_calls
    )
    assert any(
        c.get("estate_id") == estate_id and c.get("security_id") == security_id
        for c in search_calls
    )
