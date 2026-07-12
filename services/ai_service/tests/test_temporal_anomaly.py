"""Orchestrator tests for temporal (Matrix Profile) anomaly detection."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import LogHistoryError
from app.domain.anomaly_types import AnomalyType
from app.pipeline import temporal_anomaly_orchestration as orch_mod
from app.pipeline.temporal_anomaly_orchestration import (
    TemporalAnomalyOrchestrator,
)

_UTC = timezone.utc
_START = datetime(2026, 1, 1, tzinfo=_UTC)


class _FakeHistory:
    """Minimal stand-in for ``EstateHistoryWindow``."""

    def __init__(self, rows, includes=("visitor_log",)):
        self.rows = rows
        self.includes = includes
        self.estate_id = "estate"


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


def _patch_history(monkeypatch, history: _FakeHistory) -> None:
    async def _fake_load(
        client, settings, *, estate_id, include_visitor, include_resident
    ):
        return history

    monkeypatch.setattr(
        orch_mod, "load_estate_history_for_temporal", _fake_load
    )


@pytest.mark.asyncio
async def test_temporal_flags_recent_burst(monkeypatch):
    _patch_history(
        monkeypatch, _FakeHistory(_daily_rows(84, last_week_burst=True))
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
    _patch_history(
        monkeypatch, _FakeHistory(_daily_rows(84, last_week_burst=False))
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
    _patch_history(monkeypatch, _FakeHistory(_daily_rows(10)))
    with pytest.raises(LogHistoryError) as exc:
        await TemporalAnomalyOrchestrator().analyze(
            client=None,
            anomaly_type=AnomalyType.COMBINED,
            estate_id=str(uuid4()),
        )
    assert exc.value.status_code == 422
    assert "at least" in exc.value.message
