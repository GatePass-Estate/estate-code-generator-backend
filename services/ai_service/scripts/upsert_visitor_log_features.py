#!/usr/bin/env python3
"""
Backfill or refresh ``core.logfeatureengineering`` from visitor/resident logs.

Each run **updates existing rows in place** when a feature-store row already
exists for ``(log_id, anomaly_type)``; it does not delete and re-insert.

Lists log rows from db-service, keeps those in the last ``history_days``
(default 30), engineers **all active scopes** (including ``features_temporal``),
validates keys against :mod:`app.core.feature_config`, and upserts.

Run from ``services/ai_service``::

    # Initial backfill
    python scripts/upsert_visitor_log_features.py visitor visitor \\
        --estate-id <uuid>

    # Refresh stored vectors to the current active schema (no new predictions)
    python scripts/upsert_visitor_log_features.py visitor visitor \\
        --estate-id <uuid> --features-only --reset-anomalous \\
        --include-stored-outside-window

First positional is log source (visitor or resident), second is anomaly type.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

# Resolve ``services/ai_service`` as package root (spatial orchestrator CLI pattern).
_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

# This CLI is usually run on the host, while ``.env.localdocker`` may set
# ``DB_SERVICE_URL`` to a Docker-only hostname. Point at localhost **before**
# ``app.core.config`` is imported so all db-service clients use a resolvable
# base. Set ``DB_SERVICE_URL`` in the environment to override.
if "DB_SERVICE_URL" not in os.environ:
    os.environ["DB_SERVICE_URL"] = "http://localhost:9032/"

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.feature_config import active_feature_set_for_scope  # noqa: E402
from app.domain.anomaly_types import AnomalyType  # noqa: E402
from app.domain.log_kind import LogKind  # noqa: E402
from app.domain.scopes import AnalysisScope  # noqa: E402
from app.integrations.db_service_feature_engineering import (  # noqa: E402
    batch_lookup_engineered_features,
    upsert_focal_engineered_features,
)
from app.integrations.db_service_logs import (  # noqa: E402
    history_window_days,
    load_log_records_for_analysis,
)
from app.models.code_validation import (  # noqa: E402
    CodeValidationPayload,
    Receiver,
)
from app.pipeline.spatial_anomaly_pipeline import (  # noqa: E402
    RECORDS_PRE_SLICED_CONTEXT_KEY,
    pipeline_for_type,
)
from app.pipeline.feature_engineer import build_feature_vector  # noqa: E402
from app.pipeline.scope_manager import resolve_scopes_for_pipeline  # noqa: E402


def _db_url(path: str) -> str:
    base = settings.DB_SERVICE_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    r = await client.get(url)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object from {url!r}")
    return data


def _parse_event_time(rec: dict[str, Any]) -> datetime | None:
    """Parse visit/access/created timestamp to UTC."""
    raw = (
        rec.get("visit_time")
        or rec.get("access_time")
        or rec.get("created_at")
    )
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        v = raw.replace("Z", "+00:00")
        try:
            ts = datetime.fromisoformat(v)
        except ValueError:
            return None
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return None


def _event_time_sort_key(rec: dict[str, Any]) -> tuple[datetime, str]:
    """Ascending sort by event timestamp; tie-break on id string."""
    ts = _parse_event_time(rec)
    if ts is None:
        ts = datetime.min.replace(tzinfo=timezone.utc)
    rid = rec.get("id")
    return (ts, str(rid) if rid is not None else "")


def _filter_rows_in_window(
    rows: list[dict[str, Any]],
    *,
    history_days: int,
    estate_id: UUID | None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Keep rows with a parseable event time in ``[now - history_days, now]``.

    When ``estate_id`` is set, also require a matching ``estate_id`` on the row
    when that field is present.
    """
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(days=history_days)
    estate_s = str(estate_id) if estate_id is not None else None
    kept: list[dict[str, Any]] = []
    for rec in rows:
        if estate_s is not None:
            row_estate = rec.get("estate_id")
            if row_estate is not None and str(row_estate) != estate_s:
                continue
        ts = _parse_event_time(rec)
        if ts is None:
            continue
        if start <= ts <= end:
            kept.append(rec)
    return kept


async def _fetch_all_logs(
    client: httpx.AsyncClient,
    *,
    log_source: LogKind,
    page_size: int,
) -> list[dict[str, Any]]:
    """All pages from list endpoint (items are JSON dicts)."""
    resource = "visitorlog" if log_source == LogKind.VISITOR else "residentlog"
    url = _db_url(f"api/v1/codeservice/{resource}")
    all_items: list[dict[str, Any]] = []
    page = 1
    while True:
        r = await client.get(url, params={"page": page, "limit": page_size})
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise SystemExit(f"Expected JSON object from log list {url!r}")
        items = data.get("items") or []
        total = int(data.get("total") or 0)
        for it in items:
            if isinstance(it, dict):
                all_items.append(it)
        if not items or len(all_items) >= total or len(items) < page_size:
            break
        page += 1
    return all_items


