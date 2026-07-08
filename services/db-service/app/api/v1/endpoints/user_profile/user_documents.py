"""API endpoints for user document metadata and GCS operations."""

import datetime
import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DocumentValidationError, NotFoundError
from app.db.session import get_db_session
from app.libs import gcs_storage
from app.libs.document_filenames import stream_filename
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
)
from app.services.user_profile.user_documents import (
    UserDocumentsService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    """Return a UserDocumentsService bound to the request DB session."""
    return Service(db_session=db_session)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    user_id: UUID4 = Form(...),
    estate_id: UUID4 = Form(...),
    document_type: DocumentType = Form(...),
    uploader_role: str = Form(...),
    file: UploadFile = File(...),
    service: Service = Depends(get_service),
) -> UploadResponse:
    """Multipart upload: validate, write to GCS, and upsert metadata."""
    try:
        return await service.upload(
            user_id=user_id,
            estate_id=estate_id,
            document_type=document_type,
            uploaded_by=user_id,
            uploader_role=uploader_role,
            file=file,
        )
    except DocumentValidationError as e:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if "maximum size" in str(e).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(e)) from e
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "/{document_id}/approve",
    response_model=ApproveResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_document(
    document_id: UUID4,
    service: Service = Depends(get_service),
) -> ApproveResponse:
    """Promote a pending document from temp storage to active."""
    try:
        return await service.approve(document_id=document_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Approve document failed for %s", document_id)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/by-id/{document_id}/stream",
    status_code=status.HTTP_200_OK,
)
async def stream_document_by_id(
    document_id: UUID4,
    service: Service = Depends(get_service),
):
    """Stream a specific document row (active or pending) by ID."""
    try:
        doc, signed_url = await service.stream_document_by_id(
            document_id=document_id
        )
        filename = stream_filename(
            content_type=doc.content_type,
            original_filename=doc.original_filename,
        )
        return StreamingResponse(
            gcs_storage.stream_object(signed_url),
            media_type=doc.content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=404, detail="Document not found"
        ) from e
    except Exception as e:
        logger.exception("Stream by id failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/user/{user_id}",
    response_model=DeleteAllForUserResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_all_for_user(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> DeleteAllForUserResponse:
    """Delete all GCS objects and soft-delete document rows for a user."""
    try:
        return await service.delete_all_for_user(user_id=user_id)
    except Exception as e:
        logger.exception("Delete all documents failed for user %s", user_id)
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/{user_id}/{document_type}/stream",
    status_code=status.HTTP_200_OK,
)
async def stream_document(
    user_id: UUID4,
    document_type: DocumentType,
    service: Service = Depends(get_service),
):
    """Stream the active document bytes from GCS (internal UPS use)."""
    try:
        doc, signed_url = await service.stream_document(
            user_id=user_id, document_type=document_type
        )
        filename = stream_filename(
            content_type=doc.content_type,
            original_filename=doc.original_filename,
        )
        return StreamingResponse(
            gcs_storage.stream_object(signed_url),
            media_type=doc.content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )
    except NotFoundError as e:
        raise HTTPException(
            status_code=404, detail="Document not found"
        ) from e
    except Exception as e:
        logger.exception("Stream failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.post(
    "",
    response_model=CreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create(
    request: CreateRequest,
    service: Service = Depends(get_service),
) -> CreateResponse:
    """Create a user document metadata record."""
    try:
        return await service.create(request=request)
    except Exception as e:
        logger.exception("Create user document failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.patch("/{id}", response_model=UpdateResponse)
async def update(
    id: UUID4,
    request: UpdateRequest,
    service: Service = Depends(get_service),
) -> UpdateResponse:
    """Update an existing user document metadata record."""
    try:
        return await service.update(id=id, request=request)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("Update user document failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete("/{id}", response_model=DeleteResponse)
async def delete(
    id: UUID4,
    service: Service = Depends(get_service),
) -> DeleteResponse:
    """Soft-delete a user document metadata record by ID."""
    try:
        return await service.delete(id=id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("Delete user document failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get("/search", response_model=ListResponse)
async def search(
    user_id: UUID4 | None = None,
    estate_id: UUID4 | None = None,
    document_type: DocumentType | None = None,
    uploaded_by: UUID4 | None = None,
    document_status: DocumentStatus | None = None,
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    page: int = 1,
    limit: int = 10,
    service: Service = Depends(get_service),
) -> ListResponse:
    """Search user document metadata with optional filters."""
    try:
        request = SearchRequest(**vars())
        return await service.search(request=request, page=page, limit=limit)
    except Exception as e:
        logger.exception("Search user documents failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get("/{id}", response_model=GetResponse)
async def get(
    id: UUID4,
    service: Service = Depends(get_service),
) -> GetResponse:
    """Fetch a single user document metadata record by ID."""
    try:
        return await service.get(id=id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("Get user document failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get("", response_model=ListResponse)
async def list_all(
    page: int | None = 1,
    limit: int | None = 20,
    service: Service = Depends(get_service),
) -> ListResponse:
    """List all active user document metadata records."""
    try:
        return await service.list(page=page, limit=limit)
    except Exception as e:
        logger.exception("List user documents failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
