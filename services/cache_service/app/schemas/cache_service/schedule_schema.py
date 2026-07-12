from typing import List

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ScheduleAddRequest",
    "ScheduleAddResponse",
    "ScheduleDueResponse",
    "ScheduleRemoveRequest",
]

model_config = ConfigDict(from_attributes=True, extra="ignore")


class ScheduleAddRequest(BaseModel):
    """
    Request to add an entry to a scheduled-task sorted set.

    Attributes:
        key: Redis sorted-set key (e.g. "scheduled_user_closures").
        score: Unix timestamp at which the task becomes due.
        member: JSON-serialised task payload stored as the sorted-set member.
    """

    key: str = Field(..., description="Redis sorted-set key")
    score: float = Field(..., description="Unix timestamp (due-at)")
    member: str = Field(..., description="JSON-serialised task payload")

    model_config = model_config


class ScheduleAddResponse(BaseModel):
    """Response returned after adding a scheduled task."""

    added: bool = Field(..., description="True if the member was newly added")

    model_config = model_config


class ScheduleDueResponse(BaseModel):
    """
    Response containing all tasks that are due now or in the past.

    Attributes:
        key: The sorted-set key that was queried.
        items: Ordered list of member strings (earliest due first).
    """

    key: str = Field(..., description="The sorted-set key that was queried")
    items: List[str] = Field(
        default_factory=list,
        description="Member strings for all due tasks",
    )

    model_config = model_config


class ScheduleRemoveRequest(BaseModel):
    """Request to remove a specific member from a scheduled-task sorted set."""

    member: str = Field(..., description="The member string to remove")

    model_config = model_config
