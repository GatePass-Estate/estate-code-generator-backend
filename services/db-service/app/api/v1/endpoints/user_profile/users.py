import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.user_profile.users import (
    UserRole,
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)
from app.services.user_profile.users import UsersService as Service

logger = logging.getLogger(__name__)


router = APIRouter()


def get_service(
    db_session: AsyncSession = Depends(get_db_session),
) -> Service:
    """
    Get an instance of Service.

    Returns:
        Service: Instance of Service
    """
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
    """
    Creates a new record in the database if it doesn't exist, otherwise
    updates the existing record.

    Arguments:
        request: The request model to CREATE a new record.

    Returns:
        The response model to CREATE a new record.

    Raises:
        HTTPException: If there is an internal server error
    """
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
    """
    Update an existing item in the database.

    Arguments:
        id: The unique ID of the item to UPDATE.
        request: The request body for updating an item.

    Returns:
        An UPDATE response model containing reference to the updated item.

    Raises:
        HTTPException: If there is an internal server error
    """
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
    """
    Deletes a record from the database.

    Arguments:
        id: The unique ID of the item to DELETE.

    Returns:
        A DELETE response model containing reference to the deleted item.

    Raises:
        HTTPException: If there is an internal server error
    """
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
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    home_address: str | None = None,
    household_id: UUID4 | None = None,
    estate_id: UUID4 | None = None,
    role: UserRole | None = None,
    status: bool | None = None,
    from_date: datetime.date | None = None,
    to_date: datetime.date | None = None,
    page: int = 1,
    limit: int = 10,
    service: Service = Depends(get_service),
) -> ListResponse:
    """
    Searches for items constrained to the criteria given.
    It searches for all the items matching the criteria given and are not
    archived. The list is sorted by the created_at field in descending.

    Arguments:
        from_date: The creation date (from).
        to_date: The creation date (to).
        page: The number of pages of results.
        limit: The number of items per page.
        first_name (str): First name of the user.
        last_name (str): Last name of the user.
        email (str): Unique email of the user.
        phone_number (str): Optional phone number of the user.
        home_address (str): Home address.
        household_id (UUID): Reference to the household.
        estate_id (UUID): Reference to the estate.
        role (UserRole): User role (enum).
        status (bool): Active/inactive status.

    Returns:
        A chronologically sorted LIST model containing a list of items.

    Raises:
        HTTPException: If there is an internal server error
    """
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
    """
    Get an item by its unique ID from the database.

    Arguments:
        id: The unique ID of the item to retrieve.

    Returns:
        A GET response model containing reference to the retrieved item.

    Raises:
        HTTPException: If there is an internal server error
    """
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
    """
    lists all the items that are not archived. The list is sorted by the
    created_at field in descending.

    Arguments:
        page: The page number to retrieve.
        limit: The number of items per page.

    Returns:
        A chronologically sorted LIST model containing a list of items.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        return await service.list(page=page, limit=limit)
    except Exception as e:
        logger.exception(
            "An unexpected error happened while listing the encounters"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
