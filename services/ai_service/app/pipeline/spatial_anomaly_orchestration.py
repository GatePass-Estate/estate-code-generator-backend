"""
End-to-end spatial anomaly orchestration.

Pipeline stages (see :meth:`SpatialAnomalyOrchestrator.analyze`):

1. **Fetch** — per-scope log cohorts via :func:`load_log_records_for_analysis`.
2. **Engineer** — active features only (:mod:`app.core.feature_config`).
3. **Reference** — batch-load stored non-anomalous vectors; exact-key schema match.
4. **Detect** — K-means, DBSCAN, LOF per scope (:mod:`app.pipeline.analysis_manager`).
5. **Ensemble** — history-confidence weighted scope mean.
6. **Persist** — upsert focal features + prediction payload to db-service.
"""

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
from app.core.ensemble_config import DETECTOR_WEIGHTS
from app.core.feature_config import feature_label, scope_label
from app.domain.anomaly_types import AnomalyType
from app.domain.log_feature_store import (
    historical_vectors_for_scope_matching_active,
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
    ScopeEnsembleWeight,
    ScopeTransparencyDetail,
)
from app.pipeline.analysis_manager import (
    ScopeEnsembleContext,
    run_models,
    score_from_model_outputs,
    weighted_ensemble_score,
)
from app.pipeline.feature_contributions import compute_feature_contributions
from app.pipeline.spatial_anomaly_pipeline import (
    RECORDS_PRE_SLICED_CONTEXT_KEY,
    pipeline_for_type,
)
from app.pipeline.feature_engineer import build_feature_vector
from app.pipeline.scope_manager import resolve_scopes_for_pipeline
from app.core.spatial_anomaly_trace import trace, trace_json
from app.pipeline.spatial_anomaly_payload import round_payload_floats
from app.pipeline.transparency_manager import explain


def _trace_log_slices(log_slices: Any) -> None:
    trace(
        "log-history",
        "per-scope wrangled slices loaded from db-service",
        source=log_slices.source,
        focal_log_id=log_slices.focal_record.get("id"),
        merged_full_rows=len(log_slices.merged_full),
        temporal_rows=len(log_slices.temporal),
        visitor_specific_rows=len(log_slices.visitor_specific),
        resident_specific_rows=len(log_slices.resident_specific),
        security_specific_rows=len(log_slices.security_specific),
        estate_wide_rows=len(log_slices.estate_wide),
    )


