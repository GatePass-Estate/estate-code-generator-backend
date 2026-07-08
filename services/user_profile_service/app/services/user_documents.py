"""BFF service for user documents: RBAC in UPS, storage in db-service."""

import logging
from typing import Any, Literal

import httpx
from fastapi import HTTPException, UploadFile

from app.libs.document_filenames import stream_filename
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
    ApproveDocumentResponse,
    DocumentMetadataItem,
    DocumentStatus,
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
        """Wire HTTP repositories for documents and user lookup."""
        self.repository = repository
        self.user_repository = user_repository

    async def _get_permissions(self, role: str) -> dict[str, Any]:
        """Load RBAC flags for the requester's role."""
        return await self.user_repository.get_role_permissions(role)

    async def _resolve_target_user(self, target_user_id: str):
        """Fetch the target user or raise 404 when missing or deleted."""
        target_user = await self.user_repository.get_user_by_id(target_user_id)
        if target_user is None or target_user.is_deleted:
            raise HTTPException(
                status_code=404, detail="Target User not found"
            )
        return target_user

    def _view_url(self, owner_id: str, document_type: str) -> str:
        """Build the UPS view URL for a document."""
        return f"{_DOCUMENTS_BASE}/{owner_id}/{document_type}/view"

    def _download_url(self, owner_id: str, document_type: str) -> str:
        """Build the UPS download URL for a document."""
        return f"{_DOCUMENTS_BASE}/{owner_id}/{document_type}/download"

    async def upload(
        self,
        requester: dict[str, Any],
        file: UploadFile,
        document_type: str,
    ) -> UploadDocumentResponse:
        """Validate and upload a document for the authenticated user."""
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
            uploader_role=requester["role"],
        )

        document_status = result.get("document_status")
        status_enum = (
            DocumentStatus(document_status) if document_status else None
        )
        document_id = str(result["id"])
        view_url = None
        if status_enum != DocumentStatus.PENDING:
            view_url = self._view_url(str(requester["id"]), doc_type.value)

        return UploadDocumentResponse(
            document_type=DocumentType(result["document_type"]),
            content_type=result["content_type"],
            file_size_bytes=result["file_size_bytes"],
            document_id=document_id,
            document_status=status_enum,
            view_url=view_url,
        )

    async def get_metadata(
        self,
        requester: dict[str, Any],
        target_user_id: str,
    ) -> UserDocumentsMetadataResponse:
        """Return document metadata and URLs when the requester may view."""
        target_user = await self._resolve_target_user(target_user_id)
        permissions = await self._get_permissions(requester["role"])

        if not can_view(requester, target_user, permissions):
            raise HTTPException(status_code=403, detail="Not allowed to view")

        is_owner = str(requester["id"]) == target_user_id
        if is_owner:
            search_result = await self.repository.search_by_user(
                target_user_id
            )
        else:
            search_result = await self.repository.search_by_user(
                target_user_id, document_status="active"
            )

        documents: list[DocumentMetadataItem] = []
        for item in search_result.get("items", []):
            raw_status = item.get("document_status")
            if raw_status == DocumentStatus.ARCHIVED.value:
                continue
            doc_type = item["document_type"]
            owner_id = str(item["user_id"])
            raw_status = item.get("document_status")
            status_enum = (
                DocumentStatus(raw_status) if raw_status is not None else None
            )
            document_id = str(item["id"])
            view_url = None
            download_url = None
            if status_enum != DocumentStatus.PENDING:
                view_url = self._view_url(owner_id, doc_type)
                if can_download(requester, target_user, permissions):
                    download_url = self._download_url(owner_id, doc_type)
            elif is_owner or requester["role"] in (
                "admin",
                "primary_admin",
                "root",
            ):
                view_url = f"{_DOCUMENTS_BASE}/pending/{document_id}/view"

            entry = DocumentMetadataItem(
                document_type=DocumentType(doc_type),
                content_type=item["content_type"],
                document_status=status_enum,
                document_id=document_id,
                view_url=view_url,
                download_url=download_url,
            )
            documents.append(entry)

        return UserDocumentsMetadataResponse(documents=documents)

    async def approve_document(
        self,
        requester: dict[str, Any],
        document_id: str,
    ) -> ApproveDocumentResponse:
        """Approve a pending document after admin review."""
        if requester["role"] not in ("admin", "primary_admin", "root"):
            raise HTTPException(
                status_code=403,
                detail="Only admins can approve documents",
            )

        doc_meta = await self.repository.get_by_id(document_id)
        if doc_meta.get("document_status") != DocumentStatus.PENDING.value:
            raise HTTPException(
                status_code=400,
                detail="Only pending documents can be approved",
            )

        if requester["role"] != "root":
            target_user = await self._resolve_target_user(
                str(doc_meta["user_id"])
            )
            if str(target_user.estate_id) != str(requester.get("estate_id")):
                raise HTTPException(
                    status_code=403,
                    detail="Cannot approve documents from other estates",
                )

        result = await self.repository.approve(document_id)
        archived_id = result.get("archived_document_id")

        return ApproveDocumentResponse(
            document_id=str(result["id"]),
            document_type=DocumentType(result["document_type"]),
            document_status=DocumentStatus(result["document_status"]),
            archived_document_id=(
                str(archived_id) if archived_id is not None else None
            ),
        )

    async def stream_pending_document(
        self,
        requester: dict[str, Any],
        document_id: str,
        *,
        disposition: Literal["inline", "attachment"],
    ) -> dict[str, Any]:
        """Stream a pending document by row ID for owner or admin review."""
        doc_meta = await self.repository.get_by_id(document_id)
        if doc_meta.get("document_status") != DocumentStatus.PENDING.value:
            raise HTTPException(
                status_code=404, detail="Pending document not found"
            )

        owner_id = str(doc_meta["user_id"])
        is_owner = str(requester["id"]) == owner_id
        is_admin = requester["role"] in ("admin", "primary_admin", "root")

        if not is_owner and not is_admin:
            raise HTTPException(status_code=403, detail="Not allowed to view")

        if is_admin and not is_owner and requester["role"] != "root":
            target_user = await self._resolve_target_user(owner_id)
            if str(target_user.estate_id) != str(requester.get("estate_id")):
                raise HTTPException(
                    status_code=403, detail="Not allowed to view"
                )

        url = f"{self.repository.endpoint}/by-id/{document_id}/stream"
        http_client = httpx.AsyncClient(timeout=60.0)
        try:
            response = await http_client.send(
                http_client.build_request("GET", url),
                stream=True,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            await http_client.aclose()
            detail = e.response.text
            try:
                detail = e.response.json().get("detail", detail)
            except ValueError:
                pass
            raise HTTPException(
                status_code=e.response.status_code,
                detail=detail,
            ) from e
        except httpx.RequestError as e:
            await http_client.aclose()
            logger.exception("Pending stream request failed")
            raise HTTPException(
                status_code=503,
                detail="Document service unavailable",
            ) from e

        filename = stream_filename(
            content_type=response.headers.get(
                "content-type", "application/octet-stream"
            ),
        )

        async def pipe():
            try:
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk
            finally:
                await response.aclose()
                await http_client.aclose()

        return {
            "media_type": response.headers.get(
                "content-type", "application/octet-stream"
            ),
            "filename": filename,
            "body": pipe(),
        }

    async def stream_document(
        self,
        requester: dict[str, Any],
        target_user_id: str,
        document_type: str,
        *,
        disposition: Literal["inline", "attachment"],
    ) -> dict[str, Any]:
        """Stream a document from db-service after RBAC and metadata checks."""
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

        doc_meta = await self.repository.get_active_by_user_and_type(
            target_user_id, document_type
        )
        if not doc_meta:
            raise HTTPException(status_code=404, detail="Document not found")

        stream = await self.repository.stream_from_db_service(
            target_user_id, document_type
        )
        db_resp = stream.response
        filename = stream_filename(
            content_type=doc_meta.get("content_type")
            or db_resp.headers.get("content-type", "application/octet-stream"),
            original_filename=doc_meta.get("original_filename"),
        )

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
        """Delete all documents for a user (account closure hook)."""
        await self.repository.delete_all_for_user(user_id)
