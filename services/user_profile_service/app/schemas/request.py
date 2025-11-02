from datetime import datetime
from enum import Enum
from pydantic import (
    BaseModel,
    Field,
    UUID4,
    ConfigDict,
    field_serializer,
)
from typing import List, Optional

__all__ = [
    "RequestType",
    "RequestStatus",
    "CreateEditRequestRequest",
    "CreateEditRequestResponse",
    "GetEditRequestResponse",
    "ListEditRequestResponse",
    "SearchEditRequestRequest",
    "UpdateRequestStatusRequest",
    "UpdateRequestStatusResponse",
]

model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class RequestType(str, Enum):
    """
    Enumeration of request types for profile edit requests.
    """

    FIRST_NAME_CHANGE = "first_name_change"
    LAST_NAME_CHANGE = "last_name_change"
    HOME_ADDRESS_CHANGE = "home_address_change"
    EMAIL_CHANGE = "email_change"
    PHONE_NUMBER_CHANGE = "phone_number_change"
    GENDER_CHANGE = "gender_change"
    VACATE_RESIDENCE = "vacate_residence"


class RequestStatus(str, Enum):
    """
    Enumeration of request status values.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CreateEditRequestRequest(BaseModel):
    """
    Request model to create a new edit request.

    Attributes:
        request_type (RequestType): Type of field to change.
        new_value (str): New value for the field.
    """

    request_type: RequestType = Field(
        ..., description="Type of field to change"
    )
    new_value: str = Field(
        ..., min_length=1, description="New value for the field"
    )

    model_config = model_config


class CreateEditRequestResponse(BaseModel):
    """
    Response model after creating an edit request.

    Attributes:
        id (UUID4): Created request ID.
        created_at (datetime): Request creation timestamp.
    """

    id: UUID4 = Field(..., description="Created request ID")
    created_at: datetime = Field(..., description="Request creation timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    model_config = model_config


class GetEditRequestResponse(BaseModel):
    """
    Response model to get an edit request by ID.

    Attributes:
        id (UUID4): Request ID.
        resident_id (UUID4): User who made the request.
        estate_id (UUID4): Estate of the user.
        request_type (RequestType): Type of field change.
        old_value (str): Original value.
        new_value (str): Requested new value.
        status (RequestStatus): Current status of the request.
        reviewed_by (UUID4): Admin who reviewed the request.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        is_deleted (bool): Deletion status.
    """

    id: UUID4 = Field(..., description="Request ID")
    resident_id: UUID4 = Field(..., description="User who made the request")
    estate_id: UUID4 = Field(..., description="Estate of the user")
    request_type: RequestType = Field(..., description="Type of field change")
    old_value: str = Field(..., description="Original value")
    new_value: Optional[str] = Field(None, description="Requested new value")
    status: RequestStatus = Field(
        ..., description="Current status of the request"
    )
    reviewed_by: Optional[UUID4] = Field(
        None, description="Admin who reviewed the request"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(
        None, description="Last update timestamp"
    )
    is_deleted: bool = Field(False, description="Deletion status")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    @field_serializer("resident_id")
    def serialize_resident_id(self, resident_id: UUID4) -> str:
        return str(resident_id)

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: UUID4) -> str:
        return str(estate_id)

    @field_serializer("reviewed_by")
    def serialize_reviewed_by(
        self, reviewed_by: Optional[UUID4]
    ) -> Optional[str]:
        return str(reviewed_by) if reviewed_by else None

    model_config = model_config


class SearchEditRequestRequest(BaseModel):
    """
    Request model to search edit requests with optional filters and pagination.

    Attributes:
        resident_id (UUID4): Filter by resident ID.
        estate_id (UUID4): Filter by estate ID.
        request_type (RequestType): Filter by request type.
        status (RequestStatus): Filter by request status.
        from_date (datetime): Filter by creation date (from).
        to_date (datetime): Filter by creation date (to).
        page (int): Page number for pagination.
        limit (int): Number of items per page.
    """

    resident_id: Optional[UUID4] = Field(
        None, description="Filter by resident ID"
    )
    estate_id: Optional[UUID4] = Field(None, description="Filter by estate ID")
    request_type: Optional[RequestType] = Field(
        None, description="Filter by request type"
    )
    status: Optional[RequestStatus] = Field(
        None, description="Filter by request status"
    )
    from_date: Optional[datetime] = Field(
        None, description="Filter by creation date (from)"
    )
    to_date: Optional[datetime] = Field(
        None, description="Filter by creation date (to)"
    )
    page: int = Field(1, ge=1, description="Page number for pagination")
    limit: int = Field(
        10, ge=1, le=100, description="Number of items per page"
    )

    @field_serializer("resident_id")
    def serialize_resident_id(
        self, resident_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(resident_id) if resident_id else None

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: Optional[UUID4]) -> Optional[str]:
        return str(estate_id) if estate_id else None

    model_config = model_config


class ListEditRequestResponse(BaseModel):
    """
    Response model for edit request list/search operations.

    Attributes:
        total (int): Total number of requests matching search criteria.
        page (int): Current page number.
        limit (int): Number of items per page.
        items (List[GetEditRequestResponse]): List of request records.
    """

    total: int = Field(..., description="Total number of requests")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    items: List[GetEditRequestResponse] = Field(
        ..., description="List of requests"
    )

    model_config = model_config


class UpdateRequestStatusRequest(BaseModel):
    """
    Request model to approve or reject an edit request.

    Attributes:
        status (RequestStatus): New status (approved or rejected).
    """

    status: RequestStatus = Field(
        ..., description="New status (approved or rejected)"
    )

    model_config = model_config


class UpdateRequestStatusResponse(BaseModel):
    """
    Response model for request status update operations.

    Attributes:
        id (UUID4): Request ID.
        status (RequestStatus): Updated status.
        reviewed_by (UUID4): Admin who reviewed the request.
        updated_at (datetime): Update timestamp.
    """

    id: UUID4 = Field(..., description="Request ID")
    status: RequestStatus = Field(..., description="Updated status")
    reviewed_by: UUID4 = Field(
        ..., description="Admin who reviewed the request"
    )
    updated_at: datetime = Field(..., description="Update timestamp")

    @field_serializer("id")
    def serialize_id(self, id: UUID4) -> str:
        return str(id)

    @field_serializer("reviewed_by")
    def serialize_reviewed_by(self, reviewed_by: UUID4) -> str:
        return str(reviewed_by)

    model_config = model_config
