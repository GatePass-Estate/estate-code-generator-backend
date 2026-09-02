"""Read predictionresult rows for the spatial-anomaly result page."""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Float, Select, String, and_, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError
from app.models.code_service.prediction_result import (
    PredictionResult as TableModel,
)
from app.models.code_service.resident_log import ResidentLog
from app.models.code_service.visitor_log import VisitorLog
from app.models.user_profile.estates import Estates
from app.models.user_profile.users import Users
from app.schemas.code_service.prediction_result import (
    HIGH_RISK_SCORE,
    MEDIUM_SCORE,
    NORMAL_SAMPLE_FRACTION,
    AiSummaryPatchRequest,
    AiSummaryResponse,
    CaseDemographicResponse,
    CaseDetailResponse,
    CaseRequest,
    HistoryItem,
    HistoryResponse,
    ListResponse,
    OverviewRequest,
    OverviewResponse,
    PredictionListItem,
    SearchRequest,
    Severity,
    UserType,
)
from app.schemas.code_service.visitor_log import Gender
from app.schemas.user_profile.users import UserRole

logger = logging.getLogger(__name__)

# Stored as core.userrole names (PRIMARY_ADMIN); compare via lower(cast).
_RESIDENT_ROLE_VALUES = (
    UserRole.RESIDENT.value,
    UserRole.ADMIN.value,
    UserRole.PRIMARY_ADMIN.value,
)


def _role_key():
    """Lowercased ``users.role`` for comparing enum names stored uppercase."""
    return func.lower(cast(Users.role, String))


def _is_resident_user():
    """True for resident, admin, or primary_admin (not security)."""
    return _role_key().in_(_RESIDENT_ROLE_VALUES)


def _payload_is_anomalous():
    """SQL predicate: stored ``result.result.is_anomalous`` is true."""
    return TableModel.result["result"]["is_anomalous"].astext == "true"


def _payload_score():
    """SQL expression for stored ``result.result.final_score`` as float."""
    return cast(TableModel.result["result"]["final_score"].astext, Float)


def _apply_range(query: Select, column, from_date, to_date) -> Select:
    """Apply inclusive ``from_date`` / ``to_date`` bounds on ``column``."""
    if from_date is not None:
        query = query.where(column >= from_date)
    if to_date is not None:
        query = query.where(column <= to_date)
    return query


def _or_clauses(clauses: list):
    """Combine SQL clauses with OR; None if empty, unwrap a single clause."""
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return or_(*clauses)


def _user_type_clause(user_types: list[UserType] | None):
    """OR guest (has visitor log) and/or resident-role resident-log rows."""
    if not user_types:
        return None
    selected = set(user_types)
    clauses = []
    if UserType.GUEST in selected:
        clauses.append(TableModel.visitor_log_id.isnot(None))
    if UserType.RESIDENT in selected:
        clauses.append(
            and_(
                TableModel.resident_log_id.isnot(None),
                _is_resident_user(),
            )
        )
    return _or_clauses(clauses)


def _gender_clause(genders: list[Gender] | None):
    """Match visitor-log or user-profile gender against any selected value."""
    if not genders:
        return None
    values = [g.value for g in genders]
    return or_(
        func.lower(cast(VisitorLog.gender, String)).in_(values),
        func.lower(cast(Users.gender, String)).in_(values),
    )


def _severity_clause(severities: list[Severity] | None):
    """OR score bands: low < 0.5, medium 0.5–0.8, high >= 0.8."""
    if not severities:
        return None
    selected = set(severities)
    clauses = []
    if Severity.HIGH in selected:
        clauses.append(_payload_score() >= HIGH_RISK_SCORE)
    if Severity.MEDIUM in selected:
        clauses.append(
            and_(
                _payload_score() >= MEDIUM_SCORE,
                _payload_score() < HIGH_RISK_SCORE,
            )
        )
    if Severity.LOW in selected:
        clauses.append(_payload_score() < MEDIUM_SCORE)
    return _or_clauses(clauses)


