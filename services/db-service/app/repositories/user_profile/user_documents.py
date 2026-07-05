import logging
from datetime import datetime, timezone
from typing import List
from uuid import UUID, uuid4

from pydantic import UUID4
from sqlalchemy import Select, func, select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError, ValidationError
from app.models import UserDocuments as TableModel
from app.schemas.user_profile.user_documents import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
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
        try:
            if request.id is None:
                session.add(request)
            await session.flush()
            await session.refresh(request)
            return request
        except SQLAlchemyError as e:
            raise DatabaseError(
                "Database error in creating/updating a record"
            ) from e

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
        record = await self._setitem(
            session=self.session,
            request=TableModel(**request.model_dump(exclude_unset=True)),
        )
        return CreateResponse.model_validate(record)

    async def delete(self, id: UUID4) -> DeleteResponse:
        record = await self._getitem(session=self.session, id=id)
        record.is_deleted = True
        record.deleted_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        return DeleteResponse.model_validate(record)

    async def get(self, id: UUID4) -> GetResponse:
        record = await self._getitem(session=self.session, id=id)
        return GetResponse.model_validate(record, from_attributes=True)

    async def update(
        self, id: UUID4, request: UpdateRequest
    ) -> UpdateResponse:
        record = await self._getitem(session=self.session, id=id)
        record.update(**request.model_dump(exclude_unset=True))
        record = await self._setitem(session=self.session, request=record)
        return UpdateResponse.model_validate(record)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
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
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_type == document_type,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return GetResponse.model_validate(record, from_attributes=True)

    async def soft_delete_active_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.document_type == document_type,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.is_deleted = True
        record.deleted_at = datetime.now(tz=timezone.utc)
        await self.session.flush()
        return GetResponse.model_validate(record, from_attributes=True)

    async def list_active_by_user_id(
        self, user_id: UUID4
    ) -> List[GetResponse]:
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        records = result.scalars().all()
        return [
            GetResponse.model_validate(record, from_attributes=True)
            for record in records
        ]

    async def list_gcs_paths_by_user_id(self, user_id: UUID4) -> List[str]:
        query = select(TableModel.gcs_object_path).where(
            TableModel.user_id == user_id
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def soft_delete_all_active_for_user(
        self, user_id: UUID4
    ) -> List[GetResponse]:
        query = select(TableModel).where(
            TableModel.user_id == user_id,
            TableModel.is_deleted == False,  # noqa: E712
        )
        result = await self.session.execute(query)
        records = result.scalars().all()
        now = datetime.now(tz=timezone.utc)
        deleted: list[GetResponse] = []
        for record in records:
            record.is_deleted = True
            record.deleted_at = now
            deleted.append(
                GetResponse.model_validate(record, from_attributes=True)
            )
        if records:
            await self.session.flush()
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
    ) -> GetResponse:
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
            ),
        )
        return GetResponse.model_validate(record, from_attributes=True)
