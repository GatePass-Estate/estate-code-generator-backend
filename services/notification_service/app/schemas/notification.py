from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_serializer

model_config = ConfigDict(
    from_attributes=True, extra="ignore", populate_by_name=True
)


class NotificationType(str, Enum):
    GUEST_CODE_USED = "GUEST_CODE_USED"
    RESIDENT_CODE_USED = "RESIDENT_CODE_USED"
    BROADCAST_RECEIVED = "BROADCAST_RECEIVED"
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
    # Transactional auth / account lifecycle
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


# Types for which user preferences are ignored — always delivered
MANDATORY_TYPES: set[NotificationType] = {
    NotificationType.LOGIN_NEW_DEVICE,
    NotificationType.SESSION_REVOKED,
    NotificationType.PASSWORD_CHANGED,
    NotificationType.TWO_FA_ENABLED,
    NotificationType.TWO_FA_DISABLED,
    NotificationType.TWO_FA_RECOVERY_USED,
    NotificationType.ROLE_PROMOTED,
    NotificationType.ROLE_DEMOTED,
    NotificationType.HOUSEHOLD_TRANSFERRED,
    NotificationType.INCIDENT_REPORT_FILED,
    NotificationType.EDIT_REQUEST_PENDING,
    NotificationType.FORGOT_PASSWORD,
    NotificationType.EMAIL_VERIFICATION,
    NotificationType.WELCOME,
    NotificationType.PASSWORD_RESET_CONFIRMED,
    NotificationType.ACCOUNT_CLOSED,
    NotificationType.ACCOUNT_DEACTIVATED,
    NotificationType.ACCOUNT_DEACTIVATION_SCHEDULED,
    NotificationType.ESTATE_DEACTIVATED,
    NotificationType.ESTATE_DEACTIVATION_SCHEDULED,
    NotificationType.ESTATE_REACTIVATED,
}

# Types that do NOT create an in-app notification row.
# These are transactional emails where the user either isn't logged in
# (FORGOT_PASSWORD, EMAIL_VERIFICATION) or the account no longer exists
# (ACCOUNT_CLOSED).
NO_IN_APP_TYPES: set[NotificationType] = {
    NotificationType.FORGOT_PASSWORD,
    NotificationType.EMAIL_VERIFICATION,
    NotificationType.ACCOUNT_CLOSED,
    # Account is being force-closed; no point creating an in-app row
    NotificationType.ACCOUNT_DEACTIVATED,
}

# Types that send email by default
EMAIL_TYPES: set[NotificationType] = {
    NotificationType.LOGIN_NEW_DEVICE,
    NotificationType.PASSWORD_CHANGED,
    NotificationType.TWO_FA_ENABLED,
    NotificationType.TWO_FA_DISABLED,
    NotificationType.TWO_FA_RECOVERY_USED,
    NotificationType.ROLE_PROMOTED,
    NotificationType.ROLE_DEMOTED,
    NotificationType.HOUSEHOLD_TRANSFERRED,
    NotificationType.INCIDENT_REPORT_FILED,
    NotificationType.EDIT_REQUEST_REVIEWED,
    NotificationType.FORGOT_PASSWORD,
    NotificationType.EMAIL_VERIFICATION,
    NotificationType.WELCOME,
    NotificationType.PASSWORD_RESET_CONFIRMED,
    NotificationType.ACCOUNT_CLOSED,
    NotificationType.ACCOUNT_DEACTIVATED,
    NotificationType.ACCOUNT_DEACTIVATION_SCHEDULED,
    NotificationType.ESTATE_DEACTIVATED,
    NotificationType.ESTATE_DEACTIVATION_SCHEDULED,
    NotificationType.ESTATE_REACTIVATED,
}

# Types that send push by default
PUSH_TYPES: set[NotificationType] = {
    NotificationType.GUEST_CODE_USED,
    NotificationType.RESIDENT_CODE_USED,
    NotificationType.BROADCAST_RECEIVED,
    NotificationType.EDIT_REQUEST_REVIEWED,
    NotificationType.LOGIN_NEW_DEVICE,
    NotificationType.SESSION_REVOKED,
    NotificationType.TWO_FA_RECOVERY_USED,
    NotificationType.ROLE_PROMOTED,
    NotificationType.ROLE_DEMOTED,
    NotificationType.HOUSEHOLD_TRANSFERRED,
    NotificationType.INCIDENT_REPORT_FILED,
    NotificationType.EDIT_REQUEST_PENDING,
    NotificationType.HOUSEHOLD_HEAD_ASSIGNED,
    NotificationType.HOUSEHOLD_NEEDS_HEAD,
}


class GuestCodeUsedMeta(BaseModel):
    visitor_name: str
    code_id: str
    visit_time: str


class ResidentCodeUsedMeta(BaseModel):
    code_id: str
    access_time: str


class BroadcastReceivedMeta(BaseModel):
    broadcast_id: str
    sender_name: str
    audience: str


class IncidentReportFiledMeta(BaseModel):
    incident_id: str
    title: str
    estate_id: str


class EditRequestPendingMeta(BaseModel):
    request_id: str
    request_type: str
    requester_name: str


class EditRequestReviewedMeta(BaseModel):
    request_id: str
    request_type: str
    review_status: str


class LoginNewDeviceMeta(BaseModel):
    ip_address: str
    device_name: Optional[str] = None
    session_id: str


class SessionRevokedMeta(BaseModel):
    device_name: Optional[str] = None


class RoleChangeMeta(BaseModel):
    new_role: str
    estate_id: str


class HouseholdTransferredMeta(BaseModel):
    new_household_id: str
    estate_id: str


# ── User-facing response schemas ─────────────────────────────────────────────


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
