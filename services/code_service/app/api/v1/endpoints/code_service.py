import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.exceptions import NotFoundError
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.schemas.code_service import (
    CreateRequestResident,
    CreateRequestVisitor,
    CreateResponse,
    GetResponseResident,
    GetResponseVisitor,
)
from app.services.code_service import (
    CodeService as Service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    ahttp_client: AsyncHttpHandler = Depends(get_http_handler),
) -> Service:
    """
    Get an instance of Service.

    Returns:
        Service: Instance of Service
    """
    return Service(ahttp_client=ahttp_client)


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
async def generate(
    receiver: str,
    request: CreateRequestVisitor | CreateRequestResident,
    service: Service = Depends(get_service),
) -> CreateResponse:
    """
    Creates a new record in the database if it doesn't exist, otherwise
    updates the existing record.

    Arguments:
        request: The request model to CREATE a new record.
        receiver: The status of the code owner (visitor or resident).

    Returns:
        The response model to CREATE a new record.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        return await service.generate(request=request, receiver=receiver)
    except Exception as e:
        logger.exception(
            f"An unexpected error happened while creating the item\nError: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@router.get(
    "/{code}",
    response_model=GetResponseResident | GetResponseVisitor,
    status_code=status.HTTP_200_OK,
    responses={
        500: {"description": "Internal server error"},
        404: {"description": "Item not found"},
        200: {"description": "Retrieved the item"},
    },
    description="Get an item by ID",
)
async def validate(
    receiver: str,
    code: str,
    service: Service = Depends(get_service),
) -> GetResponseResident | GetResponseVisitor:
    """
    Get an item by its unique ID from the database.

    Arguments:
        code: The generated access code to be validated.
        recevier: The status of the code owner (visitor and resident)

    Returns:
        A GET response model containing reference to the retrieved item.

    Raises:
        HTTPException: If there is an internal server error
    """
    try:
        return await service.validate(code=code, receiver=receiver)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail="Item not found") from e
    except Exception as e:
        logger.exception("An unexpected error happened while getting the item")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e
