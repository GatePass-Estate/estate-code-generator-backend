from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import UUID4, BaseModel, Field, field_serializer

from app.schemas.base import BaseListResponse, SharedModel, model_config

__all__ = [
    "NotificationType",
    "DevicePlatform",
    "CreateNotificationRequest",
    "CreateNotificationResponse",
    "GetNotificationResponse",
    "ListNotificationsResponse",
    "UnreadCountResponse",
    "MarkReadResponse",
    "RegisterDeviceTokenRequest",
    "RegisterDeviceTokenResponse",
    "GetDeviceTokenResponse",
    "ListDeviceTokensResponse",
    "UpsertPreferenceRequest",
    "GetPreferenceResponse",
    "ListPreferencesResponse",
    "DeleteNotificationResponse",
    "DeleteAllNotificationsResponse",
]


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
    # Admin-initiated account deactivation
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    ACCOUNT_DEACTIVATION_SCHEDULED = "ACCOUNT_DEACTIVATION_SCHEDULED"
    # Estate lifecycle
    ESTATE_DEACTIVATED = "ESTATE_DEACTIVATED"
    ESTATE_DEACTIVATION_SCHEDULED = "ESTATE_DEACTIVATION_SCHEDULED"
    ESTATE_REACTIVATED = "ESTATE_REACTIVATED"
    # Household management
    HOUSEHOLD_HEAD_ASSIGNED = "HOUSEHOLD_HEAD_ASSIGNED"
    HOUSEHOLD_NEEDS_HEAD = "HOUSEHOLD_NEEDS_HEAD"


class DevicePlatform(str, Enum):
    IOS = "IOS"
    ANDROID = "ANDROID"


# ── Notifications ────────────────────────────────────────────────────────────


class CreateNotificationRequest(BaseModel):
    user_id: UUID4 = Field(..., description="Recipient user ID")
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., description="Short display title")
    body: str = Field(..., description="Full notification body")
    payload: Optional[Dict[str, Any]] = Field(
        None, description="Optional JSON payload for deep-linking"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class CreateNotificationResponse(BaseModel):
    id: UUID4 = Field(..., description="Created notification ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class GetNotificationResponse(SharedModel):
    user_id: UUID4 = Field(..., description="Recipient user ID")
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., description="Short display title")
    body: str = Field(..., description="Full notification body")
    is_read: bool = Field(
        ..., description="Whether the notification has been read"
    )
    payload: Optional[Dict[str, Any]] = Field(
        None, description="Deep-link payload"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)


class ListNotificationsResponse(BaseListResponse):
    items: List[GetNotificationResponse] = Field(
        ..., description="List of notifications"
    )


class UnreadCountResponse(BaseModel):
    count: int = Field(..., description="Number of unread notifications")
    model_config = model_config


class MarkReadResponse(BaseModel):
    id: UUID4 = Field(..., description="Notification ID")
    is_read: bool = Field(..., description="Updated read status")
    updated_at: datetime = Field(..., description="Last updated timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class DeleteNotificationResponse(BaseModel):
    deleted: int = Field(
        ..., description="Number of notifications deleted (0 or 1)"
    )
    model_config = model_config


class DeleteAllNotificationsResponse(BaseModel):
    deleted: int = Field(..., description="Number of notifications deleted")
    model_config = model_config


# ── Device Tokens ────────────────────────────────────────────────────────────


class RegisterDeviceTokenRequest(BaseModel):
    user_id: UUID4 = Field(..., description="Owning user ID")
    session_id: Optional[UUID4] = Field(
        None, description="Session the token belongs to"
    )
    token: str = Field(..., description="FCM registration token")
    platform: DevicePlatform = Field(..., description="Target platform")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("session_id")
    def serialize_session_id(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None

    model_config = model_config


class RegisterDeviceTokenResponse(BaseModel):
    id: UUID4 = Field(..., description="Device token record ID")
    created_at: datetime = Field(..., description="Creation timestamp")

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class GetDeviceTokenResponse(SharedModel):
    user_id: UUID4 = Field(..., description="Owning user ID")
    session_id: Optional[UUID4] = Field(
        None, description="Associated session ID"
    )
    token: str = Field(..., description="FCM registration token")
    platform: DevicePlatform = Field(..., description="Target platform")

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    @field_serializer("session_id")
    def serialize_session_id(self, value: Optional[UUID]) -> Optional[str]:
        return str(value) if value else None


class ListDeviceTokensResponse(BaseModel):
    items: List[GetDeviceTokenResponse] = Field(
        ..., description="List of device tokens"
    )
    model_config = model_config


# ── Notification Preferences ─────────────────────────────────────────────────


class UpsertPreferenceRequest(BaseModel):
    user_id: UUID4 = Field(..., description="Owning user ID")
    notification_type: NotificationType = Field(
        ..., description="Notification type to configure"
    )
    push_enabled: bool = Field(
        ..., description="Whether push delivery is enabled"
    )
    email_enabled: bool = Field(
        ..., description="Whether email delivery is enabled"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)

    model_config = model_config


class GetPreferenceResponse(SharedModel):
    user_id: UUID4 = Field(..., description="Owning user ID")
    notification_type: NotificationType = Field(
        ..., description="Notification type"
    )
    push_enabled: bool = Field(
        ..., description="Whether push delivery is enabled"
    )
    email_enabled: bool = Field(
        ..., description="Whether email delivery is enabled"
    )

    @field_serializer("user_id")
    def serialize_user_id(self, value: UUID4) -> str:
        return str(value)


class ListPreferencesResponse(BaseModel):
    items: List[GetPreferenceResponse] = Field(
        ..., description="List of preference overrides"
    )
    model_config = model_config
