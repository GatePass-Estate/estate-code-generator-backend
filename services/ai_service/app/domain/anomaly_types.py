"""High-level anomaly detection mode (who the analysis is centred on)."""

from enum import StrEnum


class AnomalyType(StrEnum):
    """Visitor- vs resident-centred pipelines (each subclasses the ABC)."""

    VISITOR = "visitor"
    RESIDENT = "resident"
