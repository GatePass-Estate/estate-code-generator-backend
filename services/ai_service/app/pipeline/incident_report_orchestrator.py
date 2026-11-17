"""
Incident intelligence orchestrator (CLI / internal date-window analysis).

Public generation lives on
``GET /incident-reports/result-page/summary``. This module remains a
CLI harness over the same date-window cohort.
"""

from __future__ import annotations

# Run CLI from ``services/ai_service``: ``python -m app.pipeline.incident_report_orchestrator``
import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from gatepass_entitlement import resolve_incident_entitlements

from app.core.config import settings
from app.core.exceptions import IncidentReportError
from app.integrations.db_service_incident_reports import (
    load_incident_reports_for_estate,
)
from app.models.incident_resultpage import IncidentLlmSummary
from app.pipeline.incident_eda import build_incident_eda
from app.pipeline.incident_llm_summarizer import summarize_incidents_with_llm
from app.pipeline.incident_resultpage import (
    attach_category_eda,
    build_inhouse_incident_summary,
)


def _coerce_summary_keys(raw: dict[str, Any]) -> dict[str, Any]:
    """Tolerate occasional scalar chat outputs before Pydantic validation."""
    out = dict(raw)
    for key in ("key_patterns", "recommended_actions"):
        v = out.get(key)
        if isinstance(v, str):
            out[key] = [v]
        elif v is None:
            out[key] = []
        elif not isinstance(v, list):
            out[key] = [str(v)]
    return out


def _parse_cli_datetime(raw: str | None) -> datetime | None:
    """Parse an optional ISO-8601 CLI datetime."""
    if raw is None or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class IncidentReportOrchestrator:
    """Load one estate date window and run entitled topic / LLM summaries."""

    async def analyze(
        self,
        *,
        client: httpx.AsyncClient,
        estate_id: UUID,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        n_topics: int | None = None,
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Analyse every incident in the selected date window.

        Tier 1 runs TF-IDF/NMF topic modelling. Tier 2 adds the LLM
        narrative. Neither tier is row-capped.
        """
        records = await load_incident_reports_for_estate(
            client,
            settings,
            estate_id=estate_id,
            from_date=from_date,
            to_date=to_date,
        )
        if not records:
            raise IncidentReportError(
                "No incident reports matched the filters.",
                status_code=422,
            )

        _page_ok, inhouse_ok, llm_ok = await resolve_incident_entitlements(
            settings.REVENUE_SERVICE_URL,
            estate_id=estate_id,
            client=client,
            auth_token=auth_token,
        )

        topics_section: dict[str, Any] = {}
        inhouse = None
        if inhouse_ok:
            inhouse = build_inhouse_incident_summary(
                records, n_topics=n_topics
            )
            topics_section = inhouse.topics or {}

        summary_section: dict[str, Any] = {}
        if llm_ok:
            eda = build_incident_eda(records)
            raw_summary, model, llm_used = await summarize_incidents_with_llm(
                client=client,
                settings=settings,
                records=records,
                eda=eda,
            )
            llm = IncidentLlmSummary.model_validate(
                _coerce_summary_keys(raw_summary)
            )
            if inhouse is not None:
                llm = attach_category_eda(llm, inhouse.category_eda)
            summary_section = {
                "eda": eda,
                "structured_summary": llm.model_dump(exclude={"category_eda"}),
                "llm_model": model,
                "llm_used": llm_used,
            }

        return {
            "estate_id": str(estate_id),
            "record_count": len(records),
            "estate_payment_active": llm_ok,
            "entitled_tier": (
                "tier2" if llm_ok else "tier1" if inhouse_ok else None
            ),
            "summary": summary_section,
            "topics": topics_section,
        }


def _json_output_path(estate_id: UUID, output: Path | None) -> Path:
    if output is not None:
        return output
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"incident_analyze_{estate_id}_{stamp}.json")


def _write_analyze_json(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=2, default=str)
    path.write_text(text + "\n", encoding="utf-8")


async def _run(
    *,
    estate_id: UUID,
    from_date: datetime | None,
    to_date: datetime | None,
    n_topics: int | None,
    as_json: bool,
    json_output: Path | None = None,
) -> None:
    """CLI harness: run analyze and print human output or write JSON."""
    orch = IncidentReportOrchestrator()
    async with httpx.AsyncClient(timeout=120.0) as client:
        started = time.perf_counter()
        result = await orch.analyze(
            client=client,
            estate_id=estate_id,
            from_date=from_date,
            to_date=to_date,
            n_topics=n_topics,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        paid = result.get("estate_payment_active")
        count = result.get("record_count", 0)
        print("\n[__main__] incident analyze")
        print(
            f"records={count} estate_payment_active={paid} latency_ms={latency_ms}"
        )
        if as_json:
            out_path = _json_output_path(estate_id, json_output)
            payload = {**result, "latency_ms": latency_ms}
            _write_analyze_json(payload, out_path)
            print(f"\n[__main__] saved analyze JSON → {out_path.resolve()}")
            return
        topics = result.get("topics") or {}
        print("\n" + (topics.get("report_text") or "(no topic report)"))
        if not paid:
            print("\n── Summary skipped (tier 2 not entitled)")
            return
        structured = (result.get("summary") or {}).get(
            "structured_summary"
        ) or {}
        exec_sum = structured.get("executive_summary")
        if exec_sum:
            print("\n── Summary\n" + exec_sum)
        else:
            print("\n── Summary (empty)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run incident analyze for a date window "
            "(topics when tier 1; LLM when tier 2)."
        ),
    )
    parser.add_argument(
        "--estate-id",
        type=UUID,
        default=UUID("6eb0c18d-5505-4601-a211-1584b6a5bc31"),
        help="Estate UUID (replace with your test estate).",
    )
    parser.add_argument(
        "--from-date",
        default=None,
        metavar="ISO",
        help="Inclusive lower bound on incident created_at.",
    )
    parser.add_argument(
        "--to-date",
        default=None,
        metavar="ISO",
        help="Inclusive upper bound on incident created_at.",
    )
    parser.add_argument(
        "--n-topics",
        type=int,
        default=None,
        metavar="K",
        help="NMF topic count (default: auto).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Write full analyze JSON to a file (default: "
            "incident_analyze_<estate_id>_<timestamp>.json)."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        metavar="PATH",
        help="JSON output path (only with --json; default: auto-named file).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.output is not None and not args.json:
        raise SystemExit("--output requires --json")
    asyncio.run(
        _run(
            estate_id=args.estate_id,
            from_date=_parse_cli_datetime(args.from_date),
            to_date=_parse_cli_datetime(args.to_date),
            n_topics=args.n_topics,
            as_json=bool(args.json),
            json_output=args.output,
        )
    )


if __name__ == "__main__":
    main()
