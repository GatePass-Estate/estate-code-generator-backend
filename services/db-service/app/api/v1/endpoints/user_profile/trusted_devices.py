import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.user_profile.trusted_devices import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)
from app.services.user_profile.trusted_devices import (
    TrustedDevicesService as Service,
)

logger = logging.getLogger(__name__)


router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    return Service(db_session=db_session)


@router.post(
    "",
    response_model=CreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "item saved successfully"},
    },
    description="Create a new trusted device",
)
async def create(
    request: CreateRequest,
    service: Service = Depends(get_service),
) -> CreateResponse:
    try:
        return await service.create(request=request)
    except Exception as e:
        logger.exception(
            "An unexpected error happened while creating the item"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.patch(
    "/{id}",
    response_model=UpdateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Updated the item"},
    },
    description="Update a trusted device by ID",
)
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
        logger.exception(
            "An unexpected error happened while updating the item"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/user/{user_id}",
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "Revoked all trusted devices for the user"},
    },
    description="Revoke all trusted devices for a user",
)
async def revoke_all_for_user(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> dict:
    try:
        await service.revoke_all_for_user(user_id=user_id)
        return {"revoked": True}
    except Exception as e:
        logger.exception(
            "An unexpected error happened while revoking all "
            "trusted devices for the user"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.delete(
    "/{id}",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Deleted the item"},
    },
    description="Delete a trusted device by ID",
)
async def delete(
    id: UUID4,
    service: Service = Depends(get_service),
) -> DeleteResponse:
    try:
        return await service.delete(id=id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while deleting the item"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/by-token-hash",
    response_model=GetResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "No trusted device found for this token hash"},
        500: {"description": "Internal server error"},
    },
    description="Look up a trusted device by its token hash",
)
async def get_by_token_hash(
    hash: str,
    service: Service = Depends(get_service),
) -> GetResponse:
    try:
        return await service.get_by_token_hash(token_hash=hash)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail="No trusted device found for the provided token hash",
        ) from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while looking up trusted device"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/search",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved the search results"},
    },
    description="Search for trusted devices",
)
async def search(
    user_id: UUID4 | None = None,
    token_hash: str | None = None,
    is_revoked: bool | None = None,
    page: int = 1,
    limit: int = Query(default=10, le=100),
    service: Service = Depends(get_service),
) -> ListResponse:
    try:
        request = SearchRequest(**vars())
        return await service.search(request=request, page=page, limit=limit)
    except Exception as e:
        logger.exception(
            "An unexpected error happened while searching for matches"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/{id}",
    response_model=GetResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Retrieved the item"},
    },
    description="Get a trusted device by ID",
)
async def get(
    id: UUID4,
    service: Service = Depends(get_service),
) -> GetResponse:
    try:
        return await service.get(id=id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting the item")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
