"""Orchestrator tests for temporal (Matrix Profile) anomaly detection."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import LogHistoryError
from app.domain.anomaly_types import AnomalyType
from app.integrations.db_service_validation_volume import (
    ValidationEventsResult,
)
from app.pipeline import temporal_anomaly_orchestration as orch_mod
from app.pipeline.matrix_profile import parse_event_time
from app.pipeline.temporal_anomaly_orchestration import (
    TemporalAnomalyOrchestrator,
)

_UTC = timezone.utc
_START = datetime(2026, 1, 1, tzinfo=_UTC)


def _daily_rows(n_days: int, last_week_burst: bool = False) -> list[dict]:
    """One row per visit; counts vary by weekday, optional final-week spike."""
    rows: list[dict] = []
    for d in range(n_days):
        day = _START + timedelta(days=d)
        count = 6 if day.weekday() >= 5 else 2
        if last_week_burst and d >= n_days - 7:
            count = 40
        for k in range(count):
            ts = day.replace(hour=9) + timedelta(minutes=k)
            rows.append({"id": f"{d}-{k}", "visit_time": ts.isoformat()})
    return rows


def _patch_validation_events(
    monkeypatch,
    rows: list[dict],
    includes: tuple[str, ...] = ("visitor_log",),
) -> None:
    timestamps = [
        ts for ts in (parse_event_time(row) for row in rows) if ts is not None
    ]

    async def _fake_load(client, settings, **kwargs):
        return ValidationEventsResult(
            timestamps=timestamps,
            includes=includes,
        )

    monkeypatch.setattr(orch_mod, "load_validation_events", _fake_load)


@pytest.mark.asyncio
async def test_temporal_flags_recent_burst(monkeypatch):
    _patch_validation_events(
        monkeypatch, _daily_rows(84, last_week_burst=True)
    )
    result = await TemporalAnomalyOrchestrator().analyze(
        client=None,
        anomaly_type=AnomalyType.COMBINED,
        estate_id=str(uuid4()),
    )
    assert result["anomaly_type"] == "combined"
    assert result["detail"]["computed"] is True
    assert result["detail"]["window_size_days"] == 7
    assert 0.0 <= result["final_score"] <= 1.0
    assert result["is_anomalous"] is True


@pytest.mark.asyncio
async def test_temporal_typical_recent_week_not_anomalous(monkeypatch):
    _patch_validation_events(
        monkeypatch, _daily_rows(84, last_week_burst=False)
    )
    result = await TemporalAnomalyOrchestrator().analyze(
        client=None,
        anomaly_type=AnomalyType.VISITOR,
        estate_id=str(uuid4()),
    )
    assert result["detail"]["computed"] is True
    assert result["is_anomalous"] is False


@pytest.mark.asyncio
async def test_temporal_errors_when_history_below_three_windows(monkeypatch):
    # 10 days of history < 3 x 7 = 21 -> error.
    _patch_validation_events(monkeypatch, _daily_rows(10))
    with pytest.raises(LogHistoryError) as exc:
        await TemporalAnomalyOrchestrator().analyze(
            client=None,
            anomaly_type=AnomalyType.COMBINED,
            estate_id=str(uuid4()),
        )
    assert exc.value.status_code == 422
    assert "at least" in exc.value.message
