from pydantic import BaseModel, Field, UUID4, ConfigDict, field_serializer

__all__ = [
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
        estate_id (UUID4): Estate ID
        primary_resident_id (UUID4): Primary resident ID
        max_members (int): Max members in the household.
    """

    estate_id: UUID4 = Field(..., description="Estate ID")
    primary_resident_id: UUID4 = Field(..., description="Primary resident ID")
    max_members: int = Field(10, description="Max members in the household")

    @field_serializer("estate_id")
    def serialize_estate_id(self, estate_id: UUID4) -> str:
        return str(estate_id)

    @field_serializer("primary_resident_id")
    def serialize_primary_resident_id(self, primary_resident_id: UUID4) -> str:
        return str(primary_resident_id)

    model_config = model_config


class UpdateHouseholdRequest(BaseModel):
    """
    Request model for updating a user's household.

    Attributes:
        user_id (UUID4): User ID.
        household_id (UUID4): Household ID.
    """

    user_id: UUID4 = Field(..., description="User ID")
    household_id: UUID4 = Field(..., description="Household ID")

    @field_serializer("user_id")
    def serialize_user_id(self, user_id: UUID4) -> str:
        return str(user_id)

    @field_serializer("household_id")
    def serialize_household_id(self, household_id: UUID4) -> str:
        return str(household_id)

    model_config = model_config


class UpdateHouseholdResponse(BaseModel):
    """
    Response model for updating a user's household.

    Attributes:
        success (bool): Success status.
        message (str): Response message.
    """

    success: bool = Field(..., description="Success status")
    message: str = Field(..., description="Response message")

    model_config = model_config
