import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import Select, func, select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError, ValidationError
from app.models import AccessCode as TableModel
from app.models import ResidentLog as ResidentLogModel
from app.models import Users as UsersModel
from app.schemas.code_service.access_code import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    HistoryItemResponse,
    HistoryListResponse,
    HistorySearchRequest,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)

logger = logging.getLogger(__name__)


class AccessCodeRepository:
    """
    Repository to operate on workflows.workflows table.
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
            # create the Query object to GET the record with the given ID.
            query = query.where(TableModel.id == id)
        else:
            message = "Please specify a valid ID %s" % id
            logger.exception(message)
            raise DatabaseError(message)

        try:
            # Execute the query and return the result.
            result = await session.execute(query)
            # Get the first record from the result
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
            # Add the record to the session if it doesn't have an ID
            if request.id is None:
                session.add(request)
            # Sends pending changes to the database
            await session.flush()
            # Reloads the given object from the database
            await session.refresh(request)
            # return the record
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
        Lists all items from the database. The total
        number of items displayed can be calculated as:
        total_retrieved = page * limit

        Arguments:
            query: The query to execute to retrieve the records.
            order_by: The order_by fields to sort the records.
            page: The page number to retrieve.
            limit: The max number of items per page.

        Returns:
            A lis of items encapsulated in GetResponse models.

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

        # Create a query to get the total number of records.
        count_query = select(func.count()).select_from(query.subquery())

        # Limit the query to the specified page and page size.
        paginated_query = (
            query.order_by(*order_by)
            .limit(limit)
            .offset((page - 1) * limit)
            .distinct()
        )
        try:
            # Execute the count_query and get the total number of records.
            total = await self.session.scalar(count_query)

            # Get the records from the database.
            records = (
                (await self.session.execute(paginated_query))
                .unique()
                .scalars()
                .all()
            )

            # Convert the records to a List schema model.
            return ListResponse(
                items=[
                    GetResponse.model_validate(record) for record in records
                ],  # convert the records to a list of GET schema models.
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
            # Create the record in the database
            record = await self._setitem(
                session=self.session,
                request=TableModel(
                    **request.model_dump(exclude_unset=True)
                ),  # convert the request to a database model instance.
            )
            # convert the record to a CREATE schema model.
            created_record = CreateResponse.model_validate(record.__dict__)
            # return the created record.
            return created_record
        except DatabaseError as e:
            message = "Database error in creating the prompt template"
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
            # Get the record from the database, then delete it.
            record = await self._getitem(session=self.session, id=id)
            record.is_deleted = True
            record.deleted_at = datetime.now(tz=timezone.utc)
            # Commit the changes to the database.
            await self.session.flush()
            # return the DELETE response.
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
            # Get the record from the database
            record = await self._getitem(session=self.session, id=id)
            # Convert the record to a GET schema model
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
            # Get the record from the database and convert to CREATE schema
            record = await self._getitem(session=self.session, id=id)
            # Update the data fields for the record with the new values.
            record.update(**request.model_dump(exclude_unset=True))
            # update the table with the new record and mark the updated_at
            # timestamp as the current time (done within the database).
            record = await self._setitem(session=self.session, request=record)
            # convert the record to a schema model.
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
        # Create a query to get all records from the database.
        query = select(TableModel).where(
            (
                TableModel.is_deleted == False  # noqa E712
            )
        )
        # Order the records by the created_at timestamp in descending order.
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
        *,
        include_deleted: bool = False,
        ascending: bool = False,
    ) -> ListResponse:
        """
        Filter access-code rows and return a paginated list.

        When ``include_deleted`` is False (the default), soft-deleted rows are
        excluded. ``ascending`` controls ``created_at`` sort direction. The
        code-service BFF uses ``include_deleted=True`` with ``ascending=True``
        and ``hashed_code`` to fetch the genesis row for code-level resident
        history.
        """
        query = select(TableModel)
        if not include_deleted:
            query = query.where(TableModel.is_deleted == False)  # noqa E712

        # Apply filters
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
                    # Normalize both column and input
                    # for case-insensitive matching
                    query = query.where(
                        func.lower(column) == field_value.lower()
                    )
                else:
                    query = query.where(column == field_value)

        order_by = (
            (TableModel.created_at.asc(),)
            if ascending
            else (TableModel.created_at.desc(),)
        )
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

    @staticmethod
    def _apply_history_filters(
        query: Select,
        request: HistorySearchRequest,
    ) -> Select:
        if request.user_id is not None:
            query = query.where(TableModel.user_id == request.user_id)
        if request.estate_id is not None:
            query = query.where(TableModel.estate_id == request.estate_id)
        if request.from_date is not None:
            query = query.where(TableModel.created_at >= request.from_date)
        if request.to_date is not None:
            query = query.where(TableModel.created_at <= request.to_date)
        return query

    async def history_search(
        self,
        request: HistorySearchRequest,
        page: int = 1,
        limit: int = 20,
        *,
        ascending: bool = False,
    ) -> HistoryListResponse:
        """
        First-level resident access-code history in one query.

        Reads ``accesscode`` rows (each row is already unique), joins
        ``users`` for ``full_name``, and left-correlates ``residentlog`` for
        ``usage_count`` plus the latest validation metadata.
        """
        log_match = (
            func.lower(ResidentLogModel.hashed_code)
            == func.lower(TableModel.hashed_code),
            ResidentLogModel.is_deleted == False,  # noqa: E712
        )
        usage_count = (
            select(func.count(ResidentLogModel.id))
            .where(*log_match)
            .correlate(TableModel)
            .scalar_subquery()
        )
        latest_security_id = (
            select(ResidentLogModel.security_id)
            .where(*log_match)
            .order_by(ResidentLogModel.access_time.desc())
            .limit(1)
            .correlate(TableModel)
            .scalar_subquery()
        )
        latest_access_time = (
            select(ResidentLogModel.access_time)
            .where(*log_match)
            .order_by(ResidentLogModel.access_time.desc())
            .limit(1)
            .correlate(TableModel)
            .scalar_subquery()
        )
        full_name = func.trim(
            func.concat(
                func.coalesce(UsersModel.first_name, ""),
                " ",
                func.coalesce(UsersModel.last_name, ""),
            )
        )

        filtered = self._apply_history_filters(
            select(TableModel).join(
                UsersModel, TableModel.user_id == UsersModel.id
            ),
            request,
        )
        count_query = select(func.count()).select_from(filtered.subquery())
        order_column = (
            TableModel.created_at.asc()
            if ascending
            else TableModel.created_at.desc()
        )
        records_query = (
            self._apply_history_filters(
                select(
                    TableModel.id,
                    TableModel.created_at,
                    TableModel.updated_at,
                    TableModel.user_id,
                    TableModel.estate_id,
                    TableModel.hashed_code,
                    TableModel.is_deleted.label("code_deleted"),
                    full_name.label("full_name"),
                    func.coalesce(usage_count, 0).label("usage_count"),
                    func.coalesce(
                        latest_security_id, TableModel.user_id
                    ).label("security_id"),
                    func.coalesce(
                        latest_access_time, TableModel.created_at
                    ).label("access_time"),
                ).join(UsersModel, TableModel.user_id == UsersModel.id),
                request,
            )
            .order_by(order_column)
            .limit(limit)
            .offset((page - 1) * limit)
        )
        try:
            total = await self.session.scalar(count_query)
            rows = (await self.session.execute(records_query)).all()
            items = [
                HistoryItemResponse.model_validate(dict(row._mapping))
                for row in rows
            ]
            return HistoryListResponse(
                items=items,
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            message = "Database error in retrieving access-code history"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in retrieving access-code history"
            logger.exception(message)
            raise DatabaseError(message) from e
