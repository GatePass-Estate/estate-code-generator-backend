"""Orchestrate incident fetch → topic modelling → payment-gated LLM summary."""

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

from app.core.config import settings
from app.core.exceptions import IncidentReportError
from app.integrations.db_service_estate import fetch_estate_payment_active
from app.integrations.db_service_incident_reports import (
    load_incident_reports_for_estate,
)
from app.models.incident_schemas import (
    IncidentStructuredSummary,
    IncidentSummarySection,
)
from app.pipeline.incident_eda import build_incident_eda
from app.pipeline.incident_llm_summarizer import summarize_incidents_with_llm
from app.pipeline.incident_topic_modelling import discover_incident_topics


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


class IncidentReportOrchestrator:
    """
    Incident intelligence orchestration for ``POST /incident-reports/summarize``.

    Always runs TF-IDF + NMF topic modelling and a human-readable theme report.
    When ``fetch_estate_payment_active`` is true, also runs cohort EDA and an
    OpenAI/heuristic structured summary; otherwise returns an empty ``summary``.
    """

    async def analyze(
        self,
        *,
        client: httpx.AsyncClient,
        estate_id: UUID,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        max_records: int = 500,
        n_topics: int | None = None,
    ) -> dict[str, Any]:
        """
        Fetch incidents once; always run topic modelling.

        When estate payment is active, also run EDA + LLM/heuristic summary.
        Otherwise return an empty ``summary`` section.
        """
        records = await load_incident_reports_for_estate(
            client,
            settings,
            estate_id=estate_id,
            from_date=from_date,
            to_date=to_date,
            max_records=max_records,
        )
        if not records:
            raise IncidentReportError(
                "No incident reports matched the filters.",
                status_code=422,
            )

        payment_active = await fetch_estate_payment_active(
            client, settings, estate_id
        )

        modelled = discover_incident_topics(records, n_topics=n_topics)
        topics_section = {
            "method": modelled.get("method", "tfidf_nmf"),
            "documents_modelled": int(modelled.get("documents_modelled") or 0),
            "n_topics": int(modelled.get("n_topics") or 0),
            "note": modelled.get("note"),
            "topics": modelled.get("topics") or [],
            "assignments": modelled.get("assignments") or [],
            "temporal_overview": modelled.get("temporal_overview") or {},
            "human_report": modelled.get("human_report"),
            "report_text": modelled.get("report_text"),
        }

        if payment_active:
            eda = build_incident_eda(records)
            raw_summary, model, llm_used = await summarize_incidents_with_llm(
                client=client,
                settings=settings,
                records=records,
                eda=eda,
            )
            structured = IncidentStructuredSummary.model_validate(
                _coerce_summary_keys(raw_summary)
            )
            summary_section = IncidentSummarySection(
                eda=eda,
                structured_summary=structured,
                llm_model=model,
                llm_used=llm_used,
            )
        else:
            summary_section = IncidentSummarySection()

        return {
            "estate_id": str(estate_id),
            "record_count": len(records),
            "estate_payment_active": payment_active,
            "summary": summary_section.model_dump(),
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
    max_records: int,
    n_topics: int | None,
    as_json: bool,
    json_output: Path | None = None,
) -> None:
    """Local e2e for merged analyze (topics + payment-gated summary)."""
    orch = IncidentReportOrchestrator()
    async with httpx.AsyncClient(timeout=120.0) as client:
        started = time.perf_counter()
        result = await orch.analyze(
            client=client,
            estate_id=estate_id,
            from_date=None,
            to_date=None,
            max_records=max_records,
            n_topics=n_topics,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        paid = result.get("estate_payment_active")
        count = result.get("record_count", 0)
        print("\n[__main__] incident analyze")
        print(
            f"records={count} estate_payment_active={paid} "
            f"latency_ms={latency_ms}"
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
            print("\n── Summary skipped (estate payment inactive)")
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
            "Run incident analyze (TF-IDF+NMF topics; LLM summary when paid)."
        ),
    )
    parser.add_argument(
        "--estate-id",
        type=UUID,
        default=UUID("6eb0c18d-5505-4601-a211-1584b6a5bc31"),
        help="Estate UUID (replace with your test estate).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=500,
        metavar="N",
        help="Max incident rows to load (default: 500).",
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
            max_records=max(1, args.max_records),
            n_topics=args.n_topics,
            as_json=bool(args.json),
            json_output=args.output,
        )
    )


if __name__ == "__main__":
    main()
