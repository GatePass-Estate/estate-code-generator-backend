from datetime import datetime
from typing import List

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_serializer

from app.schemas.notification import NotificationType

model_config = ConfigDict(from_attributes=True, extra="ignore")


class UpdatePreferenceRequest(BaseModel):
    push_enabled: bool = Field(
        ..., description="Whether push delivery is enabled"
    )
    email_enabled: bool = Field(
        ..., description="Whether email delivery is enabled"
    )
    model_config = model_config


class PreferenceResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    notification_type: NotificationType
    push_enabled: bool
    email_enabled: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class ListPreferencesResponse(BaseModel):
    items: List[PreferenceResponse]
    model_config = model_config
