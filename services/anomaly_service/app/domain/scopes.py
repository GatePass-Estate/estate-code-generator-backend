"""Analysis scopes from the design doc (abbreviations VS/RS/SS/EW)."""

from enum import StrEnum


class AnalysisScope(StrEnum):
    """Which behavioural lens to apply."""

    VISITOR = "visitor_specific"  # VS
    RESIDENT = "resident_specific"  # RS
    SECURITY = "security_specific"  # SS
    ESTATE_WIDE = "estate_wide"  # EW


class TriggerMode(StrEnum):
    """How the pipeline was invoked."""

    REALTIME = "realtime"  # e.g. post-validation Pub/Sub (future)
    BATCH = "batch"  # retrospective / scheduled
