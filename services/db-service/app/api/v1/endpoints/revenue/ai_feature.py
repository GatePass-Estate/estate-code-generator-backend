import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.revenue.ai_feature import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)
from app.services.revenue.ai_feature import AiFeatureService as Service

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
    description="Create a new item",
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
    description="Update a item by ID",
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
    "/{id}",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Deleted the item"},
    },
    description="Delete a item by ID",
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
    "/search",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved the search results"},
    },
    description="Search for items",
)
async def search(
    feature_key: str | None = None,
    name: str | None = None,
    is_free: bool | None = None,
    is_active: bool | None = None,
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
    description="Get an item by ID",
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


@router.get(
    "",
    response_model=ListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "Retrieved a list of items"},
    },
    description="Retrievs a list of items",
)
async def list_all(
    page: int | None = 1,
    limit: int | None = 20,
    service: Service = Depends(get_service),
) -> ListResponse:
    try:
        return await service.list(page=page, limit=limit)
    except Exception as e:
        logger.exception(
            "An unexpected error happened while listing the items"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
