"""Incident result-page reads over ``core.incidentreport``."""

from __future__ import annotations

import logging

from sqlalchemy import Select, String, and_, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError
from app.models.user_profile.estates import Estates
from app.models.user_profile.incident_report import (
    IncidentReport as TableModel,
)
from app.models.user_profile.users import Users
from app.schemas.ai_features.incident_resultpage import (
    ListItem,
    ListResponse,
    OverviewRequest,
    OverviewResponse,
    ReporterUserType,
    SearchRequest,
)
from app.schemas.user_profile.users import UserRole

logger = logging.getLogger(__name__)

_EXCLUDED_RESIDENT_ROLES = (
    UserRole.SECURITY.value,
    UserRole.GUEST.value,
    UserRole.ROOT.value,
)


def _role_key():
    """Lowercased ``users.role`` for comparing enum names stored uppercase."""
    return func.lower(cast(Users.role, String))


def _is_resident_reporter():
    """True for every role except security, guest, and root."""
    return and_(
        Users.id.isnot(None),
        ~_role_key().in_(_EXCLUDED_RESIDENT_ROLES),
    )


def _reporter_user_type(role: object) -> ReporterUserType | None:
    """Map a stored user role onto the result-page resident/security bucket."""
    raw = role.value if hasattr(role, "value") else role
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if key == UserRole.SECURITY.value:
        return ReporterUserType.SECURITY
    if key in _EXCLUDED_RESIDENT_ROLES:
        return None
    return ReporterUserType.RESIDENT


def _apply_range(query: Select, column, from_date, to_date) -> Select:
    """Apply inclusive ``from_date`` / ``to_date`` bounds on ``column``."""
    if from_date is not None:
        query = query.where(column >= from_date)
    if to_date is not None:
        query = query.where(column <= to_date)
    return query


class IncidentResultPageRepository:
    """Overview counts and filtered list for the incident result page."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to ``session``."""
        self.session = session

    def _search_query(self, request: SearchRequest) -> Select:
        """Incidents for one estate window, optionally filtered by lists."""
        query = (
            select(TableModel, Users.role.label("reporter_role"))
            .outerjoin(Users, TableModel.reported_by_user_id == Users.id)
            .where(
                TableModel.is_deleted == False,  # noqa: E712
                TableModel.estate_id == request.estate_id,
            )
        )
        query = _apply_range(
            query, TableModel.created_at, request.from_date, request.to_date
        )
        if request.categories:
            query = query.where(
                or_(
                    *[
                        TableModel.category.contains([tag])
                        for tag in request.categories
                    ]
                )
            )
        if request.user_types:
            selected = set(request.user_types)
            clauses = []
            if ReporterUserType.RESIDENT in selected:
                clauses.append(_is_resident_reporter())
            if ReporterUserType.SECURITY in selected:
                clauses.append(_role_key() == UserRole.SECURITY.value)
            if clauses:
                query = query.where(or_(*clauses))
        return query

    async def overview(self, request: OverviewRequest) -> OverviewResponse:
        """Estate identity plus report counts split by reporter bucket."""
        try:
            estate = (
                await self.session.execute(
                    select(Estates).where(
                        Estates.id == request.estate_id,
                        Estates.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            if estate is None:
                raise NotFoundError(f"Estate {request.estate_id} not found")

            base = select(TableModel.id).where(
                TableModel.is_deleted == False,  # noqa: E712
                TableModel.estate_id == request.estate_id,
            )
            base = _apply_range(
                base, TableModel.created_at, request.from_date, request.to_date
            )
            total = int(
                await self.session.scalar(
                    select(func.count()).select_from(base.subquery())
                )
                or 0
            )

            joined = (
                select(TableModel.id)
                .outerjoin(Users, TableModel.reported_by_user_id == Users.id)
                .where(
                    TableModel.is_deleted == False,  # noqa: E712
                    TableModel.estate_id == request.estate_id,
                )
            )
            joined = _apply_range(
                joined,
                TableModel.created_at,
                request.from_date,
                request.to_date,
            )
            resident_q = joined.where(_is_resident_reporter())
            security_q = joined.where(_role_key() == UserRole.SECURITY.value)
            resident_count = int(
                await self.session.scalar(
                    select(func.count()).select_from(resident_q.subquery())
                )
                or 0
            )
            security_count = int(
                await self.session.scalar(
                    select(func.count()).select_from(security_q.subquery())
                )
                or 0
            )
            return OverviewResponse(
                estate_name=estate.name,
                state=estate.state,
                country=estate.country,
                total_reports=total,
                resident_report_count=resident_count,
                security_report_count=security_count,
            )
        except NotFoundError:
            raise
        except SQLAlchemyError as e:
            logger.exception("result page overview incident report")
            raise DatabaseError(
                "Database error in result page overview"
            ) from e

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 10
    ) -> ListResponse:
        """Paginate estate incidents with category and user-type filters."""
        query = self._search_query(request)
        count_query = select(func.count()).select_from(query.subquery())
        paginated = (
            query.order_by(TableModel.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        try:
            total = await self.session.scalar(count_query) or 0
            rows = (await self.session.execute(paginated)).all()
            items: list[ListItem] = []
            for row in rows:
                record = row[0]
                item = ListItem.model_validate(record, from_attributes=True)
                item.reporter_user_type = _reporter_user_type(
                    row._mapping.get("reporter_role")
                )
                items.append(item)
            return ListResponse(
                items=items,
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            logger.exception("result page search incident report")
            raise DatabaseError("Database error in result page search") from e
