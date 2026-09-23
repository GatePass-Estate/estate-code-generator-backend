#!/usr/bin/env python3
"""
Offline spatial anomaly eval harness (Phase 1).

Exercises history-confidence weighting and feature contributions on synthetic
fixtures without calling db-service. Extend with log replay when needed.

Run from ``services/ai_service``::

    python scripts/eval_spatial_anomaly.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

from app.domain import features as feat  # noqa: E402
from app.domain.scopes import AnalysisScope  # noqa: E402
from app.pipeline.analysis_manager import (  # noqa: E402
    ScopeEnsembleContext,
    run_models,
    score_from_model_outputs,
    weighted_ensemble_score,
)
from app.pipeline.feature_contributions import compute_feature_contributions  # noqa: E402
from app.pipeline.spatial_anomaly_eval import (  # noqa: E402
    evaluate_scope_row,
    is_anomalous,
    perturb_features,
)


async def _demo() -> None:
    focal = {
        feat.HOUR_OF_DAY: 23.0,
        feat.NIGHT_VISIT_FLAG: 1.0,
        feat.DAY_OF_WEEK: 6.0,
        feat.IS_WEEKEND: 1.0,
        feat.VISIT_HOUR_BUCKET: 3.0,
    }
    hist = [
        {
            feat.HOUR_OF_DAY: 9.0,
            feat.NIGHT_VISIT_FLAG: 0.0,
            feat.DAY_OF_WEEK: 2.0,
            feat.IS_WEEKEND: 0.0,
            feat.VISIT_HOUR_BUCKET: 1.0,
        }
        for _ in range(5)
    ]
    perturbed = perturb_features(focal, {feat.HOUR_OF_DAY: 2.0})

    model_out = await run_models(
        scope=AnalysisScope.TEMPORAL,
        focal_features=perturbed,
        historical_features=hist,
    )
    row = evaluate_scope_row(
        AnalysisScope.TEMPORAL,
        focal_features=perturbed,
        historical_features=hist,
        model_outputs=model_out,
        eligible_count=6,
    )
    ctx = ScopeEnsembleContext(
        scope=AnalysisScope.TEMPORAL,
        score=row.score,
        matched_count=row.matched,
        eligible_count=row.eligible,
    )
    final = weighted_ensemble_score([ctx])
    contribs = compute_feature_contributions(
        AnalysisScope.TEMPORAL,
        perturbed,
        hist,
        score_from_model_outputs(model_out),
    )
    print("=== spatial_anomaly_eval demo ===")
    print(
        f"scope={row.scope} score={row.score:.4f} confidence={row.history_confidence:.4f}"
    )
    print(f"final={final:.4f} anomalous={is_anomalous(final)}")
    print("top feature contributions:")
    for c in sorted(contribs, key=lambda x: float(x["weight"]), reverse=True)[
        :3
    ]:
        print(
            f"  {c['feature_name']}: weight={c['weight']} "
            f"contribution={c['contribution']}"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(_demo())
