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
from app.services.user_profile.user_documents import (
    UserDocumentsService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
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
    file: UploadFile = File(...),
    service: Service = Depends(get_service),
) -> UploadResponse:
    try:
        return await service.upload(
            user_id=user_id,
            estate_id=estate_id,
            document_type=document_type,
            uploaded_by=user_id,
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


@router.delete(
    "/user/{user_id}",
    response_model=DeleteAllForUserResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_all_for_user(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> DeleteAllForUserResponse:
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
    from_date: datetime.datetime | None = None,
    to_date: datetime.datetime | None = None,
    page: int = 1,
    limit: int = 10,
    service: Service = Depends(get_service),
) -> ListResponse:
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
    try:
        return await service.list(page=page, limit=limit)
    except Exception as e:
        logger.exception("List user documents failed")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
