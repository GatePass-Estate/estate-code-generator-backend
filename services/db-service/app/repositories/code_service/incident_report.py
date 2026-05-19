import logging

from pydantic import UUID4
from sqlalchemy import Select, func, select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError, ValidationError
from app.models import IncidentReport as TableModel
from app.schemas.code_service.incident_report import (
    CreateRequest,
    CreateResponse,
    GetResponse,
    IncidentCategory,
    ListResponse,
    SearchRequest,
)

logger = logging.getLogger(__name__)


class IncidentReportRepository:
    """Persistence for ``core.incidentreport``."""

    def __init__(self, session: AsyncSession) -> None:
        self.session: AsyncSession = session

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
            message = "Database error in retrieving a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in retrieving a record with ID %s" % id
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
            message = "Database error in creating/updating a record"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in creating/updating a record"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def _list(
        self,
        query: Select,
        order_by: tuple,
        page: int = 1,
        limit: int = 10,
    ) -> ListResponse:
        if not isinstance(query, Select):
            raise ValidationError(
                "query must be an instance of sqlalchemy.sql.selectable.Select"
            )
        if not isinstance(order_by, tuple):
            raise ValidationError("order_by must be a tuple")

        count_query = select(func.count()).select_from(query.subquery())

        paginated_query = (
            query.order_by(*order_by)
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

            return ListResponse(
                items=[
                    GetResponse.model_validate(record, from_attributes=True)
                    for record in records
                ],
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            message = "Database error in retrieving records"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in retrieving records"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def create(self, request: CreateRequest) -> CreateResponse:
        try:
            record = await self._setitem(
                session=self.session,
                request=TableModel(**request.model_dump(exclude_unset=True)),
            )
            return CreateResponse(id=record.id, created_at=record.created_at)
        except DatabaseError as e:
            message = "Database error in creating incident report"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, id: UUID4) -> GetResponse:
        try:
            record = await self._getitem(session=self.session, id=id)
            return GetResponse.model_validate(record, from_attributes=True)
        except NotFoundError as e:
            raise NotFoundError(str(e)) from e
        except DatabaseError as e:
            message = "Database error in getting a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        query = select(TableModel).where(
            TableModel.is_deleted == False  # noqa E712
        )
        order_by = (TableModel.created_at.desc(),)
        try:
            return await self._list(
                query=query, order_by=order_by, page=page, limit=limit
            )
        except DatabaseError as e:
            message = "Database error in getting a list of items"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        query = select(TableModel).where(
            TableModel.is_deleted == False  # noqa E712
        )

        for key in request.model_fields:
            if key in ("page", "limit"):
                continue
            val = getattr(request, key)
            if val is None:
                continue
            if key in ("from_date", "to_date"):
                query = (
                    query.where(TableModel.created_at >= request.from_date)
                    if key == "from_date"
                    else query.where(TableModel.created_at <= request.to_date)
                )
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

        order_by = (TableModel.created_at.desc(),)
        try:
            return await self._list(
                query=query,
                order_by=order_by,
                page=page,
                limit=limit,
            )
        except DatabaseError as e:
            message = "Database error in searching for items"
            logger.exception(message)
            raise DatabaseError(message) from e
