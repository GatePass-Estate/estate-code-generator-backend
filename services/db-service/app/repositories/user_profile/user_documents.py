"""Repository for core.user_documents table access."""

import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4

from pydantic import UUID4
from sqlalchemy import Select, func, select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import object_session

from app.core.exceptions import DatabaseError, NotFoundError, ValidationError
from app.models import UserDocuments as TableModel
from app.schemas.user_profile.user_documents import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    DocumentStatus,
    DocumentType,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)

logger = logging.getLogger(__name__)


class UserDocumentsRepository:
    """Repository for core.user_documents."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to an async SQLAlchemy session."""
        self.session = session

    async def _getitem(self, session: AsyncSession, **kwargs) -> TableModel:
        id = kwargs.get("id")
        query = select(TableModel).where(TableModel.is_deleted == False)  # noqa: E712
        if isinstance(id, UUID):
            query = query.where(TableModel.id == id)
        else:
            raise DatabaseError("Please specify a valid ID %s" % id)
        try:
            result = await session.execute(query)
            return result.unique().scalar_one()
        except NoResultFound as e:
            raise NotFoundError("Record with ID %s not found" % id) from e
        except SQLAlchemyError as e:
            raise DatabaseError(
                "Database error in retrieving a record with ID %s" % id
            ) from e

    async def _setitem(
        self, session: AsyncSession, request: TableModel
    ) -> TableModel:
        """Persist a row, flush, and refresh so server defaults are loaded."""
        try:
            if object_session(request) is None:
                session.add(request)
            await session.flush()
            await session.refresh(request)
            return request
        except SQLAlchemyError as e:
            raise DatabaseError(
                "Database error in creating/updating a record"
            ) from e

    async def _to_get_response(self, record: TableModel) -> GetResponse:
        """
        Build a GetResponse after a write.

        Refreshes the ORM instance first so async SQLAlchemy can read
        server-managed columns such as updated_at without lazy-load errors.
        """
        await self.session.refresh(record)
        return GetResponse.model_validate(record, from_attributes=True)

    async def _list(
        self,
        query: Select,
        order_by: tuple,
        page: int = 1,
        limit: int = 10,
    ) -> ListResponse:
        if not isinstance(query, Select):
            raise ValidationError("query must be a Select instance")
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
            raise DatabaseError("Database error in retrieving records") from e

    async def create(self, request: CreateRequest) -> CreateResponse:
        """Insert a new user document metadata row."""
        record = await self._setitem(
            session=self.session,
            request=TableModel(**request.model_dump(exclude_unset=True)),
        )
        return CreateResponse.model_validate(record)

    async def delete(self, id: UUID4) -> DeleteResponse:
        """Soft-delete a user document row and return refreshed timestamps."""
        record = await self._getitem(session=self.session, id=id)
        record.is_deleted = True
        record.deleted_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        await self.session.refresh(record)
        return DeleteResponse.model_validate(record)

    async def get(self, id: UUID4) -> GetResponse:
        """Fetch a non-deleted user document row by primary key."""
        record = await self._getitem(session=self.session, id=id)
        return GetResponse.model_validate(record, from_attributes=True)

    async def update(
        self, id: UUID4, request: UpdateRequest
    ) -> UpdateResponse:
        """Update fields on an active user document row."""
        record = await self._getitem(session=self.session, id=id)
        record.update(**request.model_dump(exclude_unset=True))
        record = await self._setitem(session=self.session, request=record)
        return UpdateResponse.model_validate(record)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        """List non-deleted user document rows with pagination."""
        query = select(TableModel).where(TableModel.is_deleted == False)  # noqa: E712
        return await self._list(
            query=query,
            order_by=(TableModel.created_at.desc(),),
            page=page,
            limit=limit,
        )

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        """
        Search non-deleted user document rows with optional filters.

        ``document_status`` may contain one or more values; multiple values
        are combined with OR (``IN``).
        """
        query = select(TableModel).where(TableModel.is_deleted == False)  # noqa: E712
        for key, _ in request.model_fields.items():
            if getattr(request, key) is None:
                continue
            if key in ("from_date", "to_date", "page", "limit"):
                if key == "from_date":
                    query = query.where(
                        TableModel.created_at >= request.from_date
                    )
                elif key == "to_date":
                    query = query.where(
                        TableModel.created_at <= request.to_date
                    )
            elif key == "document_status":
                statuses = getattr(request, key)
                if not statuses:
                    continue
                if len(statuses) == 1:
                    query = query.where(
                        TableModel.document_status == statuses[0]
                    )
                else:
                    query = query.where(
                        TableModel.document_status.in_(statuses)
                    )
            elif hasattr(TableModel, key):
                query = query.where(
                    getattr(TableModel, key) == getattr(request, key)
                )
        return await self._list(
            query=query,
            order_by=(TableModel.created_at.desc(),),
            page=page,
            limit=limit,
        )

    async def get_active_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        """Return the active document for a user and type, if present."""
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_type == document_type,
            TableModel.document_status == DocumentStatus.ACTIVE,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return GetResponse.model_validate(record, from_attributes=True)

    async def get_pending_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        """Return the pending document for a user and type, if present."""
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_type == document_type,
            TableModel.document_status == DocumentStatus.PENDING,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return GetResponse.model_validate(record, from_attributes=True)

    async def get_by_id(
        self,
        document_id: UUID4,
        *,
        document_status: DocumentStatus | None = None,
    ) -> GetResponse:
        """
        Fetch a non-deleted document row by primary key.

        When ``document_status`` is provided, the row must match that status.
        """
        query = select(TableModel).where(
            TableModel.id == document_id,
            TableModel.is_deleted == False,  # noqa: E712
        )
        if document_status is not None:
            query = query.where(TableModel.document_status == document_status)
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundError("Record with ID %s not found" % document_id)
        return GetResponse.model_validate(record, from_attributes=True)

    async def archive_active_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        """
        Mark the active document as archived for a user and type, if present.

        Returns the updated row with refreshed server timestamps.
        """
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_type == document_type,
            TableModel.document_status == DocumentStatus.ACTIVE,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.document_status = DocumentStatus.ARCHIVED
        await self.session.flush()
        return await self._to_get_response(record)

    async def restore_archived_to_active(
        self, document_id: UUID4
    ) -> GetResponse | None:
        """
        Restore a previously archived document back to active status.

        Returns the updated row with refreshed server timestamps.
        """
        query = select(TableModel).where(
            TableModel.id == document_id,
            TableModel.document_status == DocumentStatus.ARCHIVED,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.document_status = DocumentStatus.ACTIVE
        await self.session.flush()
        return await self._to_get_response(record)

    async def soft_delete_active_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        """
        Soft-delete the active document for a user and type, if present.

        Returns the updated row with refreshed server timestamps.
        """
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_type == document_type,
            TableModel.document_status == DocumentStatus.ACTIVE,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.is_deleted = True
        record.deleted_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        return await self._to_get_response(record)

    async def archive_pending_by_id(
        self, document_id: UUID4
    ) -> GetResponse | None:
        """
        Mark a pending document row as archived by primary key.

        The GCS object is left in place (typically under ``temp/``).
        """
        query = select(TableModel).where(
            TableModel.id == document_id,
            TableModel.document_status == DocumentStatus.PENDING,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.document_status = DocumentStatus.ARCHIVED
        await self.session.flush()
        return await self._to_get_response(record)

    async def archive_pending_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        """
        Mark the pending document as archived for a user and type, if present.

        The GCS object is left in place (typically under ``temp/``).
        """
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_type == document_type,
            TableModel.document_status == DocumentStatus.PENDING,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.document_status = DocumentStatus.ARCHIVED
        await self.session.flush()
        return await self._to_get_response(record)

    async def list_visible_by_user_id(
        self, user_id: UUID4
    ) -> List[GetResponse]:
        """List active and pending document rows for a user."""
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_status.in_(
                (DocumentStatus.ACTIVE, DocumentStatus.PENDING)
            ),
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        records = result.scalars().all()
        return [
            GetResponse.model_validate(record, from_attributes=True)
            for record in records
        ]

    async def list_active_by_user_id(
        self, user_id: UUID4
    ) -> List[GetResponse]:
        """List active document metadata rows for a user."""
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_status == DocumentStatus.ACTIVE,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        records = result.scalars().all()
        return [
            GetResponse.model_validate(record, from_attributes=True)
            for record in records
        ]

    async def list_gcs_paths_by_user_id(self, user_id: UUID4) -> List[str]:
        """Return all GCS object paths ever stored for a user."""
        query = select(TableModel.gcs_object_path).where(
            TableModel.user_id == user_id
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def soft_delete_all_active_for_user(
        self, user_id: UUID4
    ) -> List[GetResponse]:
        """
        Soft-delete every active or pending document row for a user.

        Returns each updated row with refreshed server timestamps.
        """
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_status.in_(
                (DocumentStatus.ACTIVE, DocumentStatus.PENDING)
            ),
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        records = result.scalars().all()
        now = datetime.now(tz=timezone.utc)
        deleted: list[GetResponse] = []
        for record in records:
            record.is_deleted = True
            record.deleted_at = now
        if records:
            await self.session.flush()
            for record in records:
                deleted.append(await self._to_get_response(record))
        return deleted

    async def create_upload_record(
        self,
        *,
        user_id: UUID4,
        estate_id: UUID4,
        document_type: DocumentType,
        gcs_object_path: str,
        content_type: str,
        file_size_bytes: int,
        original_filename: str | None,
        uploaded_by: UUID4,
        document_status: DocumentStatus | None,
    ) -> GetResponse:
        """Insert metadata for a newly uploaded GCS object."""
        record = await self._setitem(
            session=self.session,
            request=TableModel(
                id=uuid4(),
                user_id=user_id,
                estate_id=estate_id,
                document_type=document_type,
                gcs_object_path=gcs_object_path,
                content_type=content_type,
                file_size_bytes=file_size_bytes,
                original_filename=original_filename,
                uploaded_by=uploaded_by,
                document_status=document_status,
            ),
        )
        return GetResponse.model_validate(record, from_attributes=True)

    async def promote_pending_to_active(
        self,
        document_id: UUID4,
        *,
        gcs_object_path: str,
    ) -> GetResponse:
        """
        Promote a pending row to active and set its final GCS object path.

        Returns the updated row with refreshed server timestamps.
        """
        query = select(TableModel).where(
            TableModel.id == document_id,
            TableModel.document_status == DocumentStatus.PENDING,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundError("Pending document %s not found" % document_id)
        record.gcs_object_path = gcs_object_path
        record.document_status = DocumentStatus.ACTIVE
        await self.session.flush()
        return await self._to_get_response(record)
