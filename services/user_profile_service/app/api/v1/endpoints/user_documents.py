import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.user import UserRepository
from app.repositories.user_documents import UserDocumentsRepository
from app.schemas.user_documents import (
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
    return await service.upload(current_user, file, document_type)


@router.get("/me", response_model=UserDocumentsMetadataResponse)
async def get_my_documents(
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
) -> UserDocumentsMetadataResponse:
    return await service.get_metadata(current_user, str(current_user["id"]))


@router.get("/me/{document_type}/view")
async def view_my_document(
    document_type: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
):
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


@router.get("/{user_id}", response_model=UserDocumentsMetadataResponse)
async def get_user_documents(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
) -> UserDocumentsMetadataResponse:
    return await service.get_metadata(current_user, user_id)


@router.get("/{user_id}/{document_type}/view")
async def view_user_document(
    user_id: str,
    document_type: str,
    current_user: dict = Depends(get_current_user),
    service: UserDocumentsService = Depends(get_documents_service),
):
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
