"""
Validation-volume forecast orchestrator (daily counts -> ARIMA forecast).

Single ``forecast`` entry used by ``POST /volume-forecast/predict/{target}``.
Also runnable as a CLI for local end-to-end checks against db-service.
"""

from __future__ import annotations

# CLI: run ``python -m app.pipeline.volume_forecast_orchestrator`` from
# ``services/ai_service``.
import sys
from pathlib import Path

# ``python volume_forecast_orchestrator.py`` from this folder puts
# ``.../app/pipeline`` on ``sys.path[0]``. Prepend ``services/ai_service`` so
# ``import app`` resolves to this microservice, not another ``app`` package.
_AI_SVC_ROOT = Path(__file__).resolve().parents[2]
if str(_AI_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_SVC_ROOT))

import argparse
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.domain.forecast_target import ForecastTarget
from app.integrations.db_service_validation_volume import (
    load_validation_events,
)
from app.pipeline.arima_forecaster import run_forecast
from app.pipeline.volume_timeseries import build_daily_series


class VolumeForecastOrchestrator:
    """Coordinates db fetch, daily bucketing, and ARIMA forecasting."""

    async def forecast(
        self,
        *,
        client: httpx.AsyncClient,
        estate_id: UUID,
        target: ForecastTarget,
        history_days: int = 120,
        horizon: int = 14,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        max_records: int = 5000,
    ) -> dict[str, Any]:
        """
        Load estate validation events, build a zero-filled daily count
        series, fit ARIMA, and return a ``VolumeForecastResponse`` dict.
        """
        end = to_date or datetime.now(timezone.utc)
        start = from_date or (end - timedelta(days=history_days))

        timestamps = await load_validation_events(
            client,
            settings,
            estate_id=estate_id,
            target=target,
            from_dt=start,
            to_dt=end,
            max_records=max_records,
        )

        series = build_daily_series(timestamps, start, end)
        result = run_forecast(series, horizon)

        observations = int((series > 0).sum())
        has_rows = len(series) > 0
        history_start = (
            series.index[0].strftime("%Y-%m-%d") if has_rows else None
        )
        history_end = (
            series.index[-1].strftime("%Y-%m-%d") if has_rows else None
        )

        model = {
            "order": list(result.order),
            "aic": result.aic,
            "adf_statistic": result.adf_statistic,
            "adf_pvalue": result.adf_pvalue,
            "differencing_applied": result.differencing_applied,
            "is_stationary": result.is_stationary,
        }

        return {
            "target": target.value,
            "estate_id": str(estate_id),
            "bucket": "daily",
            "observations": observations,
            "history_start": history_start,
            "history_end": history_end,
            "model": model,
            "backtest": result.backtest,
            "forecast": result.forecast,
            "notes": result.notes,
        }


async def _run(
    *,
    estate_id: UUID,
    target: ForecastTarget,
    history_days: int,
    horizon: int,
    as_json: bool,
) -> None:
    """CLI harness: run forecast and print a short summary or full JSON."""
    orch = VolumeForecastOrchestrator()
    async with httpx.AsyncClient(timeout=120.0) as client:
        started = time.perf_counter()
        result = await orch.forecast(
            client=client,
            estate_id=estate_id,
            target=target,
            history_days=history_days,
            horizon=horizon,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)

    if as_json:
        payload = {**result, "latency_ms": latency_ms}
        print(json.dumps(payload, indent=2, default=str))
        return

    model = result["model"]
    backtest = result.get("backtest") or {}
    print("\n[__main__] volume forecast")
    print(
        f"target={result['target']} observations={result['observations']} "
        f"order={model['order']} aic={model['aic']} "
        f"rmse={backtest.get('rmse')} latency_ms={latency_ms}"
    )
    for point in result["forecast"]:
        print(
            f"  {point['date']}  predicted={point['predicted']}  "
            f"[{point['lower']}, {point['upper']}]"
        )
    if result.get("notes"):
        print(f"\nnote: {result['notes']}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Forecast daily validation volume with ARIMA.",
    )
    parser.add_argument(
        "--estate-id",
        type=UUID,
        default=UUID("6eb0c18d-5505-4601-a211-1584b6a5bc31"),
        help="Estate UUID (replace with your test estate).",
    )
    parser.add_argument(
        "--target",
        type=ForecastTarget,
        choices=list(ForecastTarget),
        default=ForecastTarget.COMBINED,
        help="Which validation stream to forecast (default: combined).",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=120,
        metavar="N",
        help="Look-back window in days (default: 120).",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=14,
        metavar="N",
        help="Days to forecast ahead (default: 14).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full forecast payload as JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    asyncio.run(
        _run(
            estate_id=args.estate_id,
            target=args.target,
            history_days=max(30, args.history_days),
            horizon=max(1, args.horizon),
            as_json=bool(args.json),
        )
    )


if __name__ == "__main__":
    main()
