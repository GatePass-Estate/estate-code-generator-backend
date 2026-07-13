"""Temporal anomaly orchestration: entire estate history -> daily series -> Matrix Profile."""

from __future__ import annotations

import sys
from pathlib import Path

# ``python temporal_anomaly_orchestration.py`` from this folder puts
# ``.../app/pipeline`` on ``sys.path[0]``. Prepend ``services/ai_service`` so
# ``import app`` resolves to this microservice, not another package named ``app``.
_AI_SVC_ROOT = Path(__file__).resolve().parents[2]
if str(_AI_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_SVC_ROOT))

import asyncio
import json
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.core.exceptions import LogHistoryError, VolumeForecastError
from app.domain.anomaly_types import AnomalyType
from app.domain.forecast_target import ForecastTarget
from app.integrations.db_service_validation_volume import (
    load_validation_events,
)
from app.models.temporal_anomaly_schema import TemporalMatrixProfileDetail
from app.pipeline.matrix_profile import score_latest_subsequence
from app.pipeline.volume_timeseries import build_daily_series


class TemporalAnomalyOrchestrator:
    """
    Scores an estate's most recent one-week window against its entire history.

    Loads full visitor/resident/combined validation history via
    ``load_validation_events``, bins timestamps into a daily count series with
    ``build_daily_series``, computes the Matrix Profile with a one-week
    subsequence, and scores the latest window as a discord. Unsupervised and
    self-contained: nothing is persisted to db-service.
    """

    async def analyze(
        self,
        *,
        client: httpx.AsyncClient,
        anomaly_type: AnomalyType,
        estate_id: str,
    ) -> dict[str, Any]:
        """
        End-to-end temporal analysis over an estate's entire history.

        Fetches unbounded validation events (no date window), builds a
        zero-filled daily series from first to last event day, then runs Matrix
        Profile scoring on the latest subsequence window.

        Raises:
            LogHistoryError: If no history exists, or the history spans fewer
            than ``settings.TEMPORAL_MIN_HISTORY_WINDOW_MULTIPLE`` subsequence
            windows (default 3 x 7 = 21 days).

        Returns:
            A dict compatible with ``TemporalAnalyzeResponse``.
        """
        window_days = int(settings.TEMPORAL_SUBSEQUENCE_WINDOW_DAYS)
        min_days = settings.TEMPORAL_MIN_HISTORY_WINDOW_MULTIPLE * window_days

        try:
            events = await load_validation_events(
                client,
                settings,
                estate_id=str(estate_id),
                target=ForecastTarget(anomaly_type.value),
                raise_if_empty=True,
                empty_message=(
                    "No log history found for the estate; "
                    "analysis cannot proceed."
                ),
                empty_status_code=404,
            )
        except VolumeForecastError as exc:
            raise LogHistoryError(
                exc.message,
                status_code=exc.status_code,
            ) from exc

        event_times = events.timestamps
        if not event_times:
            raise LogHistoryError(
                "Estate history has no parseable event timestamps; "
                "analysis cannot proceed.",
                status_code=422,
            )

        from_dt = min(event_times)
        to_dt = max(event_times)
        series = build_daily_series(event_times, from_dt, to_dt)

        history_days = int(series.shape[0])
        if history_days < min_days:
            raise LogHistoryError(
                f"Estate history spans {history_days} day(s); temporal "
                f"analysis needs at least {min_days} (3 x {window_days}-day "
                "window).",
                status_code=422,
            )

        result = score_latest_subsequence(series.values, m=window_days)
        final = result.score if result.computed else 0.0
        is_anomalous = final >= settings.TEMPORAL_ANOMALY_SCORE_THRESHOLD

        detail = TemporalMatrixProfileDetail(
            computed=result.computed,
            window_size_days=result.window_size,
            series_length_days=result.series_length,
            latest_window_index=result.latest_window_index,
            latest_profile_value=result.latest_profile_value,
            profile_mean=result.profile_mean,
            profile_max=result.profile_max,
            discord_index=result.discord_index,
            note=result.note,
        )
        explanation = (
            f"Temporal matrix-profile analysis final_score={final:.4f} on the "
            f"latest {window_days}-day window over {history_days} days of "
            f"history (subject={anomaly_type.value})."
        )

        return {
            "anomaly_type": anomaly_type.value,
            "final_score": final,
            "is_anomalous": is_anomalous,
            "explanation": explanation,
            "included_logs": list(events.includes),
            "detail": detail.model_dump(),
        }


async def _main() -> None:
    """Local e2e: replace the estate id with a real db-service value."""
    orch = TemporalAnomalyOrchestrator()
    async with httpx.AsyncClient(timeout=120.0) as client:
        result = await orch.analyze(
            client=client,
            anomaly_type=AnomalyType.COMBINED,
            estate_id=str(UUID("6eb0c18d-5505-4601-a211-1584b6a5bc31")),
        )
    print("\n[__main__] temporal analyze result:")
    print("\n" + json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
