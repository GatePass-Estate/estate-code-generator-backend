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
                _bump_max(feature_max, name, fval)
                _bump_max(feat_store, name, fval)
    return feature_max, scope_score_max, scope_feature_max


def _severity_of(score: float | None) -> Severity | None:
    """Map ``final_score`` onto low / medium / high; None if score missing."""
    if score is None:
        return None
    if score >= HIGH_RISK_SCORE:
        return Severity.HIGH
    if score >= MEDIUM_SCORE:
        return Severity.MEDIUM
    return Severity.LOW


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
                ResidentLog.full_name.label("resident_fullname"),
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
            all_q = (
                select(TableModel.result)
                .outerjoin(
                    VisitorLog, TableModel.visitor_log_id == VisitorLog.id
                )
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
            all_q = _apply_range(
                all_q,
                TableModel.created_at,
                request.from_date,
                request.to_date,
            )
            all_rows = [
                row
                for row in (await self.session.execute(all_q)).scalars().all()
                if isinstance(row, dict)
            ]
            feature_max, scope_max, scope_feat_max = _collect_maxes(all_rows)
            non_anom = [
                row for row in all_rows if not _payload_flag_anomalous(row)
            ]
            sample: list[dict[str, Any]] = []
            if non_anom:
                limit_n = min(
                    len(non_anom),
                    max(1, int(len(non_anom) * NORMAL_SAMPLE_FRACTION)),
                )
                sample = random.sample(non_anom, limit_n)

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
