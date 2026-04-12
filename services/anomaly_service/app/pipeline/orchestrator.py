"""Wires scope → wrangle → features → analysis → transparency."""

from typing import Any

from app.domain.scopes import AnalysisScope
from app.pipeline.analysis_manager import ensemble_score
from app.pipeline.base import StubScopeAnalysis
from app.pipeline.data_wrangler import wrangle_visit_records
from app.pipeline.feature_engineer import build_feature_vector
from app.pipeline.scope_manager import resolve_scopes
from app.pipeline.transparency_manager import explain


def _impl_for_scope(scope: AnalysisScope) -> StubScopeAnalysis:
    return StubScopeAnalysis(scope)


class AnomalyOrchestrator:
    async def analyze(
        self,
        *,
        raw_records: list[dict[str, Any]],
        scopes: list[AnalysisScope] | None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = context or {}
        resolved = resolve_scopes(scopes)
        cleaned = await wrangle_visit_records(raw_records)

        scope_scores: dict[str, float] = {}
        for scope in resolved:
            impl = _impl_for_scope(scope)
            feats = await build_feature_vector(impl, cleaned, ctx)
            scope_scores[scope.value] = await impl.score(feats)

        final = await ensemble_score(list(scope_scores.values()))
        explanation = explain(final, scope_scores, model_outputs={})

        return {
            "final_score": final,
            "per_scope_scores": scope_scores,
            "explanation": explanation,
            "scopes_evaluated": [s.value for s in resolved],
        }
