"""Service layer for user document metadata and GCS operations."""

import logging
from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from gatepass_docs import requires_admin_approval  # pyright: ignore[reportMissingImports]
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
    ApproveResponse,
    CreateRequest,
    CreateResponse,
    DeleteAllForUserResponse,
    DeleteResponse,
    DocumentStatus,
    DocumentType,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
    UploadResponse,
    default_document_status,
)

logger = logging.getLogger(__name__)


class UserDocumentsService:
    """Service for user document metadata and GCS operations."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize with an async DB session."""
        self.repository = Repository(db_session)

    async def create(self, request: CreateRequest) -> CreateResponse:
        """Persist a new user document metadata row."""
        return await self.repository.create(request=request)

    async def delete(self, id: str) -> DeleteResponse:
        """Soft-delete a user document metadata row by ID."""
        return await self.repository.delete(id=id)

    async def get(self, id: str) -> GetResponse:
        """Fetch a user document metadata row by ID."""
        return await self.repository.get(id=id)

    async def update(self, id: str, request: UpdateRequest) -> UpdateResponse:
        """Update fields on an existing user document metadata row."""
        return await self.repository.update(id=id, request=request)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        """List active user document metadata rows with pagination."""
        return await self.repository.list(page=page, limit=limit)

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        """Search active user document metadata rows with filters."""
        return await self.repository.search(
            request=request, page=page, limit=limit
        )

    async def get_by_user_and_type(
        self, user_id: UUID4, document_type: DocumentType
    ) -> GetResponse | None:
        """Return the active document for a user and type, if any."""
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
        uploader_role: str,
        file: UploadFile,
    ) -> UploadResponse:
        """
        Validate upload, write to GCS (temp or main), and persist metadata.

        ID card uploads from residents/security/guests are staged as pending in
        the temp folder. Other uploads are activated immediately.
        """
        content = await file.read()
        content_type = validate_content_type(document_type, file.content_type)
        validate_file_size(document_type, len(content))
        validate_magic_bytes(content_type, content)

        pending = requires_admin_approval(document_type, uploader_role)
        document_status = (
            DocumentStatus.PENDING
            if pending
            else default_document_status(document_type)
        )

        if pending:
            prior_pending = (
                await self.repository.soft_delete_pending_by_user_and_type(
                    user_id=user_id, document_type=document_type
                )
            )
            if prior_pending:
                try:
                    await gcs_storage.delete_object(
                        prior_pending.gcs_object_path
                    )
                except Exception:
                    logger.exception(
                        "Failed to delete superseded pending GCS object: %s",
                        prior_pending.gcs_object_path,
                    )
        else:
            await self.repository.archive_active_by_user_and_type(
                user_id=user_id, document_type=document_type
            )

        document_id = str(uuid4())
        object_path = build_object_path(
            estate_id=str(estate_id),
            user_id=str(user_id),
            document_type=document_type,
            document_id=document_id,
            content_type=content_type,
            pending=pending,
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
                document_status=document_status,
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

        if not pending:
            signed_url_cache.invalidate(str(user_id), document_type.value)

        return UploadResponse(
            document_type=document_type,
            content_type=content_type,
            file_size_bytes=len(content),
            gcs_object_path=object_path,
            id=record.id,
            document_status=document_status,
        )

    async def approve(self, document_id: UUID4) -> ApproveResponse:
        """
        Promote a pending document from temp storage to the main folder.

        Archives any previously active document of the same type for the user.
        """
        pending = await self.repository.get_by_id(
            document_id, document_status=DocumentStatus.PENDING
        )

        main_path = build_object_path(
            estate_id=str(pending.estate_id),
            user_id=str(pending.user_id),
            document_type=pending.document_type,
            document_id=str(pending.id),
            content_type=pending.content_type,
            pending=False,
        )
        original_temp_path = pending.gcs_object_path

        await gcs_storage.move_object(original_temp_path, main_path)

        archived = await self.repository.archive_active_by_user_and_type(
            user_id=pending.user_id,
            document_type=pending.document_type,
        )

        try:
            active = await self.repository.promote_pending_to_active(
                document_id,
                gcs_object_path=main_path,
            )
        except Exception:
            if archived is not None:
                try:
                    await self.repository.restore_archived_to_active(
                        archived.id
                    )
                except Exception:
                    logger.exception(
                        "Failed to restore archived document %s after "
                        "promote failure",
                        archived.id,
                    )
            try:
                await gcs_storage.move_object(main_path, original_temp_path)
            except Exception:
                logger.exception(
                    "Failed to roll back GCS object to temp path: %s",
                    original_temp_path,
                )
            raise

        signed_url_cache.invalidate(
            str(pending.user_id), pending.document_type.value
        )

        return ApproveResponse(
            id=active.id,
            document_type=active.document_type,
            document_status=DocumentStatus.ACTIVE,
            gcs_object_path=main_path,
            archived_document_id=archived.id if archived else None,
        )

    async def delete_all_for_user(
        self, user_id: UUID4
    ) -> DeleteAllForUserResponse:
        """Soft-delete all active rows and remove all GCS objects for a user."""
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
        """Return active document metadata and an internal signed GCS URL."""
        doc = await self.get_by_user_and_type(user_id, document_type)
        if not doc:
            raise NotFoundError("Document not found")
        signed_url = signed_url_cache.get_or_sign(
            str(user_id),
            document_type.value,
            doc.gcs_object_path,
        )
        return doc, signed_url

    async def stream_document_by_id(
        self, document_id: UUID4
    ) -> tuple[GetResponse, str]:
        """Return document metadata and a signed URL for a specific row."""
        doc = await self.repository.get_by_id(document_id)
        if doc.document_status not in (
            DocumentStatus.ACTIVE,
            DocumentStatus.PENDING,
        ):
            raise NotFoundError("Document not found")
        signed_url = signed_url_cache.get_or_sign(
            str(doc.user_id),
            f"{doc.document_type.value}:{doc.id}",
            doc.gcs_object_path,
        )
        return doc, signed_url
