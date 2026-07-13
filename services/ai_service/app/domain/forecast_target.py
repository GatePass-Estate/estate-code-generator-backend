"""What validation stream the volume forecast is centred on."""

from enum import StrEnum


class ForecastTarget(StrEnum):
    """Which validation counts feed the ARIMA volume forecast."""

    VISITOR = "visitor"
    RESIDENT = "resident"
    COMBINED = "combined"
