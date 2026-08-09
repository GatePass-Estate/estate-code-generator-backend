from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_serializer

model_config = ConfigDict(from_attributes=True, extra="ignore")


class NotificationType(str, Enum):
    GUEST_CODE_USED = "GUEST_CODE_USED"
    RESIDENT_CODE_USED = "RESIDENT_CODE_USED"
    BROADCAST_HIGH = "BROADCAST_HIGH"
    BROADCAST_MEDIUM = "BROADCAST_MEDIUM"
    INCIDENT_REPORT_FILED = "INCIDENT_REPORT_FILED"
    EDIT_REQUEST_PENDING = "EDIT_REQUEST_PENDING"
    EDIT_REQUEST_REVIEWED = "EDIT_REQUEST_REVIEWED"
    LOGIN_NEW_DEVICE = "LOGIN_NEW_DEVICE"
    SESSION_REVOKED = "SESSION_REVOKED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    TWO_FA_ENABLED = "TWO_FA_ENABLED"
    TWO_FA_DISABLED = "TWO_FA_DISABLED"
    TWO_FA_RECOVERY_USED = "TWO_FA_RECOVERY_USED"
    ROLE_PROMOTED = "ROLE_PROMOTED"
    ROLE_DEMOTED = "ROLE_DEMOTED"
    HOUSEHOLD_TRANSFERRED = "HOUSEHOLD_TRANSFERRED"
    FORGOT_PASSWORD = "FORGOT_PASSWORD"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    WELCOME = "WELCOME"
    PASSWORD_RESET_CONFIRMED = "PASSWORD_RESET_CONFIRMED"
    ACCOUNT_CLOSED = "ACCOUNT_CLOSED"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    ACCOUNT_DEACTIVATION_SCHEDULED = "ACCOUNT_DEACTIVATION_SCHEDULED"
    ESTATE_DEACTIVATED = "ESTATE_DEACTIVATED"
    ESTATE_DEACTIVATION_SCHEDULED = "ESTATE_DEACTIVATION_SCHEDULED"
    ESTATE_REACTIVATED = "ESTATE_REACTIVATED"
    HOUSEHOLD_HEAD_ASSIGNED = "HOUSEHOLD_HEAD_ASSIGNED"
    HOUSEHOLD_NEEDS_HEAD = "HOUSEHOLD_NEEDS_HEAD"


class DevicePlatform(str, Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"


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


class NotificationResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    type: NotificationType
    title: str
    body: str
    is_read: bool
    metadata: Optional[Dict[str, Any]] = Field(
        None, alias="payload", serialization_alias="metadata"
    )
    created_at: datetime
    updated_at: datetime

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class ListNotificationsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[NotificationResponse]
    model_config = model_config


class UnreadCountResponse(BaseModel):
    count: int
    model_config = model_config


class MarkReadResponse(BaseModel):
    id: UUID4
    is_read: bool
    updated_at: datetime

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class DeleteNotificationResponse(BaseModel):
    deleted: int
    model_config = model_config


class DeleteAllNotificationsResponse(BaseModel):
    deleted: int
    model_config = model_config
