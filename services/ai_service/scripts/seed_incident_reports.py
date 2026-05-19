#!/usr/bin/env python3
"""
Insert sample rows into ``core.incidentreport`` via db-service for testing.

Run from ``services/ai_service``::

    python scripts/seed_incident_reports.py \\
        [--estate-id <uuid>] [--user-id <uuid>] [--dry-run]

Resolves ``estate_id`` from the first estate in db-service when omitted.
``reported_by_user_id`` is optional; when omitted the script tries the first
user on that estate.
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

_SVC_ROOT = Path(__file__).resolve().parents[1]
if str(_SVC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SVC_ROOT))

if "DB_SERVICE_URL" not in os.environ:
    os.environ["DB_SERVICE_URL"] = "http://localhost:9032/"

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.domain.incident_category import IncidentCategory  # noqa: E402

_CREATE_PATH = "api/v1/codeservice/incidentreport"


def _db_url(path: str) -> str:
    base = settings.DB_SERVICE_URL.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object from {url!r}")
    return data


async def _post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object from POST {url!r}")
    return data


async def _resolve_estate_id(
    client: httpx.AsyncClient,
    explicit: UUID | None,
) -> UUID:
    if explicit is not None:
        return explicit
    data = await _get_json(
        client,
        _db_url("api/v1/userprofile/estates"),
        params={"page": 1, "limit": 1},
    )
    items = data.get("items") or []
    if not items:
        raise SystemExit(
            "No estates found; pass --estate-id explicitly.",
        )
    raw = items[0].get("id")
    if raw is None:
        raise SystemExit("First estate row has no id.")
    return UUID(str(raw))


async def _resolve_reported_by_user_id(
    client: httpx.AsyncClient,
    *,
    estate_id: UUID,
    explicit: UUID | None,
) -> UUID | None:
    if explicit is not None:
        return explicit
    data = await _get_json(
        client,
        _db_url("api/v1/userprofile/users"),
        params={"page": 1, "limit": 50},
    )
    for row in data.get("items") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("estate_id")) == str(estate_id) and row.get("id"):
            return UUID(str(row["id"]))
    return None


def _occurred_at(days_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat().replace("+00:00", "Z")


def _sample_payloads(
    estate_id: UUID,
    reported_by_user_id: UUID | None,
) -> list[dict[str, Any]]:
    """Curated mix of enum categories, titles, and custom labels."""
    base = {
        "estate_id": str(estate_id),
        "reported_by_user_id": (
            str(reported_by_user_id) if reported_by_user_id else None
        ),
    }

    templates: list[dict[str, Any]] = [
        {
            "title": "Repeated gate alarm after hours",
            "category": [
                IncidentCategory.SECURITY,
                IncidentCategory.ACCESS_CONTROL,
            ],
            "custom_category": None,
            "narrative": (
                "Main entrance sensor triggered three times between 01:00 "
                "and 02:30. Guard confirmed no unauthorized vehicles."
            ),
            "days_ago": 1.5,
        },
        {
            "title": "Loud music from unit block B",
            "category": [IncidentCategory.NOISE_DISTURBANCE],
            "custom_category": None,
            "narrative": (
                "Residents reported amplified music past quiet hours. "
                "Security asked occupants to lower volume."
            ),
            "days_ago": 3.0,
        },
        {
            "title": "Broken perimeter lighting",
            "category": [
                IncidentCategory.MAINTENANCE,
                IncidentCategory.SECURITY,
            ],
            "custom_category": None,
            "narrative": (
                "Three lamps along the east fence are out. Area is poorly lit "
                "at night; facilities ticket opened."
            ),
            "days_ago": 5.0,
        },
        {
            "title": None,
            "category": [IncidentCategory.THEFT],
            "custom_category": None,
            "narrative": (
                "Bicycle removed from rack near clubhouse despite lock. "
                "CCTV clip saved for review."
            ),
            "days_ago": 7.0,
        },
        {
            "title": "Pool chemical odor",
            "category": [],
            "custom_category": "Pool chemical handling concern",
            "narrative": (
                "Strong chlorine smell near pool plant room; no injuries "
                "reported. Awaiting vendor inspection."
            ),
            "days_ago": 9.0,
        },
        {
            "title": "Visitor tailgating at barrier",
            "category": [IncidentCategory.UNAUTHORIZED_ACCESS],
            "custom_category": None,
            "narrative": (
                "Unknown vehicle followed a resident through the barrier "
                "without scanning a code."
            ),
            "days_ago": 11.0,
        },
        {
            "title": "Elevator stuck between floors",
            "category": [IncidentCategory.MAINTENANCE],
            "custom_category": None,
            "narrative": (
                "Lift C stopped between levels 4 and 5 with two passengers. "
                "Vendor released car within 25 minutes."
            ),
            "days_ago": 14.0,
        },
        {
            "title": "Verbal dispute at reception",
            "category": [
                IncidentCategory.DISPUTE,
                IncidentCategory.HARASSMENT,
            ],
            "custom_category": None,
            "narrative": (
                "Two residents argued at front desk over parcel delivery. "
                "No physical contact; both parties separated."
            ),
            "days_ago": 18.0,
        },
        {
            "title": "Smell of smoke in parking level P2",
            "category": [IncidentCategory.FIRE_SAFETY],
            "custom_category": None,
            "narrative": (
                "Light smoke smell traced to overheated vehicle alternator. "
                "Fire panel normal; area ventilated."
            ),
            "days_ago": 21.0,
        },
        {
            "title": "Resident slip on wet walkway",
            "category": [IncidentCategory.MEDICAL_EMERGENCY],
            "custom_category": None,
            "narrative": (
                "Adult slipped after irrigation overspray. Minor bruising; "
                "declined ambulance transport."
            ),
            "days_ago": 25.0,
        },
        {
            "title": "Graffiti on amenity wall",
            "category": [
                IncidentCategory.PROPERTY_DAMAGE,
                IncidentCategory.OTHER,
            ],
            "custom_category": "Tagging near playground",
            "narrative": (
                "Fresh paint tags on south amenity wall. Photos taken for "
                "estate management follow-up."
            ),
            "days_ago": 30.0,
        },
        {
            "title": "Unknown drone over estate",
            "category": [],
            "custom_category": "Drone surveillance over private gardens",
            "narrative": (
                "Residents reported a drone hovering for ~10 minutes. "
                "Direction of flight unknown."
            ),
            "days_ago": 35.0,
        },
    ]

    payloads: list[dict[str, Any]] = []
    for tpl in templates:
        body = {
            **base,
            "title": tpl["title"],
            "category": [c.value for c in tpl["category"]],
            "custom_category": tpl["custom_category"],
            "narrative": tpl["narrative"],
            "occurred_at": _occurred_at(float(tpl["days_ago"])),
        }
        if body["reported_by_user_id"] is None:
            body.pop("reported_by_user_id", None)
        payloads.append(body)
    return payloads


async def run(
    *,
    estate_id: UUID | None,
    user_id: UUID | None,
    dry_run: bool,
) -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resolved_estate = await _resolve_estate_id(client, estate_id)
        resolved_user = await _resolve_reported_by_user_id(
            client,
            estate_id=resolved_estate,
            explicit=user_id,
        )
        samples = _sample_payloads(resolved_estate, resolved_user)

        print(f"DB_SERVICE_URL={settings.DB_SERVICE_URL}")
        print(f"estate_id={resolved_estate}")
        print(f"reported_by_user_id={resolved_user or '(none)'}")
        print(f"Prepared {len(samples)} sample incident report(s).")

        if dry_run:
            for i, body in enumerate(samples, start=1):
                print(f"\n--- sample {i} (dry-run) ---")
                print(body)
            return

        url = _db_url(_CREATE_PATH)
        created = 0
        for i, body in enumerate(samples, start=1):
            result = await _post_json(client, url, body)
            created += 1
            print(
                f"[{i}/{len(samples)}] created id={result.get('id')} "
                f"title={body.get('title')!r} "
                f"categories={body.get('category')}"
            )
        print(f"\nDone. Inserted {created} incident report(s).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="POST sample incident reports to db-service for testing.",
    )
    parser.add_argument(
        "--estate-id",
        type=UUID,
        default=None,
        help="Estate UUID (default: first estate from db-service).",
    )
    parser.add_argument(
        "--user-id",
        type=UUID,
        default=None,
        help="reported_by_user_id (default: first user on the estate).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without calling db-service.",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            estate_id=args.estate_id,
            user_id=args.user_id,
            dry_run=bool(args.dry_run),
        )
    )


if __name__ == "__main__":
    main()
