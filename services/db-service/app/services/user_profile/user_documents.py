import logging
from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.libs import gcs_storage, signed_url_cache
from app.libs.document_validation import (
    build_object_path,
    validate_content_type,
    validate_file_size,
    validate_magic_bytes,
)
from app.repositories.user_profile.user_documents import (
    UserDocumentsRepository as Repository,
)
from app.schemas.user_profile.user_documents import (
    CreateRequest,
    CreateResponse,
    DeleteAllForUserResponse,
    DeleteResponse,
    DocumentType,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
    UploadResponse,
)

logger = logging.getLogger(__name__)


class UserDocumentsService:
    """Service for user document metadata and GCS operations."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        return await self.repository.create(request=request)

    async def delete(self, id: str) -> DeleteResponse:
        return await self.repository.delete(id=id)

    async def get(self, id: str) -> GetResponse:
        return await self.repository.get(id=id)

    async def update(self, id: str, request: UpdateRequest) -> UpdateResponse:
        return await self.repository.update(id=id, request=request)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        return await self.repository.list(page=page, limit=limit)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        return await self.repository.search(
            request=request, page=page, limit=limit
        )

    async def get_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        return await self.repository.get_active_by_user_and_type(
            user_id=user_id, document_type=document_type
        )

    async def upload(
        self,
        *,
        user_id: UUID4,
        estate_id: UUID4,
        document_type: DocumentType,
        uploaded_by: UUID4,
        file: UploadFile,
    ) -> UploadResponse:
        content = await file.read()
        content_type = validate_content_type(document_type, file.content_type)
        validate_file_size(document_type, len(content))
        validate_magic_bytes(content_type, content)

        await self.repository.soft_delete_active_by_user_and_type(
            user_id=user_id, document_type=document_type
        )

        document_id = str(uuid4())
        object_path = build_object_path(
            estate_id=str(estate_id),
            user_id=str(user_id),
            document_type=document_type,
            document_id=document_id,
            content_type=content_type,
        )

        await gcs_storage.upload_object(
            object_path,
            BytesIO(content),
            content_type,
        )

        try:
            record = await self.repository.create_upload_record(
                user_id=user_id,
                estate_id=estate_id,
                document_type=document_type,
                gcs_object_path=object_path,
                content_type=content_type,
                file_size_bytes=len(content),
                original_filename=file.filename,
                uploaded_by=uploaded_by,
            )
        except Exception:
            try:
                await gcs_storage.delete_object(object_path)
            except Exception:
                logger.exception(
                    "Failed to roll back GCS object after DB error: %s",
                    object_path,
                )
            raise

        signed_url_cache.invalidate(str(user_id), document_type.value)

        return UploadResponse(
            document_type=document_type,
            content_type=content_type,
            file_size_bytes=len(content),
            gcs_object_path=object_path,
            id=record.id,
        )

    async def delete_all_for_user(
        self, user_id: UUID4
    ) -> DeleteAllForUserResponse:
        paths = await self.repository.list_gcs_paths_by_user_id(user_id)
        deleted_rows = await self.repository.soft_delete_all_active_for_user(
            user_id
        )

        gcs_deleted = 0
        for path in paths:
            try:
                await gcs_storage.delete_object(path)
                gcs_deleted += 1
            except Exception:
                logger.exception("Failed to delete GCS object %s", path)

        signed_url_cache.invalidate(str(user_id))

        return DeleteAllForUserResponse(
            deleted_count=len(deleted_rows),
            gcs_objects_deleted=gcs_deleted,
        )

    async def stream_document(
        self, user_id: UUID4, document_type: DocumentType
    ) -> tuple[GetResponse, str]:
        doc = await self.get_by_user_and_type(user_id, document_type)
        if not doc:
            raise NotFoundError("Document not found")
        signed_url = signed_url_cache.get_or_sign(
            str(user_id),
            document_type.value,
            doc.gcs_object_path,
        )
        return doc, signed_url
