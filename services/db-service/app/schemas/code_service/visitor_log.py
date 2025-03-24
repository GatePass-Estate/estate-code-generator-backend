from datetime import datetime
from enum import Enum
from typing import List

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.code_service.base import (
    Access,
    BaseListResponse,
    BaseSearchRequest,
    SharedModel,
    Status,
    model_config,
)

__all__ = [
    "CreateRequest",
    "CreateResponse",
    "UpdateRequest",
    "UpdateResponse",
    "DeleteResponse",
    "GetResponse",
    "SearchRequest",
    "ListResponse",
]


class Relation(str, Enum):
    """
    Enumeration of supported resident-guest relation: family, spouse,
            friend, delivery, taxi, technician
    """

    FAMILY = "family"
    SPOUSE = "spouse"
    FRIEND = "friend"
    TECHNICIAN = "technician"
    TAXI = "taxi"
    DELIVERY = "delivery"


class WorkflowBase(BaseModel):
    """
    Model for Composer Workflows table.

    Attributes:
        id: Unique identifier of the record
        access: Access level of the record
        status: Availability status of the record
        created_at: Creation timestamp
        updated_at: Last updated timestamp
        is_deleted: Flag to indicate if the record is deleted
        name: Name of the workflow
        description: Description of the workflow
        version: Version of the workflow in the format 'vX.Y.Z'
        steps: List of steps in the workflow
    """

    org_id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Name of the workflow")
    description: str | None = Field(
        default=None, description="Description of the workflow"
    )
    version: str = Field(
        ..., description="Version of the workflow in the format 'vX.Y.Z'"
    )
    url: str | None = Field(
        default=None,
        description="Unique URL to access and share the results of a "
        "workflow execution",
    )
    deployed_at: datetime | None = Field(
        default=None, description="Time when the workflow was deployed"
    )

    model_config = model_config


class CreateRequest(BaseModel):
    """
    Base request model to CREATE a record.

    Attributes:
        access: Access level of the record
        status: Availability status of the record
        name: Name of the workflow
        description: Description of the workflow
        version: Version of the workflow in the format 'vX.Y.Z'
        steps: List of steps with nested resources and instructions
    """

    org_id: str = Field(..., description="Organization ID")
    name: str = Field(..., description="Name of the workflow")
    description: str | None = Field(
        default=None, description="Description of the workflow"
    )
    version: str = Field(
        ..., description="Version of the workflow in the format 'vX.Y.Z'"
    )
    url: str | None = Field(
        default=None,
        description="Unique URL to access and share the results of a "
        "workflow execution",
    )
    deployed_at: datetime | None = Field(
        default=None, description="Time when the workflow was deployed"
    )

    access: Access | None = Field(
        default=Access.PUBLIC, description="Access level of the record"
    )
    status: Status | None = Field(
        default=Status.AVAILABLE, description="Status of the record"
    )

    model_config = model_config


class CreateResponse(BaseModel):
    """
    Base response model to CREATE a record.

    Attributes:
        id: Unique identifier returned for the created record
        created_at: Creation timestamp
    """

    id: UUID4 = Field(
        ..., description="Unique identifier returned for the created record"
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
        access: Access level of the record
        status: Availability status of the record
        name: Name of the workflow
        description: Description of the workflow
        version: Version of the workflow in the format 'vX.Y.Z'
        state: State of the workflow
        url: Unique URL to access and share the results of a workflow execution
        deployed_at: Time when the workload was deployed
    """

    access: Access | None = Field(
        default=None, description="Access level of the record"
    )
    status: Status | None = Field(
        default=None, description="Status of the record"
    )
    name: str | None = Field(None, description="Name of the workflow")
    description: str | None = Field(
        default=None, description="Description of the workflow"
    )
    version: str | None = Field(
        None, description="Version of the workflow in the format 'vX.Y.Z'"
    )
    url: str | None = Field(
        default=None,
        description="Unique URL to access and share the results of a "
        "workflow execution",
    )
    deployed_at: datetime | None = Field(
        default=None, description="Time when the workload was deployed"
    )
    model_config = model_config


class UpdateResponse(CreateResponse):
    """
    Base response model to UPDATE a record by id.

    Attributes:
        id: Unique identifier returned for the updated record
        created_at: Creation timestamp
        updated_at: Last updated timestamp
    """

    updated_at: datetime = Field(..., description="Last updated timestamp")


class DeleteResponse(BaseModel):
    """
    Base response model to DELETE a record by id.

    Attributes:
        is_deleted: Flag to indicate if itemm is deleted
        archived_at: UTC Time when the item was archived.
        deleted_at: UTC Time when the item was deleted.
    """

    is_deleted: bool = Field(
        default=True,
        description="Flag to indicate if item is deleted",
    )
    archived_at: datetime = Field(
        ..., description="UTC timestamp of archiving"
    )
    deleted_at: datetime = Field(..., description="UTC timestamp of deletion")
    model_config = model_config


class GetResponse(SharedModel, WorkflowBase):
    """
    Base response model to GET a record by id.

    Attributes:
        id: Unique identifier of the record
        access: Access level of the record
        status: Availability status of the record
        created_at: Creation timestamp
        updated_at: Last updated timestamp
        is_deleted: Flag to indicate if the record is deleted
        name: Name of the workflow
        description: Description of the workflow
        version: Version of the workflow in the format 'vX.Y.Z'
        state: State of the workflow
        url: Unique URL to access and share the results of a workflow execution
        deployed_at: Time when the workload was deployed
        steps: List of steps implemented in the workflow
    """


class SearchRequest(BaseSearchRequest):
    """
    Request model to GET a list of items that are not archived and filtered
    according to the provided contraints. Items are returned in a chronological
    order based on the creation timestamp.

    Attributes:
        access: Access level of the record
        status: Availability status of the record
        from_date: Filter by creation date (from)
        to_date: Filter by creation date (to)
        page: Page number for pagination
        limit: Number of items per page
        org_id: The organization ID.
        name: Name of the workflow
        version: Version of the workflow
        state: Progress state of the workflow
    """

    org_id: str | None = Field(None, description="Organization ID")
    name: str | None = Field(None, description="Name of the workflow")
    version: str | None = Field(None, description="Version of the workflow")


class ListResponse(BaseListResponse):
    """
    Response model to GET the list of all items that are not archived. Items
    are returned in a chronological order based on the creation timestamp.

    Attributes:
        total: Total number of items that are not archived
        page: Current page number
        limit: Number of items per page
        items: Ordered list of table objects
    """

    items: List[GetResponse] = Field(
        ..., description="Ordered list of table objects"
    )