def _unwrap_result(raw: Any) -> dict[str, Any]:
    """Return the inner prediction dict, or ``raw`` if already unwrapped."""
    if isinstance(raw, dict) and isinstance(raw.get("result"), dict):
        return raw["result"]
    return raw if isinstance(raw, dict) else {}


def _payload_flag_anomalous(raw: Any) -> bool:
    """Python-side ``is_anomalous`` flag from a stored result payload."""
    return bool(_unwrap_result(raw).get("is_anomalous"))


def _bump_max(store: dict[str, float], key: str, value: float) -> None:
    """Keep the larger of ``value`` and any previous max for ``key``."""
    prev = store.get(key)
    store[key] = value if prev is None else max(prev, value)


def _collect_maxes(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, float], dict[str, dict[str, float]]]:
    """
    Max feature values and scope scores across every prediction in ``rows``.

    Returns global feature maxes, per-scope score maxes, and per-scope
    feature maxes used as spider/factor ``scale`` in ai-service.
    """
    feature_max: dict[str, float] = {}
    scope_score_max: dict[str, float] = {}
    scope_feature_max: dict[str, dict[str, float]] = {}
    # Walk every prediction (anomalous included). Per-scope score →
    # scope_max_scores; per-feature value → feature_max_values and
    # scope_feature_max_values (ai-service ``scale``).
    for raw in rows:
        payload = _unwrap_result(raw)
        scopes = (payload.get("transparency") or {}).get("scopes") or []
        if not isinstance(scopes, list):
            continue
        for detail in scopes:
            if not isinstance(detail, dict):
                continue
            scope = detail.get("scope")
            if not isinstance(scope, str) or not scope:
                continue
            score = detail.get("score")
            try:
                if score is not None:
                    # → contributing_factors[].scale (period max scope score)
                    _bump_max(scope_score_max, scope, float(score))
            except (TypeError, ValueError):
                pass
            feat_store = scope_feature_max.setdefault(scope, {})
            for fc in detail.get("feature_contributions") or []:
                if not isinstance(fc, dict):
                    continue
                name = fc.get("feature_name")
                if not isinstance(name, str) or not name:
                    continue
                try:
                    value = fc.get("value")
                    if value is None:
                        continue
                    fval = float(value)
                except (TypeError, ValueError):
                    continue
                # global max → spider_plot[].scale
                _bump_max(feature_max, name, fval)
                # per-scope max → contributing_factors[].sub_factors[].scale
                _bump_max(feat_store, name, fval)
    return feature_max, scope_score_max, scope_feature_max


_CANONICAL_SCOPES = (
    "visitor_specific",
    "resident_specific",
    "security_specific",
    "estate_wide",
)


def _payload_scopes(raw: Any) -> set[str]:
    """Scope names stored on one prediction payload."""
    payload = _unwrap_result(raw)
    scopes = (payload.get("transparency") or {}).get("scopes") or []
    names: set[str] = set()
    if not isinstance(scopes, list):
        return names
    for detail in scopes:
        if not isinstance(detail, dict):
            continue
        scope = detail.get("scope")
        if isinstance(scope, str) and scope:
            names.add(scope)
    return names


def _stratified_normal_sample(
    non_anom: list[dict[str, Any]], limit_n: int
) -> list[dict[str, Any]]:
    """
    Random sample that still includes a row for each known scope.

    A plain 30% draw can miss visitor (or other) scopes when most
    non-anomalous rows are another type. Pick one covering row per
    canonical scope first, then fill the remaining slots at random.
    """
    if not non_anom:
        return []
    limit_n = min(max(limit_n, 1), len(non_anom))
    # 1. Bucket non-anomalous rows by canonical scope so a 30% draw
    #    cannot drop visitor_specific (or any other) entirely.
    by_scope: dict[str, list[dict[str, Any]]] = {
        s: [] for s in _CANONICAL_SCOPES
    }
    for row in non_anom:
        for scope in _payload_scopes(row):
            bucket = by_scope.get(scope)
            if bucket is not None:
                bucket.append(row)
    # 2. One covering row per populated scope (same row can cover several).
    picked: list[dict[str, Any]] = []
    seen: set[int] = set()
    for rows in by_scope.values():
        if not rows:
            continue
        choice = random.choice(rows)
        marker = id(choice)
        if marker in seen:
            continue
        seen.add(marker)
        picked.append(choice)
    # 3. Raise the cap if needed, then fill remaining slots at random.
    #    → ai-service normal_sample for spider_plot / factor means.
    limit_n = min(len(non_anom), max(limit_n, len(picked)))
    remaining = [r for r in non_anom if id(r) not in seen]
    need = limit_n - len(picked)
    if need > 0 and remaining:
        picked.extend(random.sample(remaining, min(need, len(remaining))))
    return picked


