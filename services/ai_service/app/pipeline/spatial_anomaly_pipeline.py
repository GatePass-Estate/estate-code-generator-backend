"""
ABC for visitor- vs resident-centred spatial (feature-space) anomaly pipelines.

Feature engineering uses the **focal** log row (anchor from the request) plus a
time-sorted cohort in the search window. Only keys for the active scope are
computed per ``engineer_scope_features`` call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.core.scope_config import scopes_for_anomaly_type
from app.domain import features as feat
from app.domain.anomaly_types import AnomalyType
from app.domain.scopes import AnalysisScope

# When True, ``engineer_scope_features`` treats ``raw_records`` as the final
# per-scope slice (orchestrator supplies rows from ``LogHistorySlices``).
RECORDS_PRE_SLICED_CONTEXT_KEY = "_records_are_scope_sliced"
# Per-``engineer_scope_features`` call: focal timestamps, sort order, gaps, etc.
_FE_SCOPE_ROW_CACHE_KEY = "_fe_scope_row_cache"

# Maps design-doc feature keys to pipeline methods (same names on subclasses).
_FEATURE_METHOD_NAMES: dict[str, str] = {
    feat.HOUR_OF_DAY: "_feature_hour_of_day",
    feat.DAY_OF_WEEK: "_feature_day_of_week",
    feat.IS_WEEKEND: "_feature_is_weekend",
    feat.VISIT_HOUR_BUCKET: "_feature_visit_hour_bucket",
    feat.TIME_SINCE_LAST_VISIT: "_feature_time_since_last_visit",
    feat.VISIT_INTERARRIVAL_TIME: "_feature_visit_interarrival_time",
    feat.NIGHT_VISIT_FLAG: "_feature_night_visit_flag",
    feat.VISITOR_TOTAL_VISITS: "_feature_visitor_total_visits",
    feat.VISITOR_WEEKLY_FREQUENCY: "_feature_visitor_weekly_frequency",
    feat.RESIDENT_VISIT_FREQUENCY: "_feature_resident_visit_frequency",
    feat.GUARD_TOTAL_VALIDATIONS: "_feature_guard_total_validations",
    feat.GUARD_NIGHT_VALIDATIONS: "_feature_guard_night_validations",
    feat.RELATIONSHIP_FREQUENCY: "_feature_relationship_frequency",
    feat.RELATIONSHIP_TRANSITION: "_feature_relationship_transition",
}


class SpatialAnomalyPipelineBase(ABC):
    """Visitor vs resident subclasses implement per-feature methods."""

    @property
    @abstractmethod
    def anomaly_type(self) -> AnomalyType:
        """Which high-level detection mode this pipeline implements."""

    def allowed_feature_scopes(self) -> list[AnalysisScope]:
        """
        Feature scopes for this anomaly type.

        See ``app.core.scope_config``.
        """
        return scopes_for_anomaly_type(self.anomaly_type)

    async def engineer_scope_features(
        self,
        scope: AnalysisScope,
        raw_records: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, float]:
        """
        Build only the features configured for ``scope``.

        Security scope uses the full window ``raw_records``; other scopes use a
        focal-centred cohort (same visitor / resident stream).
        """
        # Pre-sliced path: orchestrator already split rows by scope; else filter
        # cohort then apply scope-specific row filter (security = full window).
        if context.get(RECORDS_PRE_SLICED_CONTEXT_KEY):
            records = list(raw_records)
        else:
            cohort = self._cohort_records(raw_records, context)

            if scope == AnalysisScope.SECURITY:
                records = self._for_scope(scope, raw_records, context)
            else:
                records = self._for_scope(scope, cohort, context)

        keys = self._scope_feature_keys(scope)

        ctx = dict(context)
        ctx[_FE_SCOPE_ROW_CACHE_KEY] = self._build_fe_scope_row_cache(
            records, context
        )

        feats: dict[str, float] = {}
        for key in keys:
            method_name = _FEATURE_METHOD_NAMES[key]
            method = getattr(self, method_name)
            value = float(method(records, ctx))
            feats[key] = value
        return feats

    def _cohort_records(
        self,
        records: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Rows in the same stream as the focal (visitor or resident)."""
        focal = context.get("focal_record") or {}
        if self.anomaly_type == AnomalyType.VISITOR:
            uid = focal.get("user_id")
            hcode = focal.get("hashed_code")
            vname = focal.get("visitor_fullname")
            out: list[dict[str, Any]] = []
            for r in records:
                if uid is not None and str(r.get("user_id")) != str(uid):
                    continue
                if hcode is not None and r.get("hashed_code") != hcode:
                    continue
                if vname is not None and r.get("visitor_fullname") != vname:
                    continue
                out.append(r)
            return out or list(records)

        uid = focal.get("user_id") or context.get("user_id")
        if uid is None:
            return list(records)
        out2 = [r for r in records if str(r.get("user_id")) == str(uid)]
        return out2 or list(records)

    def _for_scope(
        self,
        scope: AnalysisScope,
        records: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Default row filter; subclasses narrow visitor-specific scopes."""
        if scope == AnalysisScope.SECURITY:
            return records
        return records

    def _scope_feature_keys(self, scope: AnalysisScope) -> list[str]:
        """Design-doc feature keys to compute for the given analysis scope."""
        if scope == AnalysisScope.VISITOR:
            return [
                feat.HOUR_OF_DAY,
                feat.DAY_OF_WEEK,
                feat.IS_WEEKEND,
                feat.VISIT_HOUR_BUCKET,
                feat.TIME_SINCE_LAST_VISIT,
                feat.VISIT_INTERARRIVAL_TIME,
                feat.NIGHT_VISIT_FLAG,
                feat.VISITOR_TOTAL_VISITS,
                feat.VISITOR_WEEKLY_FREQUENCY,
                feat.RELATIONSHIP_FREQUENCY,
                feat.RELATIONSHIP_TRANSITION,
            ]
        if scope == AnalysisScope.RESIDENT:
            return [
                feat.HOUR_OF_DAY,
                feat.DAY_OF_WEEK,
                feat.IS_WEEKEND,
                feat.VISIT_HOUR_BUCKET,
                feat.TIME_SINCE_LAST_VISIT,
                feat.VISIT_INTERARRIVAL_TIME,
                feat.NIGHT_VISIT_FLAG,
                feat.RESIDENT_VISIT_FREQUENCY,
            ]
        if scope == AnalysisScope.SECURITY:
            return [
                feat.GUARD_TOTAL_VALIDATIONS,
                feat.GUARD_NIGHT_VALIDATIONS,
                feat.NIGHT_VISIT_FLAG,
                feat.HOUR_OF_DAY,
            ]
        return [
            feat.HOUR_OF_DAY,
            feat.DAY_OF_WEEK,
            feat.IS_WEEKEND,
            feat.VISIT_INTERARRIVAL_TIME,
            feat.RESIDENT_VISIT_FREQUENCY,
            feat.VISITOR_WEEKLY_FREQUENCY,
            feat.GUARD_TOTAL_VALIDATIONS,
            feat.NIGHT_VISIT_FLAG,
        ]

    def _parse_ts(self, value: Any) -> datetime | None:
        """Parse API/JSON timestamps to timezone-aware UTC ``datetime``."""
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo:
                return value
            return value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            v = value.replace("Z", "+00:00")
            try:
                ts = datetime.fromisoformat(v)
            except ValueError:
                return None
            return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        return None

    def _event_ts_of_record(self, rec: dict[str, Any]) -> datetime | None:
        """Best event time for a log row (visit, access, or creation)."""
        for key in ("visit_time", "access_time", "created_at"):
            ts = self._parse_ts(rec.get(key))
            if ts is not None:
                return ts
        return None

    def _sorted_by_event(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return ``records`` sorted ascending by primary event timestamp."""
        epoch = datetime.min.replace(tzinfo=timezone.utc)

        def sort_key(r: dict[str, Any]) -> datetime:
            """Chronological key: event time or UTC epoch if missing."""
            t = self._event_ts_of_record(r)
            return t if t is not None else epoch

        return sorted(records, key=sort_key)

    def _build_fe_scope_row_cache(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Compute once per ``engineer_scope_features`` call: focal event time,
        time-ordered rows, focal index, previous event time, inter-arrival gaps,
        and scalar focal calendar fields reused across feature methods.
        """
        focal = self._focal_record(context)
        focal_event_ts = self._event_ts_of_record(focal)
        ordered = self._sorted_by_event(records)
        focal_idx = self._focal_index(ordered, context)
        prev_ts = self._prev_event_ts(ordered, focal_idx)
        gaps = self._gaps_through_focal(ordered, focal_idx)
        row: dict[str, Any] = {
            "focal_event_ts": focal_event_ts,
            "sorted_by_event": ordered,
            "focal_index": focal_idx,
            "prev_event_ts": prev_ts,
            "gaps_through_focal": gaps,
            "focal_relationship": focal.get("relationship_with_resident"),
        }
        if focal_event_ts is not None:
            row["focal_hour"] = focal_event_ts.hour
            row["focal_weekday"] = focal_event_ts.weekday()
            row["focal_is_weekend"] = (
                1.0 if focal_event_ts.weekday() >= 5 else 0.0
            )
            row["focal_hour_bucket"] = float(
                self._hour_bucket(focal_event_ts.hour)
            )
            row["focal_night_flag"] = (
                1.0
                if focal_event_ts.hour < 6 or focal_event_ts.hour >= 22
                else 0.0
            )
        else:
            row["focal_hour"] = None
            row["focal_weekday"] = None
            row["focal_is_weekend"] = 0.0
            row["focal_hour_bucket"] = 0.0
            row["focal_night_flag"] = 0.0
        return row

    def _ordered_for_features(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Time-sorted rows for the current scope; uses scope row cache when set."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "sorted_by_event" in c:
            return c["sorted_by_event"]
        return self._sorted_by_event(records)

    def _focal_index_for_features(
        self, ordered: list[dict[str, Any]], context: dict[str, Any]
    ) -> int:
        """Focal row index in ``ordered``; uses cache when ``ordered`` is cached."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if (
            isinstance(c, dict)
            and c.get("sorted_by_event") is ordered
            and "focal_index" in c
        ):
            return int(c["focal_index"])
        return self._focal_index(ordered, context)

    def _focal_record(self, context: dict[str, Any]) -> dict[str, Any]:
        """Anchor log row dict placed in context by the orchestrator."""
        return context.get("focal_record") or {}

    def _focal_event_ts(self, context: dict[str, Any]) -> datetime | None:
        """Event timestamp of the focal (current validation) log row."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "focal_event_ts" in c:
            return c["focal_event_ts"]
        return self._event_ts_of_record(self._focal_record(context))

    def _focal_index(
        self, sorted_records: list[dict[str, Any]], context: dict[str, Any]
    ) -> int:
        """Index of the focal row in a time-sorted cohort (fallback: last row)."""
        focal = self._focal_record(context)
        fid = focal.get("id")
        if fid is None or not sorted_records:
            return max(0, len(sorted_records) - 1)
        fs = str(fid)
        for i, r in enumerate(sorted_records):
            if str(r.get("id")) == fs:
                return i
        return max(0, len(sorted_records) - 1)

    def _prev_event_ts(
        self,
        sorted_records: list[dict[str, Any]],
        focal_idx: int,
    ) -> datetime | None:
        """Event time of the chronologically previous row before the focal."""
        if focal_idx <= 0:
            return None
        return self._event_ts_of_record(sorted_records[focal_idx - 1])

    def _mean(self, values: list[float]) -> float:
        """Arithmetic mean; empty input yields ``0.0``."""
        if not values:
            return 0.0
        return float(sum(values) / len(values))

    def _history_weeks(self, context: dict[str, Any]) -> float:
        """Weeks of history implied by ``history_window_days`` (for rates)."""
        days = float(context.get("history_window_days") or 30.0)
        return max(days / 7.0, 1e-6)

    def _hour_bucket(self, hour: int) -> float:
        """Coarse day-part bucket index for hour-of-day (0=night..3=evening)."""
        if 0 <= hour < 6:
            return 0.0
        if 6 <= hour < 12:
            return 1.0
        if 12 <= hour < 18:
            return 2.0
        return 3.0

    def _gaps_through_focal(
        self,
        sorted_records: list[dict[str, Any]],
        focal_idx: int,
    ) -> list[float]:
        """Inter-arrival hours between consecutive events up to the focal."""
        gaps: list[float] = []
        for i in range(1, focal_idx + 1):
            t0 = self._event_ts_of_record(sorted_records[i - 1])
            t1 = self._event_ts_of_record(sorted_records[i])
            if t0 is None or t1 is None:
                continue
            gaps.append((t1 - t0).total_seconds() / 3600.0)
        return gaps


class VisitorAnomalyPipeline(SpatialAnomalyPipelineBase):
    """Visitor mode: all feature scopes; focal = anchor visitor log row."""

    @property
    def anomaly_type(self) -> AnomalyType:
        """This pipeline implements visitor-centred anomaly detection."""
        return AnomalyType.VISITOR

    def _for_scope(
        self,
        scope: AnalysisScope,
        records: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Security uses full window; visitor scope keeps rows with visitor name."""
        if scope == AnalysisScope.SECURITY:
            return records
        if scope == AnalysisScope.VISITOR:
            return [r for r in records if "visitor_fullname" in r]
        return records

    def _feature_hour_of_day(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Hour (0–23) of the focal visitor validation event."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and c.get("focal_hour") is not None:
            out = float(c["focal_hour"])
        else:
            ts = self._focal_event_ts(context)
            out = float(ts.hour) if ts is not None else 0.0
        return out

    def _feature_day_of_week(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Weekday index (Mon=0) of the focal visitor event."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and c.get("focal_weekday") is not None:
            out = float(c["focal_weekday"])
        else:
            ts = self._focal_event_ts(context)
            out = float(ts.weekday()) if ts is not None else 0.0
        return out

    def _feature_is_weekend(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """1 if the focal visitor event falls on Sat/Sun, else 0."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "focal_is_weekend" in c:
            out = float(c["focal_is_weekend"])
            return out
        ts = self._focal_event_ts(context)
        if ts is None:
            out = 0.0
            return out
        out = float(1.0 if ts.weekday() >= 5 else 0.0)
        return out

    def _feature_visit_hour_bucket(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Coarse day-part bucket for the focal visitor event hour."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "focal_hour_bucket" in c:
            out = float(c["focal_hour_bucket"])
            return out
        ts = self._focal_event_ts(context)
        if ts is None:
            out = 0.0
            return out
        out = float(self._hour_bucket(ts.hour))
        return out

    def _feature_time_since_last_visit(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Hours from the previous cohort visit to the focal visit."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict):
            focal_ts = c.get("focal_event_ts")
            prev_ts = c.get("prev_event_ts")
            if focal_ts is not None and prev_ts is not None:
                out = (focal_ts - prev_ts).total_seconds() / 3600.0
                return out
        ordered = self._ordered_for_features(records, context)
        idx = self._focal_index_for_features(ordered, context)
        focal_ts = self._focal_event_ts(context)
        prev_ts = self._prev_event_ts(ordered, idx)
        if focal_ts is None or prev_ts is None:
            out = 0.0
            return out
        out = (focal_ts - prev_ts).total_seconds() / 3600.0
        return out

    def _feature_visit_interarrival_time(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Mean inter-arrival hours for consecutive visits up to the focal."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "gaps_through_focal" in c:
            out = self._mean(c["gaps_through_focal"])
            return out
        ordered = self._ordered_for_features(records, context)
        idx = self._focal_index_for_features(ordered, context)
        out = self._mean(self._gaps_through_focal(ordered, idx))
        return out

    def _feature_night_visit_flag(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """1 if the focal visit hour is night (before 6 or from 22), else 0."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "focal_night_flag" in c:
            out = float(c["focal_night_flag"])
            return out
        ts = self._focal_event_ts(context)
        if ts is None:
            out = 0.0
            return out
        out = float(1.0 if ts.hour < 6 or ts.hour >= 22 else 0.0)
        return out

    def _feature_visitor_total_visits(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Count of cohort rows (same visitor stream in the window)."""
        out = float(len(records))
        return out

    def _feature_visitor_weekly_frequency(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Visits per week implied by cohort size and the history window."""
        out = float(len(records) / self._history_weeks(context))
        return out

    def _feature_resident_visit_frequency(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Cohort visit count per week (resident stream proxy on visitor data)."""
        out = float(len(records) / self._history_weeks(context))
        return out

    def _feature_guard_total_validations(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Validations in the window for ``context.security_id`` (or all)."""
        sec = context.get("security_id")
        if sec is None:
            out = float(len(records))
        else:
            out = float(
                sum(
                    1 for r in records if str(r.get("security_id")) == str(sec)
                )
            )
        return out

    def _feature_guard_night_validations(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Count of night-time validations in the full-window security slice."""
        n = 0
        for r in records:
            ts = self._event_ts_of_record(r)
            if ts is not None and (ts.hour < 6 or ts.hour >= 22):
                n += 1
        out = float(n)
        return out

    def _feature_relationship_frequency(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Share of cohort visits whose relationship matches the focal's."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        rel0 = (
            c.get("focal_relationship")
            if isinstance(c, dict) and "focal_relationship" in c
            else self._focal_record(context).get("relationship_with_resident")
        )
        if rel0 is None or not records:
            out = 0.0
            return out
        same = sum(
            1 for r in records if r.get("relationship_with_resident") == rel0
        )
        out = float(same / len(records))
        return out

    def _feature_relationship_transition(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """1 if focal relationship differs from the immediately prior visit."""
        ordered = self._ordered_for_features(records, context)
        idx = self._focal_index_for_features(ordered, context)
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        rel0 = (
            c.get("focal_relationship")
            if isinstance(c, dict) and "focal_relationship" in c
            else self._focal_record(context).get("relationship_with_resident")
        )
        if rel0 is None or idx <= 0:
            out = 0.0
            return out
        prev_rel = ordered[idx - 1].get("relationship_with_resident")
        out = float(1.0 if prev_rel != rel0 else 0.0)
        return out


class ResidentAnomalyPipeline(SpatialAnomalyPipelineBase):
    """Resident mode; focal = anchor resident log row."""

    @property
    def anomaly_type(self) -> AnomalyType:
        """This pipeline implements resident-centred anomaly detection."""
        return AnomalyType.RESIDENT

    def _feature_hour_of_day(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Hour (0–23) of the focal resident access event."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and c.get("focal_hour") is not None:
            out = float(c["focal_hour"])
        else:
            ts = self._focal_event_ts(context)
            out = float(ts.hour) if ts is not None else 0.0
        return out

    def _feature_day_of_week(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Weekday index (Mon=0) of the focal resident event."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and c.get("focal_weekday") is not None:
            out = float(c["focal_weekday"])
        else:
            ts = self._focal_event_ts(context)
            out = float(ts.weekday()) if ts is not None else 0.0
        return out

    def _feature_is_weekend(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """1 if the focal resident event falls on Sat/Sun, else 0."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "focal_is_weekend" in c:
            out = float(c["focal_is_weekend"])
            return out
        ts = self._focal_event_ts(context)
        if ts is None:
            out = 0.0
            return out
        out = float(1.0 if ts.weekday() >= 5 else 0.0)
        return out

    def _feature_visit_hour_bucket(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Coarse day-part bucket for the focal resident event hour."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "focal_hour_bucket" in c:
            out = float(c["focal_hour_bucket"])
            return out
        ts = self._focal_event_ts(context)
        if ts is None:
            out = 0.0
            return out
        out = float(self._hour_bucket(ts.hour))
        return out

    def _feature_time_since_last_visit(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Hours from the previous cohort access to the focal access."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict):
            focal_ts = c.get("focal_event_ts")
            prev_ts = c.get("prev_event_ts")
            if focal_ts is not None and prev_ts is not None:
                out = (focal_ts - prev_ts).total_seconds() / 3600.0
                return out
        ordered = self._ordered_for_features(records, context)
        idx = self._focal_index_for_features(ordered, context)
        focal_ts = self._focal_event_ts(context)
        prev_ts = self._prev_event_ts(ordered, idx)
        if focal_ts is None or prev_ts is None:
            out = 0.0
            return out
        out = (focal_ts - prev_ts).total_seconds() / 3600.0
        return out

    def _feature_visit_interarrival_time(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Mean inter-arrival hours for consecutive accesses up to the focal."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "gaps_through_focal" in c:
            out = self._mean(c["gaps_through_focal"])
            return out
        ordered = self._ordered_for_features(records, context)
        idx = self._focal_index_for_features(ordered, context)
        out = self._mean(self._gaps_through_focal(ordered, idx))
        return out

    def _feature_night_visit_flag(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """1 if the focal access hour is night (before 6 or from 22), else 0."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        if isinstance(c, dict) and "focal_night_flag" in c:
            out = float(c["focal_night_flag"])
            return out
        ts = self._focal_event_ts(context)
        if ts is None:
            out = 0.0
            return out
        out = float(1.0 if ts.hour < 6 or ts.hour >= 22 else 0.0)
        return out

    def _feature_visitor_total_visits(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Row count in cohort (resident pipeline; key name kept for parity)."""
        out = float(len(records))
        return out

    def _feature_visitor_weekly_frequency(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Cohort events per week for shared feature key naming."""
        out = float(len(records) / self._history_weeks(context))
        return out

    def _feature_resident_visit_frequency(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Resident cohort accesses per week over the history window."""
        out = float(len(records) / self._history_weeks(context))
        return out

    def _feature_guard_total_validations(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Validations in the window for ``context.security_id`` (or all)."""
        sec = context.get("security_id")
        if sec is None:
            out = float(len(records))
        else:
            out = float(
                sum(
                    1 for r in records if str(r.get("security_id")) == str(sec)
                )
            )
        return out

    def _feature_guard_night_validations(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Count of night-time validations in the full-window security slice."""
        n = 0
        for r in records:
            ts = self._event_ts_of_record(r)
            if ts is not None and (ts.hour < 6 or ts.hour >= 22):
                n += 1
        out = float(n)
        return out

    def _feature_relationship_frequency(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """Share of cohort rows whose relationship matches the focal's."""
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        rel0 = (
            c.get("focal_relationship")
            if isinstance(c, dict) and "focal_relationship" in c
            else self._focal_record(context).get("relationship_with_resident")
        )
        if rel0 is None or not records:
            out = 0.0
            return out
        same = sum(
            1 for r in records if r.get("relationship_with_resident") == rel0
        )
        out = float(same / len(records))
        return out

    def _feature_relationship_transition(
        self, records: list[dict[str, Any]], context: dict[str, Any]
    ) -> float:
        """1 if focal relationship differs from the immediately prior row."""
        ordered = self._ordered_for_features(records, context)
        idx = self._focal_index_for_features(ordered, context)
        c = context.get(_FE_SCOPE_ROW_CACHE_KEY)
        rel0 = (
            c.get("focal_relationship")
            if isinstance(c, dict) and "focal_relationship" in c
            else self._focal_record(context).get("relationship_with_resident")
        )
        if rel0 is None or idx <= 0:
            out = 0.0
            return out
        prev_rel = ordered[idx - 1].get("relationship_with_resident")
        out = float(1.0 if prev_rel != rel0 else 0.0)
        return out


def pipeline_for_type(anomaly_type: AnomalyType) -> SpatialAnomalyPipelineBase:
    """
    Return the concrete pipeline implementation for ``anomaly_type``.

    Raises:
        ValueError: If ``anomaly_type`` is not a supported enum member.
    """
    if anomaly_type == AnomalyType.VISITOR:
        return VisitorAnomalyPipeline()
    if anomaly_type == AnomalyType.RESIDENT:
        return ResidentAnomalyPipeline()
    raise ValueError(f"Unsupported anomaly type: {anomaly_type}")
