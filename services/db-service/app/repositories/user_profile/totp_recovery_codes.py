import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import Select, func, select, cast, String
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError, ValidationError
from app.models import TotpRecoveryCodes as TableModel
from app.schemas.user_profile.totp_recovery_codes import (
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


class TotpRecoveryCodesRepository:
    """
    Repository to operate on totp_recovery_codes table.
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
            message = "Database error in creating the totp recovery code"
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
            # Get the record from the database
            record = await self._getitem(session=self.session, id=id)
            # Update the data fields for the record with the new values.
            record.update(**request.model_dump(exclude_none=True))
            # update the table with the new record and mark the updated_at
            # timestamp as the current time (done within the database).
            await self._setitem(session=self.session, request=record)
            # convert the record to a schema model.
            return UpdateResponse.model_validate(record.__dict__)
        except NotFoundError as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in updating a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        """
        Filters items based on the provided search criteria and returns
        a list of them meeting the criteria.

        Arguments:
            request: The request body for searching items.
            page: The page number to retrieve.
            limit: The max number of items per page.

        Returns:
            A ListResponse object containing all the items found from the table
            which match the requested criteria.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
        # Create a query to get all records from the database.
        query = select(TableModel).where(
            TableModel.is_deleted == False  # noqa E712
        )

        # Handle is_used filter explicitly before the generic loop
        if request.is_used is not None:
            if request.is_used:
                query = query.where(TableModel.used_at != None)  # noqa E711
            else:
                query = query.where(TableModel.used_at == None)  # noqa E711

        # Apply filters
        for key, info in request.model_fields.items():
            if getattr(request, key) is None:
                continue
            if key in ["from_date", "to_date", "is_used"]:
                if key == "from_date":
                    query = query.where(
                        TableModel.created_at >= request.from_date
                    )
                elif key == "to_date":
                    query = query.where(
                        TableModel.created_at <= request.to_date
                    )
            elif hasattr(TableModel, key):
                field_value = getattr(request, key)
                column = getattr(TableModel, key)

                # Extract enum value if it's an enum
                if hasattr(field_value, "value"):
                    field_value = field_value.value

                if isinstance(field_value, str):
                    # Normalize both column and input
                    # for case-insensitive matching
                    # Cast column to text for enum types before applying lower
                    query = query.where(
                        func.lower(cast(column, String)) == field_value.lower()
                    )
                else:
                    query = query.where(column == field_value)

        # Order the records by the created_at timestamp in descending order.
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

    async def delete_all_for_user(self, user_id: UUID4) -> None:
        """
        Soft-deletes all non-deleted recovery codes for a given user.

        Arguments:
            user_id: The ID of the user whose recovery codes should be deleted.

        Raises:
            DatabaseError: If there's an error during the database operation.
        """
        try:
            query = select(TableModel).where(
                TableModel.is_deleted == False,  # noqa E712
                TableModel.user_id == user_id,
            )
            result = await self.session.execute(query)
            records = result.unique().scalars().all()

            now = datetime.now(tz=timezone.utc)
            for record in records:
                record.is_deleted = True
                record.deleted_at = now

            await self.session.flush()
        except SQLAlchemyError as e:
            message = (
                "Database error in deleting all recovery codes for user %s"
                % user_id
            )
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = (
                "Unexpected error in deleting all recovery codes for user %s"
                % user_id
            )
            logger.exception(message)
            raise DatabaseError(message) from e
