from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, ConfigDict, Field, model_validator

from app.schemas.notification import NotificationType


class FanOutSpec(BaseModel):
    estate_id: UUID4 = Field(..., description="Estate to fan out to")
    roles: List[str] = Field(..., description="User roles to notify")
    model_config = ConfigDict(extra="ignore")


class InternalNotifyRequest(BaseModel):
    """
    Request body for POST /api/v1/internal/notify.

    Exactly one of recipient_user_ids or fan_out must be provided.
    """

    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., description="Short display title")
    body: str = Field(..., description="Full notification body")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional deep-link payload"
    )
    recipient_user_ids: Optional[List[UUID4]] = Field(
        None, description="Explicit list of recipient user IDs"
    )
    fan_out: Optional[FanOutSpec] = Field(
        None,
        description=(
            "Resolve recipients by estate + roles "
            "(mutually exclusive with recipient_user_ids)"
        ),
    )

    @model_validator(mode="after")
    def validate_recipients(self) -> "InternalNotifyRequest":
        has_users = bool(self.recipient_user_ids)
        has_fanout = self.fan_out is not None
        if has_users == has_fanout:
            raise ValueError(
                "Exactly one of recipient_user_ids or fan_out must be provided"
            )
        return self

    model_config = ConfigDict(extra="ignore")
