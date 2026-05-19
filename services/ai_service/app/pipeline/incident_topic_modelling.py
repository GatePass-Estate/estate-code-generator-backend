"""
Latent theme discovery for incident cohorts via TF-IDF and NMF.

Builds a document-term matrix from incident text, factorises it into
document-topic and topic-term matrices, and assigns each report to a
dominant topic. See ``INCIDENT_REPORTS.md`` for the mathematical specification.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

from app.pipeline.incident_corpus import build_incident_document_text
from app.pipeline.incident_topic_human_report import (
    build_human_topic_report,
    enrich_topics_for_display,
)

_NON_WORD = re.compile(r"[^a-z0-9\s]+")
_MIN_RECORDS = 3
_DEFAULT_TOP_TERMS = 8


def _parse_occurred_at(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        text = raw.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _clean_document(text: str) -> str:
    """Lowercase and strip punctuation so tokens are alphanumeric words."""
    lowered = text.lower().strip()
    if not lowered:
        return ""
    return _NON_WORD.sub(" ", lowered)


def _resolve_n_topics(n_docs: int, requested: int | None) -> int:
    """Choose NMF rank ``K`` from API override or cohort-size heuristic."""
    if requested is not None:
        return max(2, min(requested, n_docs - 1, 12))
    # Heuristic: one topic per ~8 reports, between 2 and 8.
    auto = max(2, min(8, max(2, n_docs // 8)))
    return min(auto, n_docs - 1)


def _auto_label(top_terms: list[str]) -> str:
    return " / ".join(top_terms[:4]) if top_terms else "unlabeled"


def _hour_bucket(hour: int) -> str:
    if hour >= 22 or hour < 6:
        return "night"
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    return "evening"


def discover_incident_topics(
    records: list[dict[str, Any]],
    *,
    n_topics: int | None = None,
    max_features: int = 4000,
    top_terms_per_topic: int = _DEFAULT_TOP_TERMS,
) -> dict[str, Any]:
    """
    Discover recurring themes with TF-IDF vectorisation and NMF factorisation.

    Steps: build documents → clean → ``TfidfVectorizer`` → ``NMF.fit_transform`` →
    top terms per topic, argmax document assignments, temporal aggregates, human report.

    Args:
        records: Incident dicts from db-service (title, category, narrative, …).
        n_topics: Optional NMF rank ``K``; auto-selected from cohort size when ``None``.
        max_features: Vocabulary cap for TF-IDF.
        top_terms_per_topic: How many weighted terms to expose per theme.

    Returns:
        Dict with ``method``, ``topics``, ``assignments``, ``temporal_overview``,
        ``human_report``, and ``report_text``. On insufficient data, ``n_topics`` is 0
        and ``note`` explains why.
    """
    n = len(records)
    if n < _MIN_RECORDS:
        note = (
            f"Need at least {_MIN_RECORDS} incident rows for topic modelling; "
            f"got {n}."
        )
        return {
            "method": "tfidf_nmf",
            "record_count": n,
            "n_topics": 0,
            "note": note,
            "topics": [],
            "assignments": [],
            "temporal_overview": {},
            "human_report": build_human_topic_report(
                records=records,
                topics=[],
                assignments=[],
                temporal_overview={},
                record_count=n,
                documents_modelled=0,
                n_topics=0,
                note=note,
            ),
        }

    doc_ids: list[str] = []
    raw_texts: list[str] = []
    for row in records:
        rid = row.get("id")
        doc_ids.append(str(rid) if rid is not None else "")
        raw_texts.append(build_incident_document_text(row))

    cleaned = [_clean_document(t) for t in raw_texts]
    non_empty_idx = [i for i, t in enumerate(cleaned) if t.strip()]
    if len(non_empty_idx) < _MIN_RECORDS:
        return {
            "method": "tfidf_nmf",
            "record_count": n,
            "n_topics": 0,
            "note": "Too few non-empty incident texts after cleaning.",
            "topics": [],
            "assignments": [],
            "temporal_overview": {},
        }

    cleaned = [cleaned[i] for i in non_empty_idx]
    doc_ids = [doc_ids[i] for i in non_empty_idx]
    records_used = [records[i] for i in non_empty_idx]
    n_used = len(cleaned)

    k = _resolve_n_topics(n_used, n_topics)
    min_df = 1 if n_used < 10 else 2

    vectorizer = TfidfVectorizer(
        max_features=max_features,
        min_df=min_df,
        max_df=0.95,
        stop_words="english",
        ngram_range=(1, 2),
    )
    tfidf = vectorizer.fit_transform(cleaned)
    if tfidf.shape[1] == 0:
        return {
            "method": "tfidf_nmf",
            "record_count": n,
            "n_topics": 0,
            "note": "Vocabulary empty after TF-IDF; try more diverse reports.",
            "topics": [],
            "assignments": [],
            "temporal_overview": {},
        }

    nmf = NMF(
        n_components=k,
        random_state=42,
        max_iter=300,
        init="nndsvda",
    )
    doc_topic = nmf.fit_transform(tfidf)
    feature_names = vectorizer.get_feature_names_out()

    topics_out: list[dict[str, Any]] = []
    topic_doc_indices: dict[int, list[int]] = defaultdict(list)

    for topic_idx in range(k):
        weights = nmf.components_[topic_idx]
        rank = np.argsort(weights)[::-1][:top_terms_per_topic]
        term_weights = [
            {
                "term": str(feature_names[i]),
                "weight": round(float(weights[i]), 4),
            }
            for i in rank
            if weights[i] > 0
        ]
        top_terms = [tw["term"] for tw in term_weights]
        topics_out.append(
            {
                "topic_id": topic_idx,
                "label": _auto_label(top_terms),
                "top_terms": term_weights,
                "document_count": 0,
                "sample_incident_ids": [],
            }
        )

    assignments: list[dict[str, Any]] = []
    for doc_i in range(n_used):
        dist = doc_topic[doc_i]
        dominant = int(np.argmax(dist))
        weight = float(dist[dominant])
        topic_doc_indices[dominant].append(doc_i)
        iid = doc_ids[doc_i]
        assignments.append(
            {
                "incident_id": iid or None,
                "topic_id": dominant,
                "weight": round(weight, 4),
            }
        )

    for topic in topics_out:
        tid = int(topic["topic_id"])
        indices = topic_doc_indices.get(tid, [])
        topic["document_count"] = len(indices)
        sample_ids = [doc_ids[i] for i in indices[:5] if doc_ids[i]]
        topic["sample_incident_ids"] = sample_ids

    temporal = _build_temporal_overview(records_used, assignments)
    topics_display = enrich_topics_for_display(
        records_used,
        topics_out,
        assignments,
        n_docs=n_used,
    )
    human_report = build_human_topic_report(
        records=records_used,
        topics=topics_out,
        assignments=assignments,
        temporal_overview=temporal,
        record_count=n,
        documents_modelled=n_used,
        n_topics=k,
    )

    return {
        "method": "tfidf_nmf",
        "record_count": n,
        "documents_modelled": n_used,
        "n_topics": k,
        "topics": topics_display,
        "assignments": assignments,
        "temporal_overview": temporal,
        "human_report": human_report,
        "report_text": human_report["full_text"],
    }


def _build_temporal_overview(
    records: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Topic counts by ISO week and coarse day/night buckets."""
    by_topic_week: Counter[tuple[int, str]] = Counter()
    weekend = Counter()
    hour_buckets = Counter()

    for row, assign in zip(records, assignments, strict=True):
        ts = _parse_occurred_at(
            row.get("occurred_at") or row.get("created_at")
        )
        topic_id = assign.get("topic_id")
        if ts is None or topic_id is None:
            continue
        week_key = ts.strftime("%Y-W%W")
        by_topic_week[(int(topic_id), week_key)] += 1
        weekend["weekend" if ts.weekday() >= 5 else "weekday"] += 1
        hour_buckets[_hour_bucket(ts.hour)] += 1

    week_rows: list[dict[str, Any]] = [
        {
            "topic_id": tid,
            "week": week,
            "count": count,
        }
        for (tid, week), count in sorted(by_topic_week.items())
    ]

    return {
        "by_topic_week": week_rows,
        "weekend_vs_weekday": dict(weekend),
        "hour_bucket": dict(hour_buckets),
    }
