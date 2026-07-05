import logging
from typing import Any, Literal

from fastapi import HTTPException, UploadFile

from app.libs.document_permissions import can_download, can_upload, can_view
from app.libs.document_validation import (
    DocumentType,
    DocumentValidationError,
    validate_content_type,
    validate_file_size,
    validate_magic_bytes,
)
from app.repositories.user import UserRepository
from app.repositories.user_documents import UserDocumentsRepository
from app.schemas.user_documents import (
    DocumentMetadataItem,
    UploadDocumentResponse,
    UserDocumentsMetadataResponse,
)

logger = logging.getLogger(__name__)

_DOCUMENTS_BASE = "/api/v1/users/documents"


class UserDocumentsService:
    """BFF service: RBAC in UPS, GCS work delegated to db-service."""

    def __init__(
        self,
        repository: UserDocumentsRepository,
        user_repository: UserRepository,
    ) -> None:
        self.repository = repository
        self.user_repository = user_repository

    async def _get_permissions(self, role: str) -> dict[str, Any]:
        return await self.user_repository.get_role_permissions(role)

    async def _resolve_target_user(self, target_user_id: str):
        return await self.user_repository.get_user_by_id(target_user_id)

    def _view_url(self, owner_id: str, document_type: str) -> str:
        return f"{_DOCUMENTS_BASE}/{owner_id}/{document_type}/view"

    def _download_url(self, owner_id: str, document_type: str) -> str:
        return f"{_DOCUMENTS_BASE}/{owner_id}/{document_type}/download"

    async def upload(
        self,
        requester: dict[str, Any],
        file: UploadFile,
        document_type: str,
    ) -> UploadDocumentResponse:
        if not can_upload(requester):
            raise HTTPException(
                status_code=403, detail="Not allowed to upload"
            )

        if not requester.get("estate_id"):
            raise HTTPException(
                status_code=403,
                detail="An estate scope is required to upload documents",
            )

        try:
            doc_type = DocumentType(document_type)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Invalid document_type"
            ) from e

        content = await file.read()
        try:
            content_type = validate_content_type(doc_type, file.content_type)
            validate_file_size(doc_type, len(content))
            validate_magic_bytes(content_type, content)
        except DocumentValidationError as e:
            status_code = 413 if "maximum size" in str(e).lower() else 400
            raise HTTPException(status_code=status_code, detail=str(e)) from e

        result = await self.repository.upload(
            file_bytes=content,
            filename=file.filename,
            content_type=content_type,
            user_id=str(requester["id"]),
            estate_id=str(requester["estate_id"]),
            document_type=doc_type.value,
        )

        return UploadDocumentResponse(
            document_type=DocumentType(result["document_type"]),
            content_type=result["content_type"],
            file_size_bytes=result["file_size_bytes"],
            view_url=self._view_url(str(requester["id"]), doc_type.value),
        )

    async def get_metadata(
        self,
        requester: dict[str, Any],
        target_user_id: str,
    ) -> UserDocumentsMetadataResponse:
        target_user = await self._resolve_target_user(target_user_id)
        permissions = await self._get_permissions(requester["role"])

        if not can_view(requester, target_user, permissions):
            raise HTTPException(status_code=403, detail="Not allowed to view")

        search_result = await self.repository.search_by_user(target_user_id)
        documents: list[DocumentMetadataItem] = []
        for item in search_result.get("items", []):
            doc_type = item["document_type"]
            owner_id = str(item["user_id"])
            entry = DocumentMetadataItem(
                document_type=DocumentType(doc_type),
                content_type=item["content_type"],
                view_url=self._view_url(owner_id, doc_type),
            )
            if can_download(requester, target_user, permissions):
                entry.download_url = self._download_url(owner_id, doc_type)
            documents.append(entry)

        return UserDocumentsMetadataResponse(documents=documents)

    async def stream_document(
        self,
        requester: dict[str, Any],
        target_user_id: str,
        document_type: str,
        *,
        disposition: Literal["inline", "attachment"],
    ) -> dict[str, Any]:
        target_user = await self._resolve_target_user(target_user_id)
        permissions = await self._get_permissions(requester["role"])

        if disposition == "inline":
            if not can_view(requester, target_user, permissions):
                raise HTTPException(
                    status_code=403, detail="Not allowed to view"
                )
        elif not can_download(requester, target_user, permissions):
            raise HTTPException(
                status_code=403, detail="Not allowed to download"
            )

        stream = await self.repository.stream_from_db_service(
            target_user_id, document_type
        )
        db_resp = stream.response
        filename = f"{document_type}.jpg"
        content_disposition = db_resp.headers.get("content-disposition", "")
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=", 1)[-1].strip('"')

        async def pipe():
            try:
                async for chunk in db_resp.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk
            finally:
                await stream.close()

        return {
            "media_type": db_resp.headers.get(
                "content-type", "application/octet-stream"
            ),
            "filename": filename,
            "body": pipe(),
        }

    async def delete_all_for_user(self, user_id: str) -> None:
        await self.repository.delete_all_for_user(user_id)
