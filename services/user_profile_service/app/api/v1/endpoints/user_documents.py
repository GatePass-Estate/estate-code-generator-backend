"""JWT-protected API for user document upload, metadata, and streaming."""

import logging

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.user import UserRepository
from app.repositories.user_documents import UserDocumentsRepository
from app.schemas.user_documents import (
    ApproveDocumentResponse,
    DocumentStatus,
    DocumentType,
    UploadDocumentResponse,
    UserDocumentsMetadataResponse,
)
from app.services.auth import get_current_user
from app.services.user_documents import UserDocumentsService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_documents_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> UserDocumentsService:
    """Return a UserDocumentsService wired to db-service and user repos."""
    return UserDocumentsService(
        repository=UserDocumentsRepository(ahttp_client),
        user_repository=UserRepository(ahttp_client),
    )


@router.post("/upload", response_model=UploadDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
) -> UploadDocumentResponse:
    """Upload a document for the authenticated user."""
    return await service.upload(current_user, file, document_type)


@router.get("/me", response_model=UserDocumentsMetadataResponse)
async def get_my_documents(
    document_type: DocumentType | None = Query(
        default=None,
        description="Filter results to a single document type",
    ),
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
) -> UserDocumentsMetadataResponse:
    """
    Return document metadata for the authenticated user.

    Optionally filter by ``document_type`` (``profile_picture`` or ``id_card``).
    """
    return await service.get_metadata(
        current_user,
        str(current_user["id"]),
        document_type=document_type.value if document_type else None,
    )


@router.get("/me/{document_type}/view")
async def view_my_document(
    document_type: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
):
    """Stream the authenticated user's document inline in the browser."""
    result = await service.stream_document(
        requester=current_user,
        target_user_id=str(current_user["id"]),
        document_type=document_type,
        disposition="inline",
    )
    return StreamingResponse(
        result["body"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": f'inline; filename="{result["filename"]}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/me/{document_type}/download")
async def download_my_document(
    document_type: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
):
    """Download the authenticated user's document as an attachment."""
    result = await service.stream_document(
        requester=current_user,
        target_user_id=str(current_user["id"]),
        document_type=document_type,
        disposition="attachment",
    )
    return StreamingResponse(
        result["body"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": (
                f'attachment; filename="{result["filename"]}"'
            ),
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/pending/{document_id}/approve",
    response_model=ApproveDocumentResponse,
)
async def approve_pending_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
) -> ApproveDocumentResponse:
    """
    Promote a pending document to active after admin approval.

    Moves the file from temp GCS storage and archives any prior active
    document of the same type.
    """
    return await service.approve_document(current_user, document_id)


@router.get("/pending/{document_id}/view")
async def view_pending_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
):
    """Stream a pending document inline for owner or admin review."""
    result = await service.stream_pending_document(
        requester=current_user,
        document_id=document_id,
        disposition="inline",
    )
    return StreamingResponse(
        result["body"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": f'inline; filename="{result["filename"]}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{user_id}", response_model=UserDocumentsMetadataResponse)
async def get_user_documents(
    user_id: str,
    document_type: DocumentType | None = Query(
        default=None,
        description="Filter results to a single document type",
    ),
    document_status: list[DocumentStatus] | None = Query(
        default=None,
        description=(
            "Filter by one or more document statuses "
            "(repeat the parameter; non-owners default to active)"
        ),
    ),
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
) -> UserDocumentsMetadataResponse:
    """
    Return document metadata for another user when RBAC allows.

    Optionally filter by ``document_type`` and/or one or more
    ``document_status`` values (repeat the query parameter).
    """
    return await service.get_metadata(
        current_user,
        user_id,
        document_type=document_type.value if document_type else None,
        document_status=document_status,
    )


@router.get("/{user_id}/{document_type}/view")
async def view_user_document(
    user_id: str,
    document_type: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
):
    """Stream another user's document inline when RBAC allows."""
    result = await service.stream_document(
        requester=current_user,
        target_user_id=user_id,
        document_type=document_type,
        disposition="inline",
    )
    return StreamingResponse(
        result["body"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": f'inline; filename="{result["filename"]}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{user_id}/{document_type}/download")
async def download_user_document(
    user_id: str,
    document_type: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
):
    """Download another user's document when RBAC allows."""
    result = await service.stream_document(
        requester=current_user,
        target_user_id=user_id,
        document_type=document_type,
        disposition="attachment",
    )
    return StreamingResponse(
        result["body"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": (
                f'attachment; filename="{result["filename"]}"'
            ),
            "Cache-Control": "private, no-store",
        },
    )