def _severity_of(score: float | None) -> Severity | None:
    """Map ``final_score`` onto low / medium / high; None if score missing."""
    if score is None:
        return None
    if score >= HIGH_RISK_SCORE:
        return Severity.HIGH
    if score >= MEDIUM_SCORE:
        return Severity.MEDIUM
    return Severity.LOW


def _has_summary_tier(raw: Any, key: str) -> bool:
    """True when ``ai_summary[key]`` is a non-empty cached report."""
    if not isinstance(raw, dict):
        return False
    value = raw.get(key)
    if value is None or value == "" or value == {}:
        return False
    return True


def _week_span(from_date: datetime | None, to_date: datetime | None) -> float:
    """Weeks in the inclusive window; at least one day (1/7 week)."""
    if from_date is None or to_date is None:
        return 1.0
    seconds = (to_date - from_date).total_seconds()
    days = max(seconds / 86400.0, 1.0)
    return days / 7.0


class PredictionResultRepository:
    """Search and overview reads over ``core.predictionresult``."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to ``session``."""
        self.session = session

    def _base_join(self) -> Select:
        """Prediction rows with visitor/resident name and gender columns."""
        return (
            select(
                TableModel,
                VisitorLog.gender.label("visitor_gender"),
                VisitorLog.visitor_fullname.label("visitor_fullname"),
                VisitorLog.hashed_code.label("visitor_code"),
                VisitorLog.visit_time.label("visitor_time"),
                ResidentLog.full_name.label("resident_fullname"),
                ResidentLog.hashed_code.label("resident_code"),
                ResidentLog.access_time.label("resident_time"),
                ResidentLog.user_id.label("resident_user_id"),
                Users.gender.label("resident_gender"),
            )
            .outerjoin(VisitorLog, TableModel.visitor_log_id == VisitorLog.id)
            .outerjoin(
                ResidentLog, TableModel.resident_log_id == ResidentLog.id
            )
            .outerjoin(Users, ResidentLog.user_id == Users.id)
            .where(TableModel.is_deleted == False)  # noqa: E712
        )

    def _estate_scope(self, query: Select, estate_id: UUID) -> Select:
        """Restrict joined rows to visitor or resident logs for the estate."""
        return query.where(
            or_(
                VisitorLog.estate_id == estate_id,
                ResidentLog.estate_id == estate_id,
            )
        )

    def _search_query(self, request: SearchRequest) -> Select:
        """Apply estate, date, user-type, gender, anomalous, and severity."""
        query = self._estate_scope(
            self._base_join(), UUID(str(request.estate_id))
        )
        query = _apply_range(
            query, TableModel.created_at, request.from_date, request.to_date
        )
        user_type_filter = _user_type_clause(request.user_type)
        if user_type_filter is not None:
            query = query.where(user_type_filter)
        gender_filter = _gender_clause(request.gender)
        if gender_filter is not None:
            query = query.where(gender_filter)
        if request.is_anomalous is True:
            query = query.where(_payload_is_anomalous())
        elif request.is_anomalous is False:
            query = query.where(
                TableModel.result["result"]["is_anomalous"].astext == "false"
            )
        severity_filter = _severity_clause(request.severity)
        if severity_filter is not None:
            query = query.where(severity_filter)
        return query

    def _to_item(self, row) -> PredictionListItem:
        """Map a joined search row onto the list-item schema."""
        record = row[0]
        mapping = row._mapping
        payload = _unwrap_result(record.result)
        score = payload.get("final_score")
        score_f = float(score) if score is not None else None
        is_guest = record.visitor_log_id is not None
        gender_raw = (
            mapping["visitor_gender"]
            if is_guest
            else mapping["resident_gender"]
        )
        if hasattr(gender_raw, "value"):
            gender_raw = gender_raw.value
        name = (
            mapping["visitor_fullname"]
            if is_guest
            else mapping["resident_fullname"]
        )
        return PredictionListItem(
            id=record.id,
            created_at=record.created_at,
            prediction_type=record.prediction_type,
            user_type=UserType.GUEST if is_guest else UserType.RESIDENT,
            gender=gender_raw,
            display_name=name,
            final_score=score_f,
            is_anomalous=payload.get("is_anomalous"),
            severity=_severity_of(score_f),
            anomaly_type=payload.get("anomaly_type"),
            has_tier1_summary=_has_summary_tier(record.ai_summary, "tier1"),
            has_tier2_summary=_has_summary_tier(record.ai_summary, "tier2"),
        )

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 10
    ) -> ListResponse:
        """Paginate ``_search_query`` ordered by ``created_at``."""
        query = self._search_query(request)
        order = (
            TableModel.created_at.asc()
            if request.sort_order == "asc"
            else TableModel.created_at.desc()
        )
        count_query = select(func.count()).select_from(query.subquery())
        paginated = (
            query.order_by(order).limit(limit).offset((page - 1) * limit)
        )
        try:
            total = await self.session.scalar(count_query) or 0
            rows = (await self.session.execute(paginated)).all()
            return ListResponse(
                items=[self._to_item(row) for row in rows],
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            logger.exception("search prediction result")
            raise DatabaseError("Database error in search") from e

    async def _scalar(self, query) -> int:
        """Execute ``query`` and return the integer scalar (0 if null)."""
        return int(await self.session.scalar(query) or 0)

    def _anomalous_instance_q(
        self,
        estate_id: UUID,
        from_date: datetime | None,
        to_date: datetime | None,
        *,
        user_type: UserType | None = None,
        high_risk: bool = False,
    ) -> Select:
        """Count anomalous prediction rows (not unique people) in the window."""
        q = (
            select(func.count())
            .select_from(TableModel)
            .outerjoin(VisitorLog, TableModel.visitor_log_id == VisitorLog.id)
            .outerjoin(
                ResidentLog, TableModel.resident_log_id == ResidentLog.id
            )
            .where(
                TableModel.is_deleted == False,  # noqa: E712
                or_(
                    VisitorLog.estate_id == estate_id,
                    ResidentLog.estate_id == estate_id,
                ),
                _payload_is_anomalous(),
            )
        )
        if user_type == UserType.GUEST:
            # → evidence_summary.total_anomalous_visitors_instances
            q = q.where(TableModel.visitor_log_id.isnot(None))
        elif user_type == UserType.RESIDENT:
            # → evidence_summary.total_anomalous_residents_instances
            q = q.where(TableModel.resident_log_id.isnot(None))
        q = _apply_range(q, TableModel.created_at, from_date, to_date)
        if high_risk:
            # → demographic.total_high_risk_instances
            q = q.where(_payload_score() >= HIGH_RISK_SCORE)
        return q

    async def _window_rows(
        self,
        estate_id: UUID,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> list[dict[str, Any]]:
        """Load all prediction JSONB payloads for the estate window."""
        all_q = (
            select(TableModel.result)
            .outerjoin(VisitorLog, TableModel.visitor_log_id == VisitorLog.id)
            .outerjoin(
                ResidentLog, TableModel.resident_log_id == ResidentLog.id
            )
            .where(
                TableModel.is_deleted == False,  # noqa: E712
                or_(
                    VisitorLog.estate_id == estate_id,
                    ResidentLog.estate_id == estate_id,
                ),
            )
        )
        all_q = _apply_range(all_q, TableModel.created_at, from_date, to_date)
        return [
            row
            for row in (await self.session.execute(all_q)).scalars().all()
            if isinstance(row, dict)
        ]

    def _sample_and_maxes(
        self, all_rows: list[dict[str, Any]]
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, float],
        dict[str, float],
        dict[str, dict[str, float]],
    ]:
        """Period max maps plus a 30% non-anomalous sample."""
        # Maxes use every row (anomalous included) → scale in ai-service.
        feature_max, scope_max, scope_feat_max = _collect_maxes(all_rows)
        # Means use only non-anomalous rows, stratified so each scope
        # appears when the window has it.
        non_anom = [
            row for row in all_rows if not _payload_flag_anomalous(row)
        ]
        sample: list[dict[str, Any]] = []
        if non_anom:
            limit_n = min(
                len(non_anom),
                max(1, int(len(non_anom) * NORMAL_SAMPLE_FRACTION)),
            )
            sample = _stratified_normal_sample(non_anom, limit_n)
        return sample, feature_max, scope_max, scope_feat_max

    async def _get_case_row(self, request: CaseRequest):
        """Load the selected prediction joined to visitor/resident logs."""
        estate_id = UUID(str(request.estate_id))
        pred_id = UUID(str(request.prediction_id))
        query = self._estate_scope(self._base_join(), estate_id).where(
            TableModel.id == pred_id
        )
        row = (await self.session.execute(query)).first()
        if row is None:
            raise NotFoundError(f"Prediction {pred_id} not found")
        return row

    def _identity(self, row) -> tuple[Any, dict, bool, str | None, Any]:
        """Record, mapping, is_guest, display name, resident user id."""
        record = row[0]
        mapping = row._mapping
        is_guest = record.visitor_log_id is not None
        name = (
            mapping["visitor_fullname"]
            if is_guest
            else mapping["resident_fullname"]
        )
        user_id = None if is_guest else mapping["resident_user_id"]
        return record, mapping, is_guest, name, user_id

    async def overview(self, request: OverviewRequest) -> OverviewResponse:
        """
        Load estate counts, a 30% non-anomalous sample, and period maxes.

        Guest uniqueness uses visitor-log ``visit_time``. Resident-side
        users are role resident, admin, or primary_admin. Anomalous and
        high-risk fields are prediction row counts. Max maps cover every
        prediction in the window, including anomalous rows.
        """
        estate_id = UUID(str(request.estate_id))
        try:
            estate = (
                await self.session.execute(
                    select(Estates).where(
                        Estates.id == estate_id,
                        Estates.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            # → demographic.estate_name / state / country
            if estate is None:
                raise NotFoundError(f"Estate {estate_id} not found")

            # unique visitor names in window → demographic.total_guests
            # and demographic.ratio.guest.count
            guest_q = select(
                func.count(func.distinct(VisitorLog.visitor_fullname))
            ).where(
                VisitorLog.estate_id == estate_id,
                VisitorLog.is_deleted == False,  # noqa: E712
            )
            guest_q = _apply_range(
                guest_q,
                VisitorLog.visit_time,
                request.from_date,
                request.to_date,
            )

            def _active_users() -> Select:
                """Count non-deleted users on this estate."""
                return (
                    select(func.count())
                    .select_from(Users)
                    .where(
                        Users.estate_id == estate_id,
                        Users.is_deleted == False,  # noqa: E712
                    )
                )

            anom_vis = await self._scalar(
                self._anomalous_instance_q(
                    estate_id,
                    request.from_date,
                    request.to_date,
                    user_type=UserType.GUEST,
                )
            )
            anom_res = await self._scalar(
                self._anomalous_instance_q(
                    estate_id,
                    request.from_date,
                    request.to_date,
                    user_type=UserType.RESIDENT,
                )
            )
            # all anomalous rows → demographic.total_anomalous_instances
            anom_all = await self._scalar(
                self._anomalous_instance_q(
                    estate_id, request.from_date, request.to_date
                )
            )
            high_all = await self._scalar(
                self._anomalous_instance_q(
                    estate_id,
                    request.from_date,
                    request.to_date,
                    high_risk=True,
                )
            )

            # all prediction payloads in window: maxes + 30% normal sample
            all_rows = await self._window_rows(
                estate_id, request.from_date, request.to_date
            )
            sample, feature_max, scope_max, scope_feat_max = (
                self._sample_and_maxes(all_rows)
            )

            return OverviewResponse(
                # → demographic.estate_name / state / country
                estate_name=estate.name,
                state=estate.state,
                country=estate.country,
                total_guests=await self._scalar(guest_q),
                # resident+admin+primary_admin → ratio.resident
                # (+ guests in ai-service → demographic.total_users)
                resident_count=await self._scalar(
                    _active_users().where(_is_resident_user())
                ),
                # → demographic.ratio.security
                security_count=await self._scalar(
                    _active_users().where(
                        _role_key() == UserRole.SECURITY.value
                    )
                ),
                total_anomalous_instances=anom_all,
                total_high_risk_instances=high_all,
                total_anomalous_residents_instances=anom_res,
                total_anomalous_visitors_instances=anom_vis,
                normal_sample=sample,
                feature_max_values=feature_max,
                scope_max_scores=scope_max,
                scope_feature_max_values=scope_feat_max,
            )
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.exception("overview prediction result")
            raise DatabaseError("Database error in overview") from e

    async def _count_entries(
        self,
        *,
        estate_id: UUID,
        is_guest: bool,
        display_name: str,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> int:
        """Count visitor or resident log rows for this named person."""
        name = display_name.strip().lower()
        if is_guest:
            q = (
                select(func.count())
                .select_from(VisitorLog)
                .where(
                    VisitorLog.estate_id == estate_id,
                    VisitorLog.is_deleted == False,  # noqa: E712
                    func.lower(VisitorLog.visitor_fullname) == name,
                )
            )
            q = _apply_range(q, VisitorLog.visit_time, from_date, to_date)
        else:
            q = (
                select(func.count())
                .select_from(ResidentLog)
                .where(
                    ResidentLog.estate_id == estate_id,
                    ResidentLog.is_deleted == False,  # noqa: E712
                    func.lower(ResidentLog.full_name) == name,
                )
            )
            q = _apply_range(q, ResidentLog.access_time, from_date, to_date)
        return await self._scalar(q)

    async def case_demographic(
        self, request: CaseRequest
    ) -> CaseDemographicResponse:
        """Name, user type, resident user id, entry rate, and summary flags."""
        try:
            # 1. Identity from the selected prediction's joined log.
            row = await self._get_case_row(request)
            record, _mapping, is_guest, name, user_id = self._identity(row)
            display = request.display_name or name or ""
            estate_id = UUID(str(request.estate_id))
            # 2. Log-row count in the window → total_entries;
            #    divide by weeks (min one day) → average_entry_per_week.
            total = await self._count_entries(
                estate_id=estate_id,
                is_guest=is_guest,
                display_name=display,
                from_date=request.from_date,
                to_date=request.to_date,
            )
            weeks = _week_span(request.from_date, request.to_date)
            avg = round(total / weeks, 2) if weeks else float(total)
            # 3. Cache flags only (not the summary body).
            return CaseDemographicResponse(
                prediction_id=record.id,
                display_name=name,
                user_type=(UserType.GUEST if is_guest else UserType.RESIDENT),
                user_id=user_id,
                total_entries=total,
                average_entry_per_week=avg,
                has_tier1_summary=_has_summary_tier(
                    record.ai_summary, "tier1"
                ),
                has_tier2_summary=_has_summary_tier(
                    record.ai_summary, "tier2"
                ),
            )
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.exception("case demographic prediction result")
            raise DatabaseError("Database error in case demographic") from e

    async def case_history(self, request: CaseRequest) -> HistoryResponse:
        """Five most recent predictions for the same name, selected last."""
        try:
            # 1. Resolve the selected person, then list prior predictions
            #    for the same visitor/resident name, newest first.
            row = await self._get_case_row(request)
            record, _mapping, is_guest, name, _uid = self._identity(row)
            display = (request.display_name or name or "").strip()
            estate_id = UUID(str(request.estate_id))
            query = self._estate_scope(self._base_join(), estate_id)
            if is_guest:
                query = query.where(
                    func.lower(VisitorLog.visitor_fullname) == display.lower()
                )
            else:
                query = query.where(
                    func.lower(ResidentLog.full_name) == display.lower()
                )
            # Inclusive of the selected row; never later than it.
            query = query.where(TableModel.created_at <= record.created_at)
            query = query.order_by(TableModel.created_at.desc()).limit(
                request.history_limit
            )
            rows = (await self.session.execute(query)).all()
            # 2. Map each row to validation time/code + severity band.
            items: list[HistoryItem] = []
            for hist in rows:
                rec = hist[0]
                mapping = hist._mapping
                guest = rec.visitor_log_id is not None
                payload = _unwrap_result(rec.result)
                score = payload.get("final_score")
                score_f = float(score) if score is not None else None
                items.append(
                    HistoryItem(
                        id=rec.id,
                        validated_at=(
                            mapping["visitor_time"]
                            if guest
                            else mapping["resident_time"]
                        ),
                        validated_code=(
                            mapping["visitor_code"]
                            if guest
                            else mapping["resident_code"]
                        ),
                        severity=_severity_of(score_f),
                        is_anomalous=payload.get("is_anomalous"),
                        final_score=score_f,
                    )
                )
            return HistoryResponse(items=items)
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.exception("case history prediction result")
            raise DatabaseError("Database error in case history") from e

    async def case_detail(self, request: CaseRequest) -> CaseDetailResponse:
        """Selected result JSON plus period sample and max maps."""
        try:
            # 1. Selected prediction identity + stored result JSON.
            row = await self._get_case_row(request)
            record, _mapping, is_guest, name, user_id = self._identity(row)
            estate_id = UUID(str(request.estate_id))
            # 2. Same window sample + max maps as first-level overview
            #    (instance overlay happens in ai-service).
            all_rows = await self._window_rows(
                estate_id, request.from_date, request.to_date
            )
            sample, feature_max, scope_max, scope_feat_max = (
                self._sample_and_maxes(all_rows)
            )
            summary = record.ai_summary
            if not isinstance(summary, dict):
                summary = None
            return CaseDetailResponse(
                prediction_id=record.id,
                created_at=record.created_at,
                prediction_type=record.prediction_type,
                user_type=(UserType.GUEST if is_guest else UserType.RESIDENT),
                display_name=name,
                user_id=user_id,
                result=record.result
                if isinstance(record.result, dict)
                else {},
                ai_summary=summary,
                has_tier1_summary=_has_summary_tier(summary, "tier1"),
                has_tier2_summary=_has_summary_tier(summary, "tier2"),
                normal_sample=sample,
                feature_max_values=feature_max,
                scope_max_scores=scope_max,
                scope_feature_max_values=scope_feat_max,
            )
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.exception("case detail prediction result")
            raise DatabaseError("Database error in case detail") from e

    async def patch_ai_summary(
        self, prediction_id: UUID, request: AiSummaryPatchRequest
    ) -> AiSummaryResponse:
        """Merge ``tier1`` / ``tier2`` into the cached ``ai_summary`` JSON."""
        try:
            query = select(TableModel).where(
                TableModel.id == prediction_id,
                TableModel.is_deleted == False,  # noqa: E712
            )
            record = (await self.session.execute(query)).scalar_one_or_none()
            if record is None:
                raise NotFoundError(f"Prediction {prediction_id} not found")
            # Merge only supplied keys so a later tier2 patch keeps tier1.
            merged = dict(record.ai_summary or {})
            if request.tier1 is not None:
                merged["tier1"] = request.tier1
            if request.tier2 is not None:
                merged["tier2"] = request.tier2
            record.ai_summary = merged
            await self.session.flush()
            await self.session.refresh(record)
            summary = record.ai_summary
            if not isinstance(summary, dict):
                summary = None
            return AiSummaryResponse(
                prediction_id=record.id,
                ai_summary=summary,
                has_tier1_summary=_has_summary_tier(summary, "tier1"),
                has_tier2_summary=_has_summary_tier(summary, "tier2"),
            )
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.exception("patch ai_summary prediction result")
            raise DatabaseError("Database error in patch ai_summary") from e
