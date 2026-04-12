"""Resolves which analysis scopes apply for a given request (config-driven later)."""

from app.domain.scopes import AnalysisScope


def resolve_scopes(
    requested: list[AnalysisScope] | None,
    *,
    default: list[AnalysisScope] | None = None,
) -> list[AnalysisScope]:
    if requested:
        return list(requested)
    return default or [AnalysisScope.VISITOR]
