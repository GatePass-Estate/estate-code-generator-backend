"""Spatial anomaly orchestration: log fetch → scopes → features → detector scoring."""

from __future__ import annotations

import sys
from pathlib import Path

# ``python spatial_anomaly_orchestration.py`` from this folder puts
# ``.../app/pipeline`` on ``sys.path[0]``. Prepend ``services/ai_service`` so
# ``import app`` resolves to this microservice, not another package named ``app``.
_AI_SVC_ROOT = Path(__file__).resolve().parents[2]
if str(_AI_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_SVC_ROOT))

import asyncio
import json
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.domain.anomaly_types import AnomalyType
from app.domain.log_feature_store import (
    historical_vectors_for_scope,
    previous_anchor_log_ids,
)
from app.integrations.db_service_feature_engineering import (
    batch_lookup_engineered_features,
    log_kind_from_slices_source,
    upsert_focal_engineered_features,
)
from app.integrations.db_service_logs import (
    history_window_days,
    load_log_records_for_analysis,
)
from app.models.code_validation import CodeValidationPayload, Receiver
from app.models.spatial_anomaly_schema import (
    AnalysisTransparency,
    FeatureContribution,
    ScopeTransparencyDetail,
)
from app.pipeline.analysis_manager import (
    ensemble_score,
    run_models,
    score_from_model_outputs,
)
from app.pipeline.spatial_anomaly_pipeline import (
    RECORDS_PRE_SLICED_CONTEXT_KEY,
    pipeline_for_type,
)
from app.pipeline.feature_engineer import build_feature_vector
from app.pipeline.scope_manager import resolve_scopes_for_pipeline
from app.pipeline.transparency_manager import explain


class SpatialAnomalyOrchestrator:
    """
    Coordinates visit log fetch, per-scope feature engineering, K-means/DBSCAN/LOF
    scoring, ensemble aggregation, transparency, and feature-store persistence.
    """

    async def analyze(
        self,
        *,
        client: httpx.AsyncClient,
        anomaly_type: AnomalyType,
        code_validation: CodeValidationPayload,
    ) -> dict[str, Any]:
        """
        End-to-end analysis: fetch logs, clean rows, engineer per-scope features,
        run detector models (K-means, DBSCAN, LOF), aggregate scores, and attach
        transparency payloads.

        Returns:
            A dict compatible with ``SpatialAnalyzeResponse`` (including nested
            ``transparency``).
        """
        log_slices = await load_log_records_for_analysis(
            client, settings, code_validation
        )
        focal_record = log_slices.focal_record

        pipeline = pipeline_for_type(anomaly_type)
        ctx: dict[str, Any] = {
            **code_validation.model_dump(mode="json"),
            "trigger_context": {"anomaly_type": anomaly_type.value},
            "focal_record": focal_record,
            "history_window_days": float(history_window_days()),
            RECORDS_PRE_SLICED_CONTEXT_KEY: True,
        }

        resolved = resolve_scopes_for_pipeline(pipeline)

        scope_scores: dict[str, float] = {}
        scope_details: list[ScopeTransparencyDetail] = []
        global_model_outputs: dict[str, float] = {}
        focal_features_by_scope: dict[str, dict[str, float]] = {}
        log_kind = log_kind_from_slices_source(log_slices.source)

        # Per scope: focal vector → batch-load prior engineered rows (non-anomalous)
        # → K-means / DBSCAN / LOF vs history → pipeline score → transparency row.
        for scope in resolved:
            scope_rows = log_slices.rows_for_analysis_scope(scope)
            feats = await build_feature_vector(
                pipeline, scope, scope_rows, ctx
            )
            focal_features_by_scope[scope.value] = feats
            prev_log_ids = previous_anchor_log_ids(scope_rows, focal_record)
            stored_rows = await batch_lookup_engineered_features(
                client,
                settings,
                log_ids=prev_log_ids,
                anomaly_type=anomaly_type,
                log_kind=log_kind,
            )
            historical_vectors = historical_vectors_for_scope(
                stored_rows, scope
            )
            model_outputs = await run_models(
                scope=scope,
                focal_features=feats,
                historical_features=historical_vectors,
            )
            for k, v in model_outputs.items():
                global_model_outputs[f"{scope.value}:{k}"] = v
            # Both anomaly types use the same detector-based scoring logic.
            # The only difference between visitor vs resident is the scopes run.
            score = score_from_model_outputs(model_outputs)
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
                        "kmeans-distance-v1",
                        "dbscan-noise-v1",
                        "lof-neighbors-v1",
                    ],
                    model_outputs=dict(model_outputs),
                )
            )

        final = await ensemble_score(list(scope_scores.values()))

        focal_is_anomalous = (
            final >= settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD
        )

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

        out = {
            "final_score": final,
            "per_scope_scores": scope_scores,
            "explanation": explanation,
            "scopes_evaluated": [s.value for s in resolved],
            "anomaly_type": anomaly_type.value,
            "is_anomalous": focal_is_anomalous,
            "transparency": transparency.model_dump(),
        }
        prediction_result_id = await upsert_focal_engineered_features(
            client,
            settings,
            code_validation=code_validation,
            anomaly_type=anomaly_type,
            features_by_scope_value=focal_features_by_scope,
            log_kind=log_kind,
            is_anomalous=focal_is_anomalous,
            prediction_result=out,
        )
        out["prediction_result_id"] = prediction_result_id
        return out


async def _main() -> None:
    """Local e2e: replace UUIDs and ``hashed_code`` with real db-service values."""
    code_validation = CodeValidationPayload(
        user_id=UUID("ea544461-05f0-43f0-b207-066d5f128a07"),
        security_id=UUID("5eaaf13e-d9e2-4e01-a65d-277fb55623b0"),
        estate_id=UUID("6eb0c18d-5505-4601-a211-1584b6a5bc31"),
        hashed_code="NL2JG5",
        valid_until="2026-03-05 08:11:47.795922+00",
        is_expired=False,
        receiver=Receiver.VISITOR,
        visitor_log_id=UUID("51c43fa0-5432-4b39-94da-5299581c3537"),
        resident_log_id=None,
    )
    orch = SpatialAnomalyOrchestrator()
    async with httpx.AsyncClient(timeout=120.0) as client:
        result = await orch.analyze(
            client=client,
            anomaly_type=AnomalyType.VISITOR,
            code_validation=code_validation,
        )
    print("\n[__main__] analyze result:")
    print("\n" + json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