def _as_iso_z(value: object) -> str:
    if isinstance(value, str):
        if value.endswith("+00:00"):
            return value.replace("+00:00", "Z")
        return value
    return str(value)


def _validate_scope_features(
    features_by_scope: dict[str, dict[str, float]],
    scopes: list[AnalysisScope],
) -> None:
    """Ensure engineered keys match the active schema (incl. temporal)."""
    for scope in scopes:
        feats = features_by_scope.get(scope.value)
        if feats is None:
            raise SystemExit(
                f"Missing engineered features for scope {scope.value!r}."
            )
        expected = active_feature_set_for_scope(scope)
        if frozenset(feats.keys()) != expected:
            raise SystemExit(
                f"Schema mismatch for scope {scope.value!r}: "
                f"got {sorted(feats.keys())}, expected {sorted(expected)}."
            )


async def _resolve_estate_id(
    client: httpx.AsyncClient,
    user_id: UUID,
    explicit: UUID | None,
) -> UUID:
    if explicit is not None:
        return explicit
    user_url = _db_url(f"api/v1/userprofile/users/{user_id}")
    user = await _get_json(client, user_url)
    raw = user.get("estate_id")
    if raw is None:
        raise SystemExit(
            "User has no estate_id; pass --estate-id explicitly.",
        )
    return UUID(str(raw))


async def _stored_log_ids_for_estate(
    client: httpx.AsyncClient,
    *,
    rows: list[dict[str, Any]],
    log_source: LogKind,
    anomaly_type: AnomalyType,
    estate_id: UUID | None,
    page_size: int,
) -> set[UUID]:
    """Return log ids that already have a feature-store row for this pipeline."""
    if estate_id is None:
        return set()
    estate_s = str(estate_id)
    candidate_ids: list[UUID] = []
    for rec in rows:
        if str(rec.get("estate_id") or "") != estate_s:
            continue
        rid = rec.get("id")
        if rid is None:
            continue
        try:
            candidate_ids.append(
                rid if isinstance(rid, UUID) else UUID(str(rid))
            )
        except ValueError:
            continue

    stored: set[UUID] = set()
    chunk = max(1, page_size)
    for start in range(0, len(candidate_ids), chunk):
        batch = candidate_ids[start : start + chunk]
        if not batch:
            continue
        items = await batch_lookup_engineered_features(
            client,
            settings,
            log_ids=batch,
            anomaly_type=anomaly_type,
            log_kind=log_source,
        )
        for row in items:
            raw = row.get("visitor_log_id") or row.get("resident_log_id")
            if raw is None:
                continue
            stored.add(raw if isinstance(raw, UUID) else UUID(str(raw)))
    return stored


def _merge_targets_by_id(
    window_rows: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    stored_ids: set[UUID],
    *,
    include_stored_outside_window: bool,
) -> list[dict[str, Any]]:
    """Union window rows with stored rows (optional), deduped by log id."""
    by_id: dict[str, dict[str, Any]] = {
        str(rec["id"]): rec for rec in window_rows if rec.get("id") is not None
    }
    if include_stored_outside_window:
        for rec in all_rows:
            rid = rec.get("id")
            if rid is None:
                continue
            try:
                log_id = rid if isinstance(rid, UUID) else UUID(str(rid))
            except ValueError:
                continue
            if log_id in stored_ids:
                by_id[str(log_id)] = rec
    merged = list(by_id.values())
    merged.sort(key=_event_time_sort_key)
    return merged


