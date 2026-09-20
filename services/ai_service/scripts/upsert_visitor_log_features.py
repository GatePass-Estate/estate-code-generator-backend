#!/usr/bin/env python3
"""
Backfill ``core.logfeatureengineering`` from visitor or resident log rows.

Lists log rows from db-service, keeps those whose event time falls within the
last ``history_days`` (default 30, matching the spatial analysis window),
engineers **all active scopes** (including ``temporal`` → ``features_temporal``),
and upserts each row.

Run from ``services/ai_service``::

    python scripts/upsert_visitor_log_features.py visitor visitor \\
        [--is-anomalous] [--estate-id <uuid>] [--history-days 30] [--page-size 100]

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


async def upsert_one_log(
    client: httpx.AsyncClient,
    *,
    log_source: LogKind,
    anchor_log_id: UUID,
    anomaly_type: AnomalyType,
    is_anomalous: bool,
    estate_id_override: UUID | None,
) -> None:
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

    resolved = resolve_scopes_for_pipeline(pipeline)
    focal_features_by_scope: dict[str, dict[str, float]] = {}
    for scope in resolved:
        scope_rows = log_slices.rows_for_analysis_scope(scope)
        feats = await build_feature_vector(pipeline, scope, scope_rows, ctx)
        focal_features_by_scope[scope.value] = feats

    _validate_scope_features(focal_features_by_scope, resolved)

    await upsert_focal_engineered_features(
        client,
        settings,
        code_validation=payload,
        anomaly_type=anomaly_type,
        features_by_scope_value=focal_features_by_scope,
        log_kind=log_source,
        is_anomalous=is_anomalous,
        prediction_result={
            "backfill": True,
            "is_anomalous": is_anomalous,
            "anomaly_type": anomaly_type.value,
        },
    )

    scope_summary = ", ".join(
        f"{name}({len(focal_features_by_scope[name])} keys)"
        for name in focal_features_by_scope
    )
    print(
        f"Upserted {resource}_id={anchor_log_id} "
        f"anomaly_type={anomaly_type.value} "
        f"scopes=[{scope_summary}] is_anomalous={is_anomalous}"
    )


async def run(
    *,
    log_source: LogKind,
    anomaly_type: AnomalyType,
    is_anomalous: bool,
    estate_id_override: UUID | None,
    history_days: int,
    page_size: int,
) -> None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        rows = await _fetch_all_logs(
            client, log_source=log_source, page_size=page_size
        )
        targets = _filter_rows_in_window(
            rows,
            history_days=history_days,
            estate_id=estate_id_override,
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
        print(
            f"Upserting {len(targets)} {source_label} log(s) from the last "
            f"{history_days} day(s)"
            + (
                f" for estate_id={estate_id_override}"
                if estate_id_override
                else ""
            )
            + "."
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
                )
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001 - batch backfill continues
                print(f"Failed log_id={anchor_id}: {exc}")
                continue
            ok += 1

        print(f"Done. Upserted {ok}/{len(targets)} log(s).")


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Backfill logfeatureengineering for logs in the last N days "
            "(default: spatial history window)."
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
        help="Store is_anomalous=true (default: false).",
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
    asyncio.run(
        run(
            log_source=LogKind(args.log_source),
            anomaly_type=AnomalyType(args.anomaly_type),
            is_anomalous=bool(args.is_anomalous),
            estate_id_override=args.estate_id,
            history_days=max(1, args.history_days),
            page_size=max(1, args.page_size),
        )
    )


if __name__ == "__main__":
    main()
