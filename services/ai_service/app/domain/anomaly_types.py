"""High-level anomaly detection mode (who the analysis is centred on)."""

from enum import StrEnum


class AnomalyType(StrEnum):
    """
    Analysis subject.

    ``VISITOR`` and ``RESIDENT`` centre the analysis on one log stream and are
    supported by both the spatial and temporal endpoints. ``COMBINED`` merges
    visitor and resident history into a single series and is supported by the
    temporal (Matrix Profile) endpoint only.
    """

    VISITOR = "visitor"
    RESIDENT = "resident"
    COMBINED = "combined"
