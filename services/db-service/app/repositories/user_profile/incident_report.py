import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import UUID4
from sqlalchemy import Select, and_, exists, func, select, update
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError
from app.models.user_profile.admin_incident_report_read import (
    AdminIncidentReportRead as ReadModel,
)
from app.models.user_profile.incident_report import (
    IncidentReport as TableModel,
)
from app.models.user_profile.users import Users
from app.schemas.user_profile.incident_report import (
    CreateRequest,
    CreateResponse,
    GetResponse,
    GetResponseWithReadStatus,
    IncidentCategory,
    ListResponse,
    ListResponseWithReadStatus,
    ReporterDetails,
    SearchRequest,
)

logger = logging.getLogger(__name__)


class IncidentReportRepository:
    """Persistence for ``core.incidentreport`` and
    ``core.admin_incident_report_reads``."""

    def __init__(self, session: AsyncSession) -> None:
        self.session: AsyncSession = session

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    async def _getitem(self, session: AsyncSession, **kwargs) -> TableModel:
        id = kwargs.get("id", None)
        query = select(TableModel).where(
            TableModel.is_deleted == False,  # noqa E712
        )
        if id is None:
            message = "Please specify a valid ID %s" % id
            logger.exception(message)
            raise DatabaseError(message)
        query = query.where(TableModel.id == id)

        try:
            result = await session.execute(query)
            return result.unique().scalar_one()
        except NoResultFound as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except SQLAlchemyError as e:
            message = "Database error retrieving record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error retrieving record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def _setitem(
        self,
        session: AsyncSession,
        request: TableModel,
    ) -> TableModel:
        try:
            if request.id is None:
                session.add(request)
            await session.flush()
            await session.refresh(request)
            return request
        except SQLAlchemyError as e:
            message = "Database error creating/updating a record"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error creating/updating a record"
            logger.exception(message)
            raise DatabaseError(message) from e

    def _is_cleared_subquery(self, admin_id: UUID4):
        """EXISTS subquery: True when admin has cleared this report."""
        return exists(
            select(ReadModel.id).where(
                and_(
                    ReadModel.incident_report_id == TableModel.id,
                    ReadModel.admin_id == admin_id,
                    ReadModel.is_deleted == True,  # noqa E712
                )
            )
        )

    async def _list_with_read_status(
        self,
        query: Select,
        admin_id: UUID4,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponseWithReadStatus:
        """Paginate and annotate each row with per-admin read status."""
        count_query = select(func.count()).select_from(query.subquery())
        paginated_query = (
            query.order_by(TableModel.created_at.desc())
            .limit(limit)
            .offset((page - 1) * limit)
            .distinct()
        )

        try:
            total = await self.session.scalar(count_query)
            records = (
                (await self.session.execute(paginated_query))
                .unique()
                .scalars()
                .all()
            )

            report_ids = [r.id for r in records]
            read_map: dict = {}
            if report_ids:
                read_rows = (
                    (
                        await self.session.execute(
                            select(ReadModel).where(
                                and_(
                                    ReadModel.admin_id == admin_id,
                                    ReadModel.incident_report_id.in_(
                                        report_ids
                                    ),
                                    ~ReadModel.is_deleted,
                                )
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                read_map = {r.incident_report_id: r for r in read_rows}

            items = []
            for record in records:
                read_rec = read_map.get(record.id)
                item = GetResponseWithReadStatus.model_validate(
                    record, from_attributes=True
                )
                item.is_read = read_rec is not None
                item.read_at = read_rec.read_at if read_rec else None
                items.append(item)

            return ListResponseWithReadStatus(
                items=items,
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            message = "Database error retrieving records"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error retrieving records"
            logger.exception(message)
            raise DatabaseError(message) from e

    # -----------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------

    async def create(self, request: CreateRequest) -> CreateResponse:
        try:
            record = await self._setitem(
                session=self.session,
                request=TableModel(**request.model_dump(exclude_unset=True)),
            )
            return CreateResponse(id=record.id, created_at=record.created_at)
        except DatabaseError as e:
            message = "Database error creating incident report"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(
        self, id: UUID4, admin_id: Optional[UUID4] = None
    ) -> GetResponseWithReadStatus:
        """Return a report with reporter details and read status."""
        try:
            record = await self._getitem(session=self.session, id=id)
            item = GetResponseWithReadStatus.model_validate(
                record, from_attributes=True
            )

            if record.reported_by_user_id is not None:
                try:
                    user_row = (
                        await self.session.execute(
                            select(Users).where(
                                Users.id == record.reported_by_user_id
                            )
                        )
                    ).scalar_one_or_none()
                    if user_row:
                        item.reporter = ReporterDetails(
                            first_name=user_row.first_name,
                            last_name=user_row.last_name,
                            email=user_row.email,
                            phone_number=user_row.phone_number,
                            home_address=user_row.home_address,
                        )
                except Exception:
                    logger.exception(
                        "Failed to fetch reporter for incident %s",
                        id,
                    )

            if admin_id is not None:
                read_rec = (
                    await self.session.execute(
                        select(ReadModel).where(
                            and_(
                                ReadModel.admin_id == admin_id,
                                ReadModel.incident_report_id == id,
                                ~ReadModel.is_deleted,
                            )
                        )
                    )
                ).scalar_one_or_none()
                item.is_read = read_rec is not None
                item.read_at = read_rec.read_at if read_rec else None

            return item
        except NotFoundError as e:
            raise NotFoundError(str(e)) from e
        except DatabaseError as e:
            message = "Database error getting incident id=%s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def list(
        self,
        admin_id: UUID4,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponseWithReadStatus:
        """List non-deleted, non-cleared reports with read status."""
        query = select(TableModel).where(
            and_(
                TableModel.is_deleted == False,  # noqa E712
                ~self._is_cleared_subquery(admin_id),
            )
        )
        try:
            return await self._list_with_read_status(
                query=query,
                admin_id=admin_id,
                page=page,
                limit=limit,
            )
        except DatabaseError as e:
            message = "Database error listing incident reports"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def search(
        self,
        request: SearchRequest,
        admin_id: Optional[UUID4] = None,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponseWithReadStatus | ListResponse:
        query = select(TableModel).where(
            TableModel.is_deleted == False  # noqa E712
        )

        if admin_id is not None:
            query = query.where(~self._is_cleared_subquery(admin_id))

        for key in request.model_fields:
            if key in ("page", "limit"):
                continue
            val = getattr(request, key)
            if val is None:
                continue
            if key == "from_date":
                query = query.where(TableModel.created_at >= request.from_date)
            elif key == "to_date":
                query = query.where(TableModel.created_at <= request.to_date)
            elif key == "category":
                tag = (
                    val
                    if isinstance(val, IncidentCategory)
                    else IncidentCategory(str(val).strip().lower())
                )
                query = query.where(TableModel.category.contains([tag]))
            elif hasattr(TableModel, key):
                column = getattr(TableModel, key)
                if isinstance(val, str):
                    query = query.where(func.lower(column) == val.lower())
                else:
                    query = query.where(column == val)

        try:
            if admin_id is not None:
                return await self._list_with_read_status(
                    query=query,
                    admin_id=admin_id,
                    page=page,
                    limit=limit,
                )

            # AI-service path — no read-status enrichment
            count_query = select(func.count()).select_from(query.subquery())
            paginated_query = (
                query.order_by(TableModel.created_at.desc())
                .limit(limit)
                .offset((page - 1) * limit)
                .distinct()
            )
            total = await self.session.scalar(count_query)
            records = (
                (await self.session.execute(paginated_query))
                .unique()
                .scalars()
                .all()
            )
            return ListResponse(
                items=[
                    GetResponse.model_validate(r, from_attributes=True)
                    for r in records
                ],
                total=total,
                page=page,
                limit=limit,
            )
        except DatabaseError as e:
            message = "Database error searching incident reports"
            logger.exception(message)
            raise DatabaseError(message) from e

    # -----------------------------------------------------------------
    # Admin read / clear operations
    # -----------------------------------------------------------------

    async def mark_read(
        self, incident_report_id: UUID4, admin_id: UUID4
    ) -> dict:
        """Upsert a read record; un-clear if previously cleared."""
        try:
            now = datetime.now(tz=timezone.utc)
            existing = (
                await self.session.execute(
                    select(ReadModel).where(
                        and_(
                            ReadModel.admin_id == admin_id,
                            ReadModel.incident_report_id == incident_report_id,
                        )
                    )
                )
            ).scalar_one_or_none()

            if existing is None:
                self.session.add(
                    ReadModel(
                        id=uuid4(),
                        admin_id=admin_id,
                        incident_report_id=incident_report_id,
                        read_at=now,
                        is_deleted=False,
                    )
                )
            else:
                existing.is_deleted = False
                existing.deleted_at = None
                existing.read_at = now

            await self.session.flush()
            return {
                "marked_read": True,
                "incident_report_id": str(incident_report_id),
            }
        except SQLAlchemyError as e:
            message = (
                "Database error marking incident %s read "
                "for admin %s" % (incident_report_id, admin_id)
            )
            logger.exception(message)
            raise DatabaseError(message) from e

    async def mark_all_read(self, admin_id: UUID4, estate_id: UUID4) -> dict:
        """Bulk-upsert read records for all non-cleared reports."""
        try:
            now = datetime.now(tz=timezone.utc)

            unread_ids_query = select(TableModel.id).where(
                and_(
                    TableModel.estate_id == estate_id,
                    TableModel.is_deleted == False,  # noqa E712
                    ~self._is_cleared_subquery(admin_id),
                )
            )
            unread_ids = (
                (await self.session.execute(unread_ids_query)).scalars().all()
            )

            if not unread_ids:
                return {"marked_read": 0}

            existing_rows = (
                (
                    await self.session.execute(
                        select(ReadModel).where(
                            and_(
                                ReadModel.admin_id == admin_id,
                                ReadModel.incident_report_id.in_(unread_ids),
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
            existing_map = {r.incident_report_id: r for r in existing_rows}

            count = 0
            for report_id in unread_ids:
                existing = existing_map.get(report_id)
                if existing is None:
                    self.session.add(
                        ReadModel(
                            id=uuid4(),
                            admin_id=admin_id,
                            incident_report_id=report_id,
                            read_at=now,
                            is_deleted=False,
                        )
                    )
                    count += 1
                elif existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.read_at = now
                    count += 1

            await self.session.flush()
            return {"marked_read": count}
        except SQLAlchemyError as e:
            message = (
                "Database error bulk-marking reports read "
                "for admin %s in estate %s" % (admin_id, estate_id)
            )
            logger.exception(message)
            raise DatabaseError(message) from e

    async def clear_read(self, admin_id: UUID4, estate_id: UUID4) -> dict:
        """Soft-delete all read (non-cleared) records for this admin."""
        try:
            now = datetime.now(tz=timezone.utc)

            estate_report_ids_query = select(TableModel.id).where(
                and_(
                    TableModel.estate_id == estate_id,
                    TableModel.is_deleted == False,  # noqa E712
                )
            )
            estate_report_ids = (
                (await self.session.execute(estate_report_ids_query))
                .scalars()
                .all()
            )

            if not estate_report_ids:
                return {"cleared": 0}

            result = await self.session.execute(
                update(ReadModel)
                .where(
                    and_(
                        ReadModel.admin_id == admin_id,
                        ReadModel.incident_report_id.in_(estate_report_ids),
                        ReadModel.is_deleted == False,  # noqa E712
                    )
                )
                .values(is_deleted=True, deleted_at=now)
            )
            await self.session.flush()
            return {"cleared": result.rowcount}
        except SQLAlchemyError as e:
            message = (
                "Database error clearing read reports "
                "for admin %s in estate %s" % (admin_id, estate_id)
            )
            logger.exception(message)
            raise DatabaseError(message) from e
