import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db_session
from app.schemas.user_profile.sessions import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
    ValidateSessionResponse,
)
from app.services.user_profile.sessions import SessionsService as Service

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


@router.delete(
    "/user/{user_id}",
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        200: {"description": "Deleted all sessions for the user"},
    },
    description="Delete all sessions for a user",
)
async def delete_all_for_user(
    user_id: UUID4,
    service: Service = Depends(get_service),
) -> dict:
    """
    Soft-deletes all sessions belonging to a given user.

    Arguments:
        user_id: The unique ID of the user whose sessions should be deleted.

    Returns:
        A dict confirming deletion.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        await service.delete_all_for_user(user_id=user_id)
        return {"deleted": True}
    except Exception as e:
        logger.exception(
            "An unexpected error happened while deleting all "
            "sessions for the user"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/by-biometric-token",
    response_model=GetResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "No session found for this biometric token"},
        500: {"description": "Internal server error"},
    },
    description="Look up an active session by its biometric token hash",
)
async def get_by_biometric_token(
    hash: str,
    service: Service = Depends(get_service),
) -> GetResponse:
    """
    Returns the session row whose ``biometric_token_hash`` matches the
    provided SHA-256 hex digest.  Used by user-profile-service during
    biometric login to verify the token without exposing the session ID.

    Arguments:
        hash: SHA-256 hex digest of the biometric token.

    Returns:
        GetResponse for the matching session.

    Raises:
        HTTPException 404: If no active session has this hash.
        HTTPException 500: If there is an internal server error.
    """
    try:
        return await service.get_by_biometric_hash(token_hash=hash)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail="No session found for the provided biometric token",
        ) from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while looking up biometric session"
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
    user_id: UUID4 | None = None,
    ip_address: str | None = None,
    is_2fa_verified: bool | None = None,
    last_active_after: datetime.datetime | None = None,
    page: int = 1,
    limit: int = 10,
    service: Service = Depends(get_service),
) -> ListResponse:
    """
    Searches for items constrained to the criteria given.
    It searches for all the items matching the criteria given and are not
    archived. The list is sorted by the created_at field in descending.

    Arguments:
        user_id (UUID): Filter by user ID.
        ip_address (str): Filter by IP address.
        is_2fa_verified (bool): Filter by 2FA verification status.
        last_active_after (datetime): Filter sessions active after this time.
        page: The number of pages of results.
        limit: The number of items per page.

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
    "/{id}/validate",
    response_model=ValidateSessionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Session or user not found"},
        200: {"description": "Session is valid"},
    },
    description="Validate a session and return combined session + user data",
)
async def validate_session(
    id: UUID4,
    service: Service = Depends(get_service),
) -> ValidateSessionResponse:
    """
    Validates that a session exists and its user is active,
    returning combined session and user data in a single DB query.

    Arguments:
        id: The unique session ID to validate.

    Returns:
        A ValidateSessionResponse with session and user fields.

    Raises:
        HTTPException 404: If the session or user is not found / deleted.
        HTTPException 500: If there is an internal server error.
    """
    try:
        return await service.validate_session(str(id))
    except NotFoundError as e:
        raise HTTPException(
            status_code=404, detail="Session or user not found"
        ) from e
    except Exception as e:
        logger.exception(
            "An unexpected error happened while validating the session"
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
