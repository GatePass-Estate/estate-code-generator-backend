from datetime import datetime
from enum import Enum
from typing import List

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import (
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    model_config,
)

__all__ = [
    "UserRole",
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class UserRole(str, Enum):
    """
    Enumeration of supported user roles: root, primary_admin, admin, resident,
                security
    """

    ROOT = "root"
    PRIMARY_ADMIN = "primary_admin"
    ADMIN = "admin"
    RESIDENT = "resident"
    SECURITY = "security"


class RolePermissionBase(BaseModel):
    """
    Base household model containing common fields.

    Attributes:
        role_name (UserRole): Role enum key.
        can_*: Boolean flags for permissions per role.
    """

    role_name: UserRole = Field(..., description="Role enum key")
    can_register_estates: bool = Field(..., description="Can register estates")
    can_register_admin: bool = Field(..., description="Can register admin")
    can_register_users: bool = Field(..., description="Can register users")
    can_set_household_limits: bool = Field(
        ..., description="Can set household limits"
    )
    can_generate_code: bool = Field(..., description="Can generate code")
    can_validate_code: bool = Field(..., description="Can validate code")
    can_remove_admin: bool = Field(..., description="Can remove admin")
    can_transfer_admin: bool = Field(..., description="Can transfer admin")
    can_add_household_member: bool = Field(
        ..., description="Can add household member"
    )

    model_config = model_config


class CreateRequest(RolePermissionBase):
    """
    Base request model to CREATE a role permission record.

    Attributes:
        role_name (UserRole): Role enum key.
        can_*: Boolean flags for permissions per role.
    """


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a request.

    Attributes:
        id (UUID): Unique identifier for the created role permission.
        created_at (DateTime): Creation timestamp.
    """

    id: UUID4 = Field(
        ..., description="Unique identifier for the created role permission"
    )

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime = Field(..., description="Creation timestamp")
    model_config = model_config


class UpdateRequest(BaseModel):
    """
    Base request model to UPDATE a record. All fields are optional and
    only the fields that need to be updated should be provided.

    Attributes:
        id (UUID): Unique identifier.
        created_at (DateTime): Created timestamp.
        updated_at (DateTime): Updated timestamp.
        role_name (UserRole): Role enum key.
        can_*: Boolean flags for permissions per role.
    """

    role_name: UserRole | None = Field(
        default=None, description="Role enum key"
    )
    can_register_estates: bool | None = Field(
        default=None, description="Can register estates"
    )
    can_register_admin: bool | None = Field(
        default=None, description="Can register admin"
    )
    can_register_users: bool | None = Field(
        default=None, description="Can register users"
    )
    can_set_household_limits: bool | None = Field(
        default=None, description="Can set household limits"
    )
    can_generate_code: bool | None = Field(
        default=None, description="Can generate code"
    )
    can_validate_code: bool | None = Field(
        default=None, description="Can validate code"
    )
    can_remove_admin: bool | None = Field(
        default=None, description="Can remove admin"
    )
    can_transfer_admin: bool | None = Field(
        default=None, description="Can transfer admin"
    )
    can_add_household_member: bool | None = Field(
        default=None, description="Can add household member"
    )

    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id (UUID): Unique identifier for the updated user.
        created_at (DateTime): Creation timestamp.
        updated_at (DateTime): Last update timestamp.
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        is_deleted: Whether the user was deleted (soft delete).
        deleted_at: UTC Time when the user was deleted.
    """

    is_deleted: bool = Field(
        default=True, description="Flag indicating soft delete"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, RolePermissionBase):
    """
    Base response model to GET a record by id.

    Attributes:
        role_name (UserRole): Role enum key.
        can_*: Boolean flags for permissions per role.
    """


class SearchRequest(BaseSearchRequest):
    """
    Request model to GET a list of items that are not archived and filtered
    according to the provided contraints. Items are returned in a chronological
    order based on the creation timestamp.

    Attributes:
        from_date: Filter by creation date (from)
        to_date: Filter by creation date (to)
        page: Page number for pagination
        limit: Number of items per page
        role_name (UserRole): Role enum key.
        can_*: Boolean flags for permissions per role.
    """

    role_name: UserRole = Field(..., description="Role enum key")
    can_register_admin: bool = Field(..., description="Can register admin")
    can_register_users: bool = Field(..., description="Can register users")
    can_set_household_limits: bool = Field(
        ..., description="Can set household limits"
    )
    can_generate_code: bool = Field(..., description="Can generate code")
    can_validate_code: bool = Field(..., description="Can validate code")
    can_remove_admin: bool = Field(..., description="Can remove admin")
    can_transfer_admin: bool = Field(..., description="Can transfer admin")
    can_add_household_member: bool = Field(
        ..., description="Can add household member"
    )


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of users.
        page: Current page number.
        limit: Number of items per page.
        items: List of user records.
    """

    items: List[GetResponse] = Field(
        ..., description="List of role permission records"
    )
