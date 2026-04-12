"""Wires anomaly type → db log fetch → scopes → features → analysis."""

from typing import Any

import httpx

from app.core.config import settings
from app.domain.anomaly_types import AnomalyType
from app.integrations.db_service_logs import load_log_records_for_analysis
from app.models.schemas import (
    AnalysisTransparency,
    CodeValidationPayload,
    FeatureContribution,
    ScopeTransparencyDetail,
)
from app.pipeline.analysis_manager import ensemble_score, run_models
from app.pipeline.anomaly_pipeline import pipeline_for_type
from app.pipeline.data_wrangler import wrangle_visit_records
from app.pipeline.feature_engineer import build_feature_vector
from app.pipeline.scope_manager import resolve_scopes_for_pipeline
from app.pipeline.transparency_manager import explain


class AnomalyOrchestrator:
    async def analyze(
        self,
        *,
        client: httpx.AsyncClient,
        anomaly_type: AnomalyType,
        code_validation: CodeValidationPayload,
    ) -> dict[str, Any]:
        raw_records = await load_log_records_for_analysis(
            client, settings, code_validation
        )
        pipeline = pipeline_for_type(anomaly_type)
        ctx: dict[str, Any] = {
            **code_validation.model_dump(mode="json"),
            "trigger_context": {"anomaly_type": anomaly_type.value},
        }
        resolved = resolve_scopes_for_pipeline(pipeline)
        cleaned = await wrangle_visit_records(raw_records)

        scope_scores: dict[str, float] = {}
        scope_details: list[ScopeTransparencyDetail] = []
        global_model_outputs: dict[str, float] = {}

        for scope in resolved:
            feats = await build_feature_vector(pipeline, scope, cleaned, ctx)
            model_outputs = await run_models(feats)
            for k, v in model_outputs.items():
                global_model_outputs[f"{scope.value}:{k}"] = v
            score = await pipeline.score_scope(scope, feats)
            scope_scores[scope.value] = score
            scope_details.append(
                ScopeTransparencyDetail(
                    scope=scope.value,
                    score=score,
                    feature_contributions=[
                        FeatureContribution(
                            feature_name=name,
                            value=float(val),
                            weight=None,
                            contribution=None,
                        )
                        for name, val in feats.items()
                    ],
                    thresholds={},
                    model_ids=[
                        "stub-kmeans-v0",
                        "stub-dbscan-v0",
                        "stub-lfoa-v0",
                    ],
                    model_outputs=dict(model_outputs),
                )
            )

        final = await ensemble_score(list(scope_scores.values()))
        explanation = explain(
            final,
            scope_scores,
            model_outputs=global_model_outputs,
        )
        transparency = AnalysisTransparency(
            scopes=scope_details,
            ensemble_method="unweighted_mean",
            ensemble_notes="Placeholder until weighted ensemble is configured.",
            global_model_outputs=global_model_outputs,
        )

        return {
            "final_score": final,
            "per_scope_scores": scope_scores,
            "explanation": explanation,
            "scopes_evaluated": [s.value for s in resolved],
            "anomaly_type": anomaly_type.value,
            "transparency": transparency.model_dump(),
        }
