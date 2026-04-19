#!/usr/bin/env python3
"""
Backfill ``core.logfeatureengineering`` from visitor log rows.

1. Lists all non-deleted rows from ``GET .../codeservice/visitorlog`` (paginated).
2. Sorts by ``visit_time`` descending; drops the single most recent visit.
3. For each remaining id, loads history, engineers features, and upserts (same
   paths as the live orchestrator).

Run from ``services/anomaly_service``::

    python scripts/upsert_visitor_log_features.py visitor \\
        [--is-anomalous] [--estate-id <uuid>] [--page-size 100]

Requires ``DB_SERVICE_URL`` (see ``app.core.config``). Without ``--estate-id``,
``estate_id`` per row is taken from ``GET .../userprofile/users/{user_id}``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

# Resolve ``services/anomaly_service`` as package root (orchestrator pattern).
_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.domain.anomaly_types import AnomalyType  # noqa: E402
from app.domain.log_kind import LogKind  # noqa: E402
from app.integrations.db_service_feature_engineering import (  # noqa: E402
    upsert_focal_engineered_features,
)
from app.integrations.db_service_logs import (  # noqa: E402
    history_window_days,
    load_log_records_for_analysis,
)
from app.models.schemas import CodeValidationPayload, Receiver  # noqa: E402
from app.pipeline.anomaly_pipeline import (  # noqa: E402
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


def _visit_time_sort_key(rec: dict[str, Any]) -> tuple[datetime, str]:
    """Descending sort: latest visit first; tie-break on id string."""
    raw = rec.get("visit_time")
    ts: datetime
    if isinstance(raw, datetime):
        ts = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    elif isinstance(raw, str):
        v = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(v)
        except ValueError:
            parsed = datetime.min.replace(tzinfo=timezone.utc)
        ts = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    else:
        ts = datetime.min.replace(tzinfo=timezone.utc)
    rid = rec.get("id")
    return (ts, str(rid) if rid is not None else "")


async def _fetch_all_visitor_logs(
    client: httpx.AsyncClient,
    *,
    page_size: int,
) -> list[dict[str, Any]]:
    """All pages from list endpoint (items are JSON dicts)."""
    url = _db_url("api/v1/codeservice/visitorlog")
    all_items: list[dict[str, Any]] = []
    page = 1
    while True:
        r = await client.get(url, params={"page": page, "limit": page_size})
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise SystemExit(
                f"Expected JSON object from visitor log list {url!r}"
            )
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


async def upsert_one_visitor_log(
    client: httpx.AsyncClient,
    *,
    visitor_log_id: UUID,
    anomaly_type: AnomalyType,
    is_anomalous: bool,
    estate_id_override: UUID | None,
) -> None:
    anchor = await _get_json(
        client,
        _db_url(f"api/v1/codeservice/visitorlog/{visitor_log_id}"),
    )
    uid = UUID(str(anchor["user_id"]))
    estate_id = await _resolve_estate_id(client, uid, estate_id_override)

    payload = CodeValidationPayload(
        user_id=uid,
        security_id=UUID(str(anchor["security_id"])),
        estate_id=estate_id,
        hashed_code=str(anchor["hashed_code"]),
        valid_until=_as_iso_z(anchor["visit_time"]),
        is_expired=False,
        receiver=Receiver.VISITOR,
        visitor_log_id=visitor_log_id,
        visitor_fullname=anchor.get("visitor_fullname"),
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

    focal_features_by_scope: dict[str, dict[str, float]] = {}
    for scope in resolve_scopes_for_pipeline(pipeline):
        scope_rows = log_slices.rows_for_analysis_scope(scope)
        feats = await build_feature_vector(pipeline, scope, scope_rows, ctx)
        focal_features_by_scope[scope.value] = feats

    await upsert_focal_engineered_features(
        client,
        settings,
        code_validation=payload,
        anomaly_type=anomaly_type,
        features_by_scope_value=focal_features_by_scope,
        log_kind=LogKind.VISITOR,
        is_anomalous=is_anomalous,
    )

    keys = list(focal_features_by_scope.keys())
    print(
        f"Upserted visitor_log_id={visitor_log_id} "
        f"anomaly_type={anomaly_type.value} scopes={keys} "
        f"is_anomalous={is_anomalous}"
    )


async def run(
    *,
    anomaly_type: AnomalyType,
    is_anomalous: bool,
    estate_id_override: UUID | None,
    page_size: int,
) -> None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        rows = await _fetch_all_visitor_logs(client, page_size=page_size)
        if len(rows) < 2:
            print(
                f"Need at least 2 visitor logs (after list); got {len(rows)}. "
                "Nothing to upsert."
            )
            return

        ordered = sorted(rows, key=_visit_time_sort_key, reverse=True)
        skipped = ordered[0]
        targets = ordered[1:]
        print(
            "Skipping most recent visit_time: "
            f"id={skipped.get('id')!r} visit_time={skipped.get('visit_time')!r}"
        )
        print(f"Upserting {len(targets)} visitor log(s).")

        for rec in targets:
            rid = rec.get("id")
            if rid is None:
                print("Skipping row with no id", rec)
                continue
            try:
                vid = rid if isinstance(rid, UUID) else UUID(str(rid))
            except ValueError:
                print(f"Skipping non-UUID id {rid!r}")
                continue
            await upsert_one_visitor_log(
                client,
                visitor_log_id=vid,
                anomaly_type=anomaly_type,
                is_anomalous=is_anomalous,
                estate_id_override=estate_id_override,
            )


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "List visitor logs, drop the latest by visit_time, upsert features "
            "for the rest into logfeatureengineering."
        ),
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
        help="Override estate UUID for every row; default: from user profile.",
    )
    p.add_argument(
        "--page-size",
        type=int,
        default=100,
        metavar="N",
        help="Page size when listing visitor logs (default: 100).",
    )
    args = p.parse_args()
    asyncio.run(
        run(
            anomaly_type=AnomalyType(args.anomaly_type),
            is_anomalous=bool(args.is_anomalous),
            estate_id_override=args.estate_id,
            page_size=max(1, args.page_size),
        )
    )


if __name__ == "__main__":
    main()
