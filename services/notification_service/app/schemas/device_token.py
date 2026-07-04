from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_serializer

model_config = ConfigDict(from_attributes=True, extra="ignore")


class DevicePlatform(str, Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"
    WEB = "WEB"


class RegisterDeviceTokenRequest(BaseModel):
    token: str = Field(..., description="FCM registration token")
    platform: DevicePlatform = Field(..., description="Target platform")
    session_id: Optional[UUID4] = Field(
        None, description="Session the token belongs to"
    )

    @field_serializer("session_id")
    def serialize_session_id(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None

    model_config = model_config


class RegisterDeviceTokenResponse(BaseModel):
    id: UUID4
    created_at: datetime

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config
