import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import Select, func, select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError, ValidationError
from app.models import AccessCode as AccessCodeModel
from app.models import ResidentLog as TableModel
from app.schemas.code_service.resident_log import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)

logger = logging.getLogger(__name__)


class ResidentLogRepository:
    """
    Repository to operate on resident log table.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initializes the repository with the provided session.

        Arguments:
            session: The database session.
        """
        self.session: AsyncSession = session

    async def _getitem(
        self,
        session: AsyncSession,
        **kwargs,
    ) -> TableModel:
        """
        Get an item from the table by its ID.

        Arguments:
            session: The database session.
            id: The ID of the item to retrieve.

        Returns:
            Returns an instance of orm_model if the requested item is found.

        Raises:
            NotFoundError: If the requested item is not found.
            DatabaseError: If there's an error during the database operation.
        """
        id = kwargs.get("id", None)
        query = select(TableModel).where(
            TableModel.is_deleted == False,  # noqa E712
        )
        if isinstance(id, UUID):
            query = query.where(TableModel.id == id)
        else:
            message = "Please specify a valid ID %s" % id
            logger.exception(message)
            raise DatabaseError(message)

        try:
            result = await session.execute(query)
            return result.unique().scalar_one()
        except NoResultFound as e:
            if id is not None:
                message = "Record with ID %s not found" % id
                logger.exception(message)
                raise NotFoundError(message) from e
            else:
                raise NotFoundError
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
        """
        Create a new record in the database.

        Args:
            session (AsyncSession): The database session.
            request (TableModel): The record to be created in the database.

        Returns:
            TableModel: Returns an instance of orm_model containing the
            created record.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
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
        """
        Lists all items from the database.

        Arguments:
            query: The query to execute to retrieve the records.
            order_by: The order_by fields to sort the records.
            page: The page number to retrieve.
            limit: The max number of items per page.

        Returns:
            A list of items encapsulated in GetResponse models.

        Raises:
            DatabaseError: If there's an error during the database operation.
            ValidationError: If the query or order_by parameters are invalid
        """
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
                    GetResponse.model_validate(record) for record in records
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
        """
        Create a new item in the table.

        Arguments:
            request: The request body for creating a new item in the table.

        Returns:
            The CreateResponse object after creating the item in the table.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
        try:
            record = await self._setitem(
                session=self.session,
                request=TableModel(**request.model_dump(exclude_unset=True)),
            )
            created_record = CreateResponse.model_validate(record.__dict__)
            return created_record
        except DatabaseError as e:
            message = "Database error in creating the resident log"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def delete(self, id: UUID4) -> DeleteResponse:
        """
        Soft Deletes an item from the table.

        Arguments:
            id: The ID of the item to delete.
        Returns:
            The DeleteResponse object after deleting the item from the table.

        Raises:
            DatabaseError: If there's an error during the database operation.
            NotFoundError: If the item with the provided ID is not found.
        """
        try:
            record = await self._getitem(session=self.session, id=id)
            record.is_deleted = True
            record.deleted_at = datetime.now(tz=timezone.utc)
            await self.session.flush()
            return DeleteResponse.model_validate(record)
        except NoResultFound as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in deleting a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, id: UUID4) -> GetResponse:
        """
        Get an item by ID.

        Arguments:
            id: The ID of the item to retrieve.

        Returns:
            A GetResponse object after retrieving the item by id.

        Raises:
            DatabaseError: If there's an error during the database operation.
            NotFoundError: If the item with the provided ID is not found.
        """
        try:
            record = await self._getitem(session=self.session, id=id)
            return GetResponse.model_validate(record, from_attributes=True)
        except NotFoundError as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in getting a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def update(
        self, id: UUID4, request: UpdateRequest
    ) -> UpdateResponse:
        """
        Update an existing item with matching id.

        Arguments:
            id: The ID of the item to update.
            request: The request body for updating a item matching the id.

        Returns:
            An UpdateResponse object after updating the item in the table.

        Raises:
            NotFoundError: If the item with the provided ID is not found.
            DatabaseError: If there's an error during the database operation.
        """
        try:
            record = await self._getitem(session=self.session, id=id)
            record.update(**request.model_dump(exclude_unset=True))
            record = await self._setitem(session=self.session, request=record)
            return UpdateResponse.model_validate(record)
        except NotFoundError as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in updating a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        """
        List all items from the database that are not archived.
        The list is sorted by the created_at field in descending order.

        Arguments:
            page: The page number to retrieve.
            limit: The max number of items per page.

        Returns:
            A ListResponse object containing the list of items which are not
            archived.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
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
        self,
        request: SearchRequest,
        page: int = 1,
        limit: int = 20,
        unique: bool = False,
        ascending: bool = False,
    ) -> ListResponse:
        """
        Filter resident-log rows and return a paginated list.

        ``unique`` collapses to one row per ``hashed_code`` (first-level BFF
        history) and attaches ``usage_count``. ``ascending`` defaults to
        descending (latest first).
        """
        query = select(TableModel).where(
            TableModel.is_deleted == False  # noqa E712
        )

        for key, info in request.model_fields.items():
            if getattr(request, key) is None:
                continue
            if key in ["from_date", "to_date"]:
                query = (
                    query.where(TableModel.created_at >= request.from_date)
                    if key == "from_date"
                    else query.where(TableModel.created_at <= request.to_date)
                )
            elif hasattr(TableModel, key):
                field_value = getattr(request, key)
                column = getattr(TableModel, key)

                if isinstance(field_value, str):
                    query = query.where(
                        func.lower(column) == field_value.lower()
                    )
                elif hasattr(field_value, "year"):
                    # Handle date filtering for datetime columns
                    query = query.where(func.date(column) == field_value)
                else:
                    query = query.where(column == field_value)

        try:
            if unique:
                return await self._search_unique(
                    query=query,
                    ascending=ascending,
                    page=page,
                    limit=limit,
                )
            order_by = (
                (TableModel.created_at.asc(),)
                if ascending
                else (TableModel.created_at.desc(),)
            )
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

    async def _search_unique(
        self,
        query: Select,
        ascending: bool = False,
        page: int = 1,
        limit: int = 20,
    ) -> ListResponse:
        """
        Collapse a filtered query to one entry per unique ``hashed_code``.

        Keeps the most recent row per code, attaches ``usage_count`` (total
        validations per code within the filtered set), and left-joins the
        earliest ``accesscode`` row per hash (including soft-deleted) for
        ``code_deleted``, then paginates by ``created_at``.
        """
        filtered = query.subquery("filtered")
        row_num = (
            func.row_number()
            .over(
                partition_by=filtered.c.hashed_code,
                order_by=filtered.c.created_at.desc(),
            )
            .label("rn")
        )
        usage_count = (
            func.count()
            .over(partition_by=filtered.c.hashed_code)
            .label("usage_count")
        )
        ranked = (
            select(filtered, row_num, usage_count)
            .select_from(filtered)
            .subquery("ranked")
        )
        access_base = select(AccessCodeModel).subquery("access_base")
        access_row_num = (
            func.row_number()
            .over(
                partition_by=access_base.c.hashed_code,
                order_by=access_base.c.created_at.asc(),
            )
            .label("ac_rn")
        )
        access_ranked = (
            select(access_base, access_row_num)
            .select_from(access_base)
            .subquery("access_ranked")
        )
        access_earliest = (
            select(
                access_ranked.c.hashed_code,
                access_ranked.c.is_deleted,
            )
            .where(access_ranked.c.ac_rn == 1)
            .subquery("access_earliest")
        )
        count_query = (
            select(func.count()).select_from(ranked).where(ranked.c.rn == 1)
        )
        order_column = ranked.c.created_at
        records_query = (
            select(
                ranked,
                func.coalesce(access_earliest.c.is_deleted, False).label(
                    "code_deleted"
                ),
            )
            .select_from(ranked)
            .outerjoin(
                access_earliest,
                func.lower(ranked.c.hashed_code)
                == func.lower(access_earliest.c.hashed_code),
            )
            .where(ranked.c.rn == 1)
            .order_by(order_column.asc() if ascending else order_column.desc())
            .limit(limit)
            .offset((page - 1) * limit)
        )
        try:
            total = await self.session.scalar(count_query)
            rows = (await self.session.execute(records_query)).all()
            items = []
            for row in rows:
                mapping = row._mapping
                items.append(
                    GetResponse.model_validate(
                        {
                            "id": mapping["id"],
                            "created_at": mapping["created_at"],
                            "updated_at": mapping["updated_at"],
                            "is_deleted": mapping["is_deleted"],
                            "user_id": mapping["user_id"],
                            "estate_id": mapping["estate_id"],
                            "full_name": mapping["full_name"],
                            "hashed_code": mapping["hashed_code"],
                            "security_id": mapping["security_id"],
                            "access_time": mapping["access_time"],
                            "usage_count": mapping["usage_count"],
                            "code_deleted": mapping["code_deleted"],
                        }
                    )
                )
            return ListResponse(
                items=items,
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            message = "Database error in retrieving unique search results"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in retrieving unique search results"
            logger.exception(message)
            raise DatabaseError(message) from e
