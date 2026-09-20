#!/usr/bin/env python3
"""
Run spatial anomaly finetuning phases 0, 2, 5, and 6 against live db-service data.

Phases:
  0 — 30-day backfill + baseline replay scores
  2 — Small grid search over detector hyperparameters
  5 — Recommend ENSEMBLE threshold from mature-cohort replay p99
  6 — Expert-review batch for prior false positives (~0.86–0.92)

Run from ``services/ai_service``::

    poetry run python scripts/finetune_spatial_anomaly.py \\
        --estate-id 6eb0c18d-5505-4601-a211-1584b6a5bc31
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any
from uuid import UUID

_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

if "DB_SERVICE_URL" not in os.environ:
    os.environ["DB_SERVICE_URL"] = "http://localhost:9032/"

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.domain.anomaly_types import AnomalyType  # noqa: E402
from app.domain.log_kind import LogKind  # noqa: E402
from app.integrations.db_service_logs import history_window_days  # noqa: E402
from app.models.code_validation import CodeValidationPayload, Receiver  # noqa: E402
from app.pipeline.spatial_anomaly_orchestration import (  # noqa: E402
    SpatialAnomalyOrchestrator,
)

# Reuse backfill helpers from the upsert script (not a package — load by path).
import importlib.util  # noqa: E402

_UPSERT_PATH = _SVC_ROOT / "scripts" / "upsert_visitor_log_features.py"
_spec = importlib.util.spec_from_file_location(
    "upsert_visitor_log_features", _UPSERT_PATH
)
assert _spec and _spec.loader
_upsert = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_upsert)
_as_iso_z = _upsert._as_iso_z
_event_time_sort_key = _upsert._event_time_sort_key
_fetch_all_logs = _upsert._fetch_all_logs
_filter_rows_in_window = _upsert._filter_rows_in_window
run_backfill = _upsert.run

DEFAULT_ESTATE = UUID("6eb0c18d-5505-4601-a211-1584b6a5bc31")

DETECTOR_GRID: dict[str, list[Any]] = {
    "SPATIAL_KMEANS_HIST_DISTANCE_PERCENTILE": [90.0, 95.0, 98.0],
    "SPATIAL_DBSCAN_FALLBACK_EPS": [0.5, 0.75, 1.0],
    "SPATIAL_LOF_INLIER_MAX": [0.4, 0.5, 0.6],
}

MATURE_CONFIDENCE_MIN = 0.8
EXPERT_REVIEW_SCORE_MIN = 0.86
EXPERT_REVIEW_SCORE_MAX = 0.92


@dataclass
class ReplayRow:
    log_id: str
    display_name: str
    anomaly_type: str
    final_score: float
    is_anomalous: bool
    per_scope_scores: dict[str, float]
    scope_weights: list[dict[str, Any]]
    min_matched: int
    min_confidence: float
    max_confidence: float


@dataclass
class FinetuneReport:
    estate_id: str
    generated_at: str
    phase0_backfill: dict[str, Any] = field(default_factory=dict)
    phase0_baseline: dict[str, Any] = field(default_factory=dict)
    phase2_grid_search: dict[str, Any] = field(default_factory=dict)
    phase5_threshold: dict[str, Any] = field(default_factory=dict)
    phase6_expert_review: dict[str, Any] = field(default_factory=dict)


def _log_row_to_payload(
    rec: dict[str, Any],
    *,
    log_source: LogKind,
) -> CodeValidationPayload:
    anchor_id = UUID(str(rec["id"]))
    receiver = (
        Receiver.VISITOR
        if log_source == LogKind.VISITOR
        else Receiver.RESIDENT
    )
    valid_until_raw = (
        rec.get("visit_time")
        or rec.get("access_time")
        or rec.get("created_at")
        or ""
    )
    return CodeValidationPayload(
        user_id=UUID(str(rec["user_id"])),
        security_id=UUID(str(rec["security_id"])),
        estate_id=UUID(str(rec["estate_id"])),
        hashed_code=str(rec["hashed_code"]),
        valid_until=_as_iso_z(valid_until_raw),
        is_expired=False,
        receiver=receiver,
        visitor_log_id=anchor_id if log_source == LogKind.VISITOR else None,
        resident_log_id=anchor_id if log_source == LogKind.RESIDENT else None,
        visitor_fullname=rec.get("visitor_fullname"),
        relationship_with_resident=(
            str(rec["relationship_with_resident"])
            if rec.get("relationship_with_resident") is not None
            else None
        ),
        gender=str(rec["gender"]) if rec.get("gender") is not None else None,
    )


def _scope_weight_summary(
    transparency: dict[str, Any],
) -> tuple[int, float, float]:
    weights = transparency.get("scope_weights") or []
    matched_vals = [int(w.get("matched_count") or 0) for w in weights]
    conf_vals = [float(w.get("history_confidence") or 0.0) for w in weights]
    if not matched_vals:
        return 0, 0.0, 0.0
    return min(matched_vals), min(conf_vals), max(conf_vals)


async def _replay_logs(
    client: httpx.AsyncClient,
    *,
    estate_id: UUID,
    log_source: LogKind,
    anomaly_type: AnomalyType,
    sample_limit: int | None = None,
    persist: bool = False,
) -> list[ReplayRow]:
    """Re-score logs through the orchestrator (optional no-op persistence)."""
    rows = await _fetch_all_logs(client, log_source=log_source, page_size=100)
    targets = _filter_rows_in_window(
        rows,
        history_days=history_window_days(),
        estate_id=estate_id,
    )
    targets.sort(key=_event_time_sort_key)
    if sample_limit is not None:
        # Evenly spaced sample for faster grid search.
        if len(targets) > sample_limit:
            step = max(1, len(targets) // sample_limit)
            targets = targets[::step][:sample_limit]

    orch = SpatialAnomalyOrchestrator()
    out: list[ReplayRow] = []

    if not persist:
        import app.integrations.db_service_feature_engineering as fe

        async def _noop_upsert(*_a: Any, **_k: Any) -> None:
            return None

        original = fe.upsert_focal_engineered_features
        fe.upsert_focal_engineered_features = _noop_upsert  # type: ignore[method-assign]
    else:
        original = None

    try:
        for rec in targets:
            payload = _log_row_to_payload(rec, log_source=log_source)
            result = await orch.analyze(
                client=client,
                anomaly_type=anomaly_type,
                code_validation=payload,
            )
            transparency = result.get("transparency") or {}
            min_m, min_c, max_c = _scope_weight_summary(transparency)
            name = (
                rec.get("visitor_fullname")
                or rec.get("resident_fullname")
                or str(rec.get("id"))
            )
            out.append(
                ReplayRow(
                    log_id=str(rec["id"]),
                    display_name=str(name),
                    anomaly_type=anomaly_type.value,
                    final_score=float(result["final_score"]),
                    is_anomalous=bool(result["is_anomalous"]),
                    per_scope_scores=dict(
                        result.get("per_scope_scores") or {}
                    ),
                    scope_weights=list(
                        transparency.get("scope_weights") or []
                    ),
                    min_matched=min_m,
                    min_confidence=min_c,
                    max_confidence=max_c,
                )
            )
    finally:
        if original is not None:
            import app.integrations.db_service_feature_engineering as fe

            fe.upsert_focal_engineered_features = original  # type: ignore[method-assign]

    return out


def _metrics_from_replays(rows: list[ReplayRow]) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "flag_rate": 0.0,
            "thin_history_flag_rate": 0.0,
            "mature_cohort_flag_rate": 0.0,
            "mean_score": 0.0,
            "p99_score": 0.0,
        }

    thin = [
        r
        for r in rows
        if r.min_matched < settings.SPATIAL_MIN_MATCHED_TO_SCORE
    ]
    mature = [r for r in rows if r.min_confidence >= MATURE_CONFIDENCE_MIN]
    scores = [r.final_score for r in rows]

    def _flag_rate(group: list[ReplayRow]) -> float:
        if not group:
            return 0.0
        return sum(1 for r in group if r.is_anomalous) / len(group)

    sorted_scores = sorted(scores)
    p99_idx = max(0, int(len(sorted_scores) * 0.99) - 1)

    return {
        "count": len(rows),
        "flag_rate": _flag_rate(rows),
        "thin_history_flag_rate": _flag_rate(thin),
        "thin_history_count": len(thin),
        "mature_cohort_flag_rate": _flag_rate(mature),
        "mature_cohort_count": len(mature),
        "mean_score": statistics.mean(scores),
        "p99_score": sorted_scores[p99_idx],
    }


def _apply_settings_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """Mutate ``settings`` in place; return prior values for restore."""
    prior: dict[str, Any] = {}
    for key, value in patch.items():
        prior[key] = getattr(settings, key)
        setattr(settings, key, value)
    return prior


def _restore_settings(prior: dict[str, Any]) -> None:
    for key, value in prior.items():
        setattr(settings, key, value)


async def _fetch_prior_predictions(
    client: httpx.AsyncClient,
    *,
    estate_id: UUID,
) -> list[dict[str, Any]]:
    url = f"{settings.DB_SERVICE_URL.rstrip('/')}/api/v1/codeservice/predictionresult/search"
    all_items: list[dict[str, Any]] = []
    page = 1
    while True:
        r = await client.get(
            url,
            params={
                "estate_id": str(estate_id),
                "page": page,
                "limit": 100,
                "sort_order": "desc",
            },
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or []
        total = int(data.get("total") or 0)
        all_items.extend(items)
        if not items or len(all_items) >= total:
            break
        page += 1
    return all_items


async def run_phase0(
    client: httpx.AsyncClient,
    *,
    estate_id: UUID,
    skip_backfill: bool,
) -> dict[str, Any]:
    print("\n=== Phase 0: backfill + baseline ===")
    backfill_summary: dict[str, Any] = {"skipped": skip_backfill}

    if not skip_backfill:
        for log_source, anomaly_type in (
            (LogKind.VISITOR, AnomalyType.VISITOR),
            (LogKind.RESIDENT, AnomalyType.RESIDENT),
        ):
            label = f"{log_source.value}_{anomaly_type.value}"
            print(f"  Backfilling {label}...")
            await run_backfill(
                log_source=log_source,
                anomaly_type=anomaly_type,
                is_anomalous=False,
                estate_id_override=estate_id,
                history_days=history_window_days(),
                page_size=100,
            )
            backfill_summary[label] = "completed"

    visitor_replay = await _replay_logs(
        client,
        estate_id=estate_id,
        log_source=LogKind.VISITOR,
        anomaly_type=AnomalyType.VISITOR,
        persist=False,
    )
    resident_replay = await _replay_logs(
        client,
        estate_id=estate_id,
        log_source=LogKind.RESIDENT,
        anomaly_type=AnomalyType.RESIDENT,
        persist=False,
    )
    all_replay = visitor_replay + resident_replay
    metrics = _metrics_from_replays(all_replay)

    print(
        f"  Replayed {metrics['count']} logs — "
        f"flag_rate={metrics['flag_rate']:.1%}, "
        f"thin_history_flag_rate={metrics['thin_history_flag_rate']:.1%}, "
        f"mature_flag_rate={metrics['mature_cohort_flag_rate']:.1%}"
    )

    return {
        "backfill": backfill_summary,
        "metrics": metrics,
        "visitor_samples": [asdict(r) for r in visitor_replay[:5]],
        "resident_samples": [asdict(r) for r in resident_replay[:5]],
    }


async def run_phase2(
    client: httpx.AsyncClient,
    *,
    estate_id: UUID,
) -> dict[str, Any]:
    print("\n=== Phase 2: detector grid search (sampled replay) ===")
    keys = list(DETECTOR_GRID.keys())
    combos = [
        dict(zip(keys, values))
        for values in product(*(DETECTOR_GRID[k] for k in keys))
    ]
    print(f"  Testing {len(combos)} parameter combinations on sampled logs...")

    results: list[dict[str, Any]] = []
    baseline_prior = {k: getattr(settings, k) for k in keys}

    for idx, patch in enumerate(combos, start=1):
        prior = _apply_settings_patch(patch)
        try:
            visitor = await _replay_logs(
                client,
                estate_id=estate_id,
                log_source=LogKind.VISITOR,
                anomaly_type=AnomalyType.VISITOR,
                sample_limit=20,
                persist=False,
            )
            metrics = _metrics_from_replays(visitor)
            row = {**patch, **metrics}
            results.append(row)
            print(
                f"  [{idx}/{len(combos)}] thin_FPR={metrics['thin_history_flag_rate']:.1%} "
                f"mature_FPR={metrics['mature_cohort_flag_rate']:.1%} "
                f"mean={metrics['mean_score']:.3f}"
            )
        finally:
            _restore_settings(prior)

    _restore_settings(baseline_prior)

    # Rank: thin-history FPR ≈ 0 first, then lowest mature FPR, then lowest mean.
    ranked = sorted(
        results,
        key=lambda r: (
            r["thin_history_flag_rate"],
            r["mature_cohort_flag_rate"],
            r["mean_score"],
        ),
    )
    best = ranked[0] if ranked else {}
    print(f"  Best combo: { {k: best.get(k) for k in keys} }")

    return {
        "grid_size": len(combos),
        "sample_limit": 20,
        "ranked_top5": [
            {
                k: row.get(k)
                for k in keys
                + [
                    "thin_history_flag_rate",
                    "mature_cohort_flag_rate",
                    "mean_score",
                ]
            }
            for row in ranked[:5]
        ],
        "recommended_patch": {k: best.get(k) for k in keys},
        "all_results": results,
    }


async def run_phase5(
    client: httpx.AsyncClient,
    *,
    estate_id: UUID,
    detector_patch: dict[str, Any],
) -> dict[str, Any]:
    print("\n=== Phase 5: threshold calibration (mature cohort p99) ===")
    prior = _apply_settings_patch(detector_patch)
    try:
        visitor = await _replay_logs(
            client,
            estate_id=estate_id,
            log_source=LogKind.VISITOR,
            anomaly_type=AnomalyType.VISITOR,
            persist=False,
        )
        resident = await _replay_logs(
            client,
            estate_id=estate_id,
            log_source=LogKind.RESIDENT,
            anomaly_type=AnomalyType.RESIDENT,
            persist=False,
        )
    finally:
        _restore_settings(prior)

    mature = [
        r
        for r in visitor + resident
        if r.min_confidence >= MATURE_CONFIDENCE_MIN
    ]
    mature_scores = sorted(r.final_score for r in mature)
    if mature_scores:
        p99_idx = max(0, int(len(mature_scores) * 0.99) - 1)
        p95_idx = max(0, int(len(mature_scores) * 0.95) - 1)
        recommended = min(0.99, mature_scores[p99_idx] + 0.02)
    else:
        p99_idx = p95_idx = 0
        recommended = settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD

    print(
        f"  Mature cohort n={len(mature)} — "
        f"p95={mature_scores[p95_idx]:.3f} p99={mature_scores[p99_idx]:.3f} "
        f"recommended_threshold={recommended:.3f} "
        f"(current={settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD})"
    )

    return {
        "mature_cohort_count": len(mature),
        "p95_score": mature_scores[p95_idx] if mature_scores else None,
        "p99_score": mature_scores[p99_idx] if mature_scores else None,
        "current_threshold": settings.ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD,
        "recommended_threshold": recommended,
        "note": (
            "Set ENSEMBLE_ANOMALOUS_SCORE_THRESHOLD to recommended_threshold "
            "after expert review confirms mature-cohort false positives drop."
        ),
    }


async def run_phase6(
    client: httpx.AsyncClient,
    *,
    estate_id: UUID,
    detector_patch: dict[str, Any],
    replay_rows: list[ReplayRow] | None = None,
) -> dict[str, Any]:
    print("\n=== Phase 6: expert review batch (0.86–0.92 band) ===")
    prior_preds = await _fetch_prior_predictions(client, estate_id=estate_id)
    band_preds = [
        p
        for p in prior_preds
        if EXPERT_REVIEW_SCORE_MIN
        <= float(p.get("final_score") or 0)
        <= EXPERT_REVIEW_SCORE_MAX
    ]

    prior = _apply_settings_patch(detector_patch)
    try:
        if replay_rows is None:
            replay_rows = await _replay_logs(
                client,
                estate_id=estate_id,
                log_source=LogKind.VISITOR,
                anomaly_type=AnomalyType.VISITOR,
                persist=False,
            )
    finally:
        _restore_settings(prior)

    replay_by_name = {r.display_name: r for r in replay_rows}
    review_cases: list[dict[str, Any]] = []

    for pred in band_preds:
        pred_id = str(pred.get("id"))
        score_before = float(pred.get("final_score") or 0)
        name = str(pred.get("display_name") or "")
        replay = replay_by_name.get(name)
        review_cases.append(
            {
                "prediction_id": pred_id,
                "display_name": name,
                "anomaly_type": pred.get("anomaly_type"),
                "score_before": score_before,
                "score_after": replay.final_score if replay else None,
                "is_anomalous_before": bool(pred.get("is_anomalous")),
                "is_anomalous_after": replay.is_anomalous if replay else None,
                "per_scope_scores_after": replay.per_scope_scores
                if replay
                else None,
                "scope_weights_after": replay.scope_weights
                if replay
                else None,
                "expert_verdict": None,
                "expert_notes": (
                    "Review: was this a genuine anomaly or thin-history false "
                    "positive? Fill expert_verdict=true/false after manual check."
                ),
            }
        )

    resolved = sum(
        1
        for c in review_cases
        if c["is_anomalous_after"] is False
        and c["is_anomalous_before"] is True
    )
    print(
        f"  Prior predictions in band: {len(band_preds)} — "
        f"would no longer flag after retune: {resolved}/{len(review_cases)}"
    )

    return {
        "score_band": [EXPERT_REVIEW_SCORE_MIN, EXPERT_REVIEW_SCORE_MAX],
        "cases": review_cases,
        "resolved_false_positive_count": resolved,
        "total_in_band": len(review_cases),
    }


async def main_async(args: argparse.Namespace) -> None:
    estate_id = args.estate_id
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = FinetuneReport(
        estate_id=str(estate_id),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        report.phase0_backfill = await run_phase0(
            client,
            estate_id=estate_id,
            skip_backfill=args.skip_backfill,
        )

        report.phase2_grid_search = await run_phase2(
            client, estate_id=estate_id
        )
        best_patch = report.phase2_grid_search.get("recommended_patch") or {}

        report.phase5_threshold = await run_phase5(
            client,
            estate_id=estate_id,
            detector_patch=best_patch,
        )

        # Full visitor replay for phase 6 name matching.
        prior = _apply_settings_patch(best_patch)
        try:
            full_visitor = await _replay_logs(
                client,
                estate_id=estate_id,
                log_source=LogKind.VISITOR,
                anomaly_type=AnomalyType.VISITOR,
                persist=False,
            )
        finally:
            _restore_settings(prior)

        report.phase6_expert_review = await run_phase6(
            client,
            estate_id=estate_id,
            detector_patch=best_patch,
            replay_rows=full_visitor,
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = out_dir / f"finetune_report_{stamp}.json"
    report_path.write_text(
        json.dumps(asdict(report), indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nReport written to {report_path}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Run spatial anomaly finetuning phases."
    )
    p.add_argument(
        "--estate-id",
        type=UUID,
        default=DEFAULT_ESTATE,
        help="Estate UUID to backfill and replay.",
    )
    p.add_argument(
        "--skip-backfill",
        action="store_true",
        help="Skip Phase 0 backfill (replay only).",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=_SVC_ROOT / "reports" / "finetune",
        help="Directory for JSON report output.",
    )
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
