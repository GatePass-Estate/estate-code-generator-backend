"""Which log table ids are used for a feature-engineering lookup or row."""

from enum import StrEnum


class LogKind(StrEnum):
    """Visitor vs resident log rows (``visitorlog`` / ``residentlog``)."""

    VISITOR = "visitor"
    RESIDENT = "resident"