async def upsert_one_log(
    client: httpx.AsyncClient,
    *,
    log_source: LogKind,
    anchor_log_id: UUID,
    anomaly_type: AnomalyType,
    is_anomalous: bool | None,
    estate_id_override: UUID | None,
    features_only: bool,
) -> None:
    """
    Engineer and upsert one log row into ``core.logfeatureengineering``.

    Mirrors live ``/analyze`` feature engineering (per-scope slices + active
    schema validation) but skips detector scoring unless ``features_only`` is
    false. Used by 30-day backfill and schema-refresh runs.

    Steps:
    1. Load anchor row + build :class:`CodeValidationPayload`.
    2. Fetch per-scope history via :func:`load_log_records_for_analysis`.
    3. Engineer all pipeline scopes; validate keys against active config.
    4. Upsert JSON columns (and optional prediction stub) to db-service.
    """
    resource = "visitorlog" if log_source == LogKind.VISITOR else "residentlog"
    anchor = await _get_json(
        client,
        _db_url(f"api/v1/codeservice/{resource}/{anchor_log_id}"),
    )
    uid = UUID(str(anchor["user_id"]))
    estate_id = await _resolve_estate_id(client, uid, estate_id_override)

    valid_until_raw = (
        anchor.get("visit_time")
        or anchor.get("access_time")
        or anchor.get("created_at")
        or ""
    )
    receiver = (
        Receiver.VISITOR
        if log_source == LogKind.VISITOR
        else Receiver.RESIDENT
    )
    payload = CodeValidationPayload(
        user_id=uid,
        security_id=UUID(str(anchor["security_id"])),
        estate_id=estate_id,
        hashed_code=str(anchor["hashed_code"]),
        valid_until=_as_iso_z(valid_until_raw),
        is_expired=False,
        receiver=receiver,
        visitor_log_id=(
            anchor_log_id if log_source == LogKind.VISITOR else None
        ),
        resident_log_id=(
            anchor_log_id if log_source == LogKind.RESIDENT else None
        ),
        visitor_fullname=(
            anchor.get("visitor_fullname")
            if log_source == LogKind.VISITOR
            else None
        ),
        relationship_with_resident=(
            str(anchor["relationship_with_resident"])
            if anchor.get("relationship_with_resident") is not None
            else None
        ),
        gender=(
            str(anchor["gender"]) if anchor.get("gender") is not None else None
        ),
    )

    # Step 2 — same per-scope fetch path as live analyze.
    log_slices = await load_log_records_for_analysis(client, settings, payload)
    focal_record = log_slices.focal_record
    pipeline = pipeline_for_type(anomaly_type)
    ctx: dict[str, Any] = {
        **payload.model_dump(mode="json"),
        "trigger_context": {"anomaly_type": anomaly_type.value},
        "focal_record": focal_record,
        "history_window_days": float(history_window_days()),
        RECORDS_PRE_SLICED_CONTEXT_KEY: True,
    }

    # Step 3 — engineer active features only; validate before persist.
    resolved = resolve_scopes_for_pipeline(pipeline)
    focal_features_by_scope: dict[str, dict[str, float]] = {}
    for scope in resolved:
        scope_rows = log_slices.rows_for_analysis_scope(scope)
        feats = await build_feature_vector(pipeline, scope, scope_rows, ctx)
        focal_features_by_scope[scope.value] = feats

    _validate_scope_features(focal_features_by_scope, resolved)

    prediction_result = None
    if not features_only:
        prediction_result = {
            "backfill": True,
            "is_anomalous": bool(is_anomalous),
            "anomaly_type": anomaly_type.value,
        }

    await upsert_focal_engineered_features(
        client,
        settings,
        code_validation=payload,
        anomaly_type=anomaly_type,
        features_by_scope_value=focal_features_by_scope,
        log_kind=log_source,
        is_anomalous=is_anomalous,
        prediction_result=prediction_result,
        features_only=features_only,
    )

    scope_summary = ", ".join(
        f"{name}({len(focal_features_by_scope[name])} keys)"
        for name in focal_features_by_scope
    )
    action = "Refreshed" if features_only else "Upserted"
    anomalous_note = (
        "is_anomalous=unchanged"
        if is_anomalous is None
        else f"is_anomalous={is_anomalous}"
    )
    print(
        f"{action} {resource}_id={anchor_log_id} "
        f"anomaly_type={anomaly_type.value} "
        f"scopes=[{scope_summary}] {anomalous_note}"
    )