class SpatialAnomalyOrchestrator:
    """
    Coordinates the spatial anomaly ``/analyze`` path.

    Owns HTTP I/O to db-service (logs + feature store), delegates detector math
    to :mod:`app.pipeline.analysis_manager`, and writes engineered features back
    after scoring. Does not render result-page UI payloads.
    """

    async def analyze(
        self,
        *,
        client: httpx.AsyncClient,
        anomaly_type: AnomalyType,
        code_validation: CodeValidationPayload,
    ) -> dict[str, Any]:
        """
        Run full spatial anomaly analysis for one gate validation.

        Step-by-step:

        1. Load anchor + per-scope history (:class:`LogHistorySlices`).
        2. For each pipeline scope — engineer focal vector, resolve prior log ids,
           batch-load stored vectors (schema-filtered), run three detectors.
        3. Build :class:`ScopeEnsembleContext` rows (matched/eligible counts feed
           ``history_confidence``).
        4. Compute :func:`weighted_ensemble_score` → compare to
           ``ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD``.
        5. Attach transparency (scope scores, weights, feature contributions).
        6. Upsert focal features and prediction JSON to the feature store.

        Returns:
            Dict compatible with ``SpatialAnalyzeResponse`` (includes
            ``transparency``, ``prediction_result_id`` after persist).
        """
        trace(
            "analyze-in",
            "incoming code validation",
            anomaly_type=anomaly_type.value,
            estate_id=code_validation.estate_id,
            receiver=code_validation.receiver.value,
            visitor_log_id=code_validation.visitor_log_id,
            resident_log_id=code_validation.resident_log_id,
            hashed_code=code_validation.hashed_code,
        )

        # Step 1 — parallel per-scope db fetches ending at anchor time.
        log_slices = await load_log_records_for_analysis(
            client, settings, code_validation
        )
        focal_record = log_slices.focal_record
        _trace_log_slices(log_slices)

        pipeline = pipeline_for_type(anomaly_type)
        ctx: dict[str, Any] = {
            **code_validation.model_dump(mode="json"),
            "trigger_context": {"anomaly_type": anomaly_type.value},
            "focal_record": focal_record,
            "history_window_days": float(history_window_days()),
            RECORDS_PRE_SLICED_CONTEXT_KEY: True,
        }

        resolved = resolve_scopes_for_pipeline(pipeline)
        trace(
            "scopes-resolved",
            "analysis scopes for this pipeline",
            scopes=[s.value for s in resolved],
        )

        scope_scores: dict[str, float] = {}
        scope_details: list[ScopeTransparencyDetail] = []
        ensemble_contexts: list[ScopeEnsembleContext] = []
        scope_weight_details: list[ScopeEnsembleWeight] = []
        global_model_outputs: dict[str, float] = {}
        focal_features_by_scope: dict[str, dict[str, float]] = {}
        log_kind = log_kind_from_slices_source(log_slices.source)

        # Step 2 — per-scope feature engineering, history lookup, detector scoring.
        for scope in resolved:
            scope_rows = log_slices.rows_for_analysis_scope(scope)
            feats = await build_feature_vector(
                pipeline, scope, scope_rows, ctx
            )
            focal_features_by_scope[scope.value] = feats
            # Temporal uses resident cohort ids; other scopes use their own slice.
            history_rows = log_slices.rows_for_history_lookup(scope)
            prev_log_ids = previous_anchor_log_ids(history_rows, focal_record)
            stored_rows = await batch_lookup_engineered_features(
                client,
                settings,
                log_ids=prev_log_ids,
                anomaly_type=anomaly_type,
                log_kind=log_kind,
            )
            historical_vectors, schema_excluded = (
                historical_vectors_for_scope_matching_active(
                    stored_rows, scope
                )
            )
            model_outputs = await run_models(
                scope=scope,
                focal_features=feats,
                historical_features=historical_vectors,
            )
            model_outputs["historical_excluded_schema_mismatch_count"] = float(
                schema_excluded
            )
            for k, v in model_outputs.items():
                global_model_outputs[f"{scope.value}:{k}"] = v
            # Both anomaly types use the same detector-based scoring logic.
            # The only difference between visitor vs resident is the scopes run.
            score = score_from_model_outputs(model_outputs)
            scope_scores[scope.value] = score
            matched = int(model_outputs.get("historical_reference_count", 0))
            eligible = len(prev_log_ids)
            ctx_row = ScopeEnsembleContext(
                scope=scope,
                score=score,
                matched_count=matched,
                eligible_count=eligible,
                excluded_schema_mismatch_count=schema_excluded,
                anomaly_type=anomaly_type,
            )
            ensemble_contexts.append(ctx_row)
            scope_weight_details.append(
                ScopeEnsembleWeight(
                    scope=scope.value,
                    label=scope_label(scope.value),
                    base_weight=ctx_row.base_weight,
                    history_confidence=ctx_row.history_confidence,
                    effective_weight=ctx_row.effective_weight,
                    matched_count=matched,
                    eligible_count=eligible,
                    excluded_schema_mismatch_count=schema_excluded,
                )
            )
            feat_rows = compute_feature_contributions(
                scope, feats, historical_vectors, score
            )
            scope_detail = ScopeTransparencyDetail(
                scope=scope.value,
                label=scope_label(scope.value),
                score=score,
                feature_contributions=[
                    FeatureContribution(
                        feature_name=str(row["feature_name"]),
                        label=feature_label(str(row["feature_name"])),
                        value=float(row["value"]),
                        weight=(
                            float(row["weight"])
                            if row.get("weight") is not None
                            else None
                        ),
                        contribution=(
                            float(row["contribution"])
                            if row.get("contribution") is not None
                            else None
                        ),
                    )
                    for row in feat_rows
                ],
                thresholds={
                    "history_confidence": ctx_row.history_confidence,
                    "effective_weight": ctx_row.effective_weight,
                },
                model_ids=[
                    "kmeans-distance-v1",
                    "dbscan-noise-v1",
                    "lof-neighbors-v1",
                ],
                model_outputs=dict(model_outputs),
            )
            scope_details.append(scope_detail)
            trace(
                f"scope:{scope.value}",
                scope_label(scope.value),
                slice_rows=len(scope_rows),
                features=feats,
                history=f"{matched}/{eligible} refs (excluded={schema_excluded})",
                detectors=(
                    f"k={model_outputs.get('kmeans'):.3f} "
                    f"d={model_outputs.get('dbscan'):.3f} "
                    f"l={model_outputs.get('lof'):.3f} → score={score:.3f}"
                ),
                confidence=ctx_row.history_confidence,
                weight=ctx_row.effective_weight,
            )

        # Step 3 — collapse scopes with history-confidence weighting.
        final = weighted_ensemble_score(ensemble_contexts)
        trace(
            "ensemble",
            "history-confidence weighted final score",
            per_scope_scores=scope_scores,
            scope_weights=[sw.model_dump() for sw in scope_weight_details],
            final_score=final,
            threshold=settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD,
        )

        focal_is_anomalous = (
            final >= settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD
        )

        explanation = explain(
            final,
            scope_scores,
            model_outputs=global_model_outputs,
        )
        active_weights = [
            c for c in ensemble_contexts if c.effective_weight > 0.0
        ]
        notes = (
            f"Weighted mean over {len(active_weights)}/{len(ensemble_contexts)} "
            "scopes with history_confidence > 0."
        )
        transparency = AnalysisTransparency(
            scopes=scope_details,
            ensemble_method="history_confidence_weighted_mean",
            ensemble_notes=notes,
            scope_weights=scope_weight_details,
            detector_weights=dict(DETECTOR_WEIGHTS),
            global_model_outputs=global_model_outputs,
        )

        out = round_payload_floats(
            {
                "final_score": final,
                "per_scope_scores": scope_scores,
                "explanation": explanation,
                "scopes_evaluated": [s.value for s in resolved],
                "anomaly_type": anomaly_type.value,
                "is_anomalous": focal_is_anomalous,
                "transparency": transparency.model_dump(),
            }
        )
        trace_json("analyze-out", "final response payload (pre-persist)", out)
        # Step 4 — persist focal vectors so future runs can reference this visit.
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
        trace(
            "persist",
            "feature store upsert complete",
            prediction_result_id=prediction_result_id,
            is_anomalous=focal_is_anomalous,
        )
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
