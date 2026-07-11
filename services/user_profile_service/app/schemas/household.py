from datetime import datetime
from typing import List, Optional

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
)

__all__ = [
    "CreateHouseholdRequest",
    "CreateHouseholdResponse",
    "DeleteHouseholdResponse",
    "HouseholdItem",
    "SearchHouseholdsResponse",
    "SetHouseholdHeadRequest",
    "UpdateHouseholdRequest",
    "UpdateHouseholdResponse",
]

model_config = ConfigDict(
    from_attributes=True,
    extra="ignore",
)


class CreateHouseholdRequest(BaseModel):
    """
    Request model for creating a new household.

    Attributes:
        estate_id (UUID4): Estate the household belongs to.
        name (str): Display name for the household.
        head_user_id (UUID4): Optional initial head of the household.
    """

    estate_id: UUID4 = Field(..., description="Estate ID")
    name: str = Field(..., description="Display name of the household")
    head_user_id: Optional[UUID4] = Field(
        default=None, description="Optional initial head of the household"
    )

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: UUID4) -> str:
        return str(estate_id)

    @field_serializer("head_user_id")
    def serialize_head_user_id(
        self, head_user_id: Optional[UUID4]
    ) -> Optional[str]:
        return str(head_user_id) if head_user_id else None

    model_config = model_config


class CreateHouseholdResponse(BaseModel):
    """
    Response model after creating a household.

    Attributes:
        id (str): Unique identifier for the created household.
        created_at (datetime): Creation timestamp.
    """

    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = model_config


class HouseholdItem(BaseModel):
    """
    A single household record returned in list/search responses.

    Attributes:
        id (str): Unique identifier.
        name (str): Display name of the household.
        estate_id (str): Estate the household belongs to.
        head_user_id (str): Optional head/lead of the household.
        created_at (datetime): Creation timestamp.
    """

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name of the household")
    estate_id: str = Field(..., description="Estate ID")
    head_user_id: Optional[str] = Field(
        default=None, description="Head/lead of the household"
    )
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = model_config


class SearchHouseholdsResponse(BaseModel):
    """
    Paginated list of households.

    Attributes:
        items: List of household records.
        total: Total matching records.
        page: Current page.
        limit: Items per page.
    """

    items: List[HouseholdItem] = Field(
        ..., description="List of household records"
    )
    total: int = Field(..., description="Total matching records")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Items per page")

    model_config = model_config


class SetHouseholdHeadRequest(BaseModel):
    """
    Request model to set the head of a household.

    Attributes:
        user_id (UUID4): The user to assign as head.
    """

    user_id: UUID4 = Field(..., description="User to assign as household head")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    model_config = model_config


class UpdateHouseholdRequest(BaseModel):
    """
    Request model for transferring a user to a different household.

    Attributes:
        user_id (UUID4): User ID.
        household_id (UUID4): Household ID to transfer the user into.
    """

    user_id: UUID4 = Field(..., description="User ID")
    household_id: UUID4 = Field(..., description="Target household ID")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    @field_serializer("household_id")
    def serialize_household_id(self, household_id: UUID4) -> str:
        return str(household_id)

    model_config = model_config


class UpdateHouseholdResponse(BaseModel):
    """
    Response model for household transfer.

    Attributes:
        success (bool): Success status.
        message (str): Response message.
    """

    success: bool = Field(..., description="Success status")
    message: str = Field(..., description="Response message")

    model_config = model_config


class DeleteHouseholdResponse(BaseModel):
    """
    Response model for household deletion (soft delete).

    Attributes:
        is_deleted (bool): Whether the household was deleted.
        deleted_at (datetime): UTC timestamp of deletion.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")

    model_config = model_config
