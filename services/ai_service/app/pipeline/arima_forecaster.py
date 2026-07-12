"""
Non-seasonal ARIMA forecasting for daily validation volume.

Follows the reference methodology: an Augmented Dickey-Fuller (ADF)
stationarity test drives the differencing order ``d``, a small AIC grid
search picks ``p`` and ``q``, the fitted model produces a ``horizon``-step
forecast with a 95% interval, and an 80/20 split yields an RMSE backtest.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import adfuller

from app.core.exceptions import VolumeForecastError

logger = logging.getLogger(__name__)

#: Fewer observations than this cannot support a meaningful ARIMA fit.
MIN_OBSERVATIONS = 14
#: ADF p-value at or below this marks the series stationary (article: 0.05).
STATIONARITY_ALPHA = 0.05
#: Search bounds for the AR (p) and MA (q) orders.
MAX_P = 3
MAX_Q = 3
#: Maximum differencing order attempted when the series is non-stationary.
MAX_D = 2


@dataclass
class ForecastResult:
    """Structured ARIMA output for assembly into the API response."""

    order: tuple[int, int, int]
    aic: float | None
    adf_statistic: float | None
    adf_pvalue: float | None
    differencing_applied: int
    is_stationary: bool
    forecast: list[dict[str, Any]] = field(default_factory=list)
    backtest: dict[str, Any] | None = None
    notes: str | None = None


def _run_adf(series: pd.Series) -> tuple[float | None, float | None, bool]:
    """Return ``(adf_statistic, p_value, is_stationary)`` for the series."""
    try:
        result = adfuller(series.values)
    except Exception as exc:  # noqa: BLE001 - degenerate series
        logger.debug("ADF test failed: %s", exc)
        return None, None, False
    stat = float(result[0])
    pvalue = float(result[1])
    return stat, pvalue, pvalue <= STATIONARITY_ALPHA


def _select_d(
    series: pd.Series,
) -> tuple[int, float | None, float | None, bool]:
    """
    Choose the differencing order via repeated ADF tests.

    Returns ``(d, adf_statistic_of_original, p_value_of_original,
    is_stationary_after_d)``. Stops at ``MAX_D``.
    """
    stat, pvalue, stationary = _run_adf(series)
    if stationary:
        return 0, stat, pvalue, True

    differenced = series
    for d in range(1, MAX_D + 1):
        differenced = differenced.diff().dropna()
        if len(differenced) < 3:
            break
        _, _, stationary_now = _run_adf(differenced)
        if stationary_now:
            return d, stat, pvalue, True
    return MAX_D, stat, pvalue, False


def _fit_arima(series: pd.Series, order: tuple[int, int, int]) -> Any:
    """Fit an ARIMA model, silencing convergence/frequency warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ARIMA(series, order=order)
        return model.fit()


def _select_order(
    series: pd.Series, d: int
) -> tuple[tuple[int, int, int], float | None]:
    """Grid-search ``p`` and ``q`` at fixed ``d``; keep the lowest-AIC fit."""
    best_order = (1, d, 0)
    best_aic: float | None = None
    for p in range(MAX_P + 1):
        for q in range(MAX_Q + 1):
            if p == 0 and q == 0:
                continue
            order = (p, d, q)
            try:
                fitted = _fit_arima(series, order)
            except Exception as exc:  # noqa: BLE001 - many orders fail to fit
                logger.debug("ARIMA%s fit failed: %s", order, exc)
                continue
            aic = float(fitted.aic)
            if best_aic is None or aic < best_aic:
                best_aic = aic
                best_order = order
    return best_order, best_aic


def _future_dates(series: pd.Series, horizon: int) -> pd.DatetimeIndex:
    last = series.index[-1]
    return pd.date_range(
        start=last + pd.Timedelta(days=1), periods=horizon, freq="D"
    )


def _clip_round(value: float) -> float:
    """Volume is a non-negative integer count."""
    return float(max(0.0, round(float(value))))


def _flat_series_result(
    series: pd.Series,
    horizon: int,
    adf_stat: float | None,
    adf_pvalue: float | None,
) -> ForecastResult:
    """Naive constant forecast for constant/degenerate series (ARIMA unstable)."""
    level = float(series.iloc[-1])
    dates = _future_dates(series, horizon)
    points = [
        {
            "date": d.strftime("%Y-%m-%d"),
            "predicted": _clip_round(level),
            "lower": _clip_round(level),
            "upper": _clip_round(level),
        }
        for d in dates
    ]
    return ForecastResult(
        order=(0, 0, 0),
        aic=None,
        adf_statistic=adf_stat,
        adf_pvalue=adf_pvalue,
        differencing_applied=0,
        is_stationary=True,
        forecast=points,
        backtest=None,
        notes=(
            "Series is constant; returned a naive constant forecast instead of "
            "fitting ARIMA."
        ),
    )


def _backtest(
    series: pd.Series, order: tuple[int, int, int]
) -> dict[str, Any] | None:
    """Retrospective 80/20 forecast RMSE (skipped when the test split is tiny)."""
    train_size = int(len(series) * 0.8)
    test_size = len(series) - train_size
    if train_size < MIN_OBSERVATIONS or test_size < 1:
        return None
    train, test = series.iloc[:train_size], series.iloc[train_size:]
    try:
        fitted = _fit_arima(train, order)
        forecast = fitted.get_forecast(steps=test_size)
        predicted = np.asarray(forecast.predicted_mean, dtype="float64")
        rmse = float(mean_squared_error(test.values, predicted) ** 0.5)
    except Exception as exc:  # noqa: BLE001 - backtest is best-effort
        logger.debug("ARIMA backtest failed for order %s: %s", order, exc)
        return None
    return {"rmse": rmse, "train_size": train_size, "test_size": test_size}


def run_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    """
    Fit ARIMA to ``series`` and forecast ``horizon`` days ahead.

    Raises:
        VolumeForecastError: If there are fewer than ``MIN_OBSERVATIONS`` days.
    """
    if len(series) < MIN_OBSERVATIONS:
        raise VolumeForecastError(
            f"Need at least {MIN_OBSERVATIONS} days of history to forecast; "
            f"got {len(series)}.",
            status_code=422,
        )

    if float(series.std()) == 0.0:
        stat, pvalue, _ = _run_adf(series)
        return _flat_series_result(series, horizon, stat, pvalue)

    d, adf_stat, adf_pvalue, is_stationary = _select_d(series)
    order, aic = _select_order(series, d)

    try:
        fitted = _fit_arima(series, order)
        forecast = fitted.get_forecast(steps=horizon)
        mean = np.asarray(forecast.predicted_mean, dtype="float64")
        conf = np.asarray(forecast.conf_int(alpha=0.05), dtype="float64")
    except Exception as exc:  # noqa: BLE001 - fall back to naive on failure
        logger.warning("ARIMA%s forecast failed: %s", order, exc)
        return _flat_series_result(series, horizon, adf_stat, adf_pvalue)

    dates = _future_dates(series, horizon)
    points = [
        {
            "date": dates[i].strftime("%Y-%m-%d"),
            "predicted": _clip_round(mean[i]),
            "lower": _clip_round(conf[i, 0]),
            "upper": _clip_round(conf[i, 1]),
        }
        for i in range(horizon)
    ]

    return ForecastResult(
        order=order,
        aic=aic,
        adf_statistic=adf_stat,
        adf_pvalue=adf_pvalue,
        differencing_applied=d,
        is_stationary=is_stationary,
        forecast=points,
        backtest=_backtest(series, order),
        notes=None,
    )