async def run(
    *,
    log_source: LogKind,
    anomaly_type: AnomalyType,
    is_anomalous: bool | None,
    estate_id_override: UUID | None,
    history_days: int,
    page_size: int,
    features_only: bool,
    include_stored_outside_window: bool,
) -> None:
    """
    Batch backfill or schema refresh for one estate (optional) and log kind.

    1. List all log rows from db-service (paginated).
    2. Filter to ``history_days`` window (+ stored-outside-window union when flagged).
    3. Sort oldest-first so later rows see richer reference history on replay.
    4. Call :func:`upsert_one_log` for each target (continues on individual failures).
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        rows = await _fetch_all_logs(
            client, log_source=log_source, page_size=page_size
        )
        window_rows = _filter_rows_in_window(
            rows,
            history_days=history_days,
            estate_id=estate_id_override,
        )
        stored_ids: set[UUID] = set()
        if include_stored_outside_window and estate_id_override is not None:
            stored_ids = await _stored_log_ids_for_estate(
                client,
                rows=rows,
                log_source=log_source,
                anomaly_type=anomaly_type,
                estate_id=estate_id_override,
                page_size=page_size,
            )
        targets = _merge_targets_by_id(
            window_rows,
            rows,
            stored_ids,
            include_stored_outside_window=include_stored_outside_window,
        )
        if not targets:
            label = (
                "visitor logs"
                if log_source == LogKind.VISITOR
                else "resident logs"
            )
            print(
                f"No {label} with an event time in the last {history_days} "
                f"day(s). Listed {len(rows)} row(s) total; nothing to upsert."
            )
            return

        # Oldest first so later live analyzes see more matching history.
        targets.sort(key=_event_time_sort_key)
        source_label = (
            "visitor" if log_source == LogKind.VISITOR else "resident"
        )
        extra = max(0, len(targets) - len(window_rows))
        mode = "refreshing features" if features_only else "upserting"
        print(
            f"{mode.capitalize()} {len(targets)} {source_label} log(s)"
            + (
                f" for estate_id={estate_id_override}"
                if estate_id_override
                else ""
            )
            + f" ({len(window_rows)} in last {history_days} day(s)"
            + (f", +{extra} stored outside window" if extra else "")
            + "). Existing rows are updated in place."
        )

        ok = 0
        for rec in targets:
            rid = rec.get("id")
            if rid is None:
                print("Skipping row with no id", rec)
                continue
            try:
                anchor_id = rid if isinstance(rid, UUID) else UUID(str(rid))
            except ValueError:
                print(f"Skipping non-UUID id {rid!r}")
                continue
            try:
                await upsert_one_log(
                    client,
                    log_source=log_source,
                    anchor_log_id=anchor_id,
                    anomaly_type=anomaly_type,
                    is_anomalous=is_anomalous,
                    estate_id_override=estate_id_override,
                    features_only=features_only,
                )
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001 - batch backfill continues
                print(f"Failed log_id={anchor_id}: {exc}")
                continue
            ok += 1

        verb = "Refreshed" if features_only else "Upserted"
        print(f"Done. {verb} {ok}/{len(targets)} log(s).")


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Backfill or refresh logfeatureengineering. Updates existing rows "
            "in place when the log id already has a feature-store entry."
        ),
    )
    p.add_argument(
        "log_source",
        type=str,
        choices=[LogKind.VISITOR.value, LogKind.RESIDENT.value],
        help="Anchor source table to backfill from.",
    )
    p.add_argument(
        "anomaly_type",
        type=str,
        choices=[AnomalyType.VISITOR.value, AnomalyType.RESIDENT.value],
        help="Pipeline flavour (visitor- or resident-centred feature keys).",
    )
    p.add_argument(
        "--is-anomalous",
        action="store_true",
        help="Store is_anomalous=true (default: false on full upsert).",
    )
    p.add_argument(
        "--features-only",
        action="store_true",
        help=(
            "Update feature JSON columns only; do not write prediction "
            "results. Use to align stored vectors with the active schema."
        ),
    )
    p.add_argument(
        "--reset-anomalous",
        action="store_true",
        help=(
            "Set is_anomalous=false on each refreshed row. Implied false "
            "when omitted and --features-only is set unless --is-anomalous."
        ),
    )
    p.add_argument(
        "--include-stored-outside-window",
        action="store_true",
        help=(
            "Also refresh log ids that already have feature-store rows for "
            "this estate, even when outside --history-days. Requires "
            "--estate-id."
        ),
    )
    p.add_argument(
        "--estate-id",
        type=UUID,
        default=None,
        help=(
            "Only backfill logs for this estate; also used as estate_id on "
            "each upsert when set."
        ),
    )
    p.add_argument(
        "--history-days",
        type=int,
        default=history_window_days(),
        metavar="N",
        help=(
            "Include logs whose event time falls within the last N days "
            f"(default: {history_window_days()}, same as spatial analysis)."
        ),
    )
    p.add_argument(
        "--page-size",
        type=int,
        default=100,
        metavar="N",
        help="Page size when listing log rows (default: 100).",
    )
    args = p.parse_args()
    if args.include_stored_outside_window and args.estate_id is None:
        raise SystemExit(
            "--include-stored-outside-window requires --estate-id."
        )

    if args.features_only:
        if args.is_anomalous:
            is_anomalous: bool | None = True
        elif args.reset_anomalous:
            is_anomalous = False
        else:
            is_anomalous = None
    else:
        is_anomalous = True if args.is_anomalous else False

    asyncio.run(
        run(
            log_source=LogKind(args.log_source),
            anomaly_type=AnomalyType(args.anomaly_type),
            is_anomalous=is_anomalous,
            estate_id_override=args.estate_id,
            history_days=max(1, args.history_days),
            page_size=max(1, args.page_size),
            features_only=bool(args.features_only),
            include_stored_outside_window=bool(
                args.include_stored_outside_window
            ),
        )
    )


if __name__ == "__main__":
    main()
