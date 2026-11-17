"""
Pydantic models for ``POST /api/v1/volume-forecast/predict/{target}``.

Daily validation-volume forecasting per estate using a non-seasonal ARIMA
model (ADF stationarity test, AIC order selection, train/test RMSE backtest).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import UUID4, BaseModel, Field


class VolumeForecastRequest(BaseModel):
    """
    Filter the estate's validation history that feeds the ARIMA model.

    Counts are bucketed **daily**. By default the look-back window is the
    last ``history_days`` up to now; ``from_date``/``to_date`` override it.
    """

    estate_id: UUID4
    history_days: int = Field(
        default=120,
        ge=30,
        le=730,
        description=(
            "Look-back length (days) when from_date/to_date are omitted."
        ),
    )
    horizon: int = Field(
        default=14,
        ge=1,
        le=60,
        description="Number of future days to forecast.",
    )
    from_date: datetime | None = Field(
        default=None,
        description="Explicit lower bound on the history window (UTC).",
    )
    to_date: datetime | None = Field(
        default=None,
        description="Explicit upper bound on the history window (UTC).",
    )
    max_records: int = Field(
        default=5000,
        ge=1,
        le=50000,
        description="Safety cap on validation rows pulled before bucketing.",
    )


class ForecastPoint(BaseModel):
    """One forecasted day: point estimate plus 95% confidence interval."""

    date: str
    predicted: float
    lower: float
    upper: float


class ArimaModelInfo(BaseModel):
    """Fitted ARIMA order, AIC, and stationarity diagnostics."""

    order: list[int] = Field(
        ...,
        description="Selected ``(p, d, q)`` order as a 3-element list.",
    )
    aic: float | None = None
    adf_statistic: float | None = None
    adf_pvalue: float | None = None
    differencing_applied: int = 0
    is_stationary: bool = False


class BacktestMetrics(BaseModel):
    """Retrospective 80/20 forecast accuracy (article's evaluation step)."""

    rmse: float
    train_size: int
    test_size: int


class VolumeForecastResponse(BaseModel):
    """API response for ``POST /volume-forecast/predict/{target}``."""

    target: str
    estate_id: str
    bucket: str = "daily"
    observations: int
    history_start: str | None = None
    history_end: str | None = None
    model: ArimaModelInfo
    backtest: BacktestMetrics | None = None
    forecast: list[ForecastPoint] = Field(default_factory=list)
    notes: str | None = None
