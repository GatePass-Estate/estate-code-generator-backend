from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

__all__ = [
    "BroadcastCategory",
    "BroadcastPriority",
    "BroadcastCreatePayload",
    "BroadcastCreateResponse",
    "UpdateBroadcastRequest",
    "BroadcastUpdateResponse",
    "BroadcastDeleteResponse",
    "BroadcastReadResponse",
    "DismissAllResponse",
    "CreateBroadcastRequest",
    "BroadcastItem",
    "BroadcastListResponse",
    "UnreadBroadcastCountResponse",
]


class BroadcastCategory(str, Enum):
    BROADCAST = "BROADCAST"
    AD = "AD"


class BroadcastPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ---------------------------------------------------------------------------
# Inbound request schemas (from API consumers)
# ---------------------------------------------------------------------------


class CreateBroadcastRequest(BaseModel):
    title: str = Field(..., description="Broadcast title")
    message: str = Field(..., description="Full broadcast message")
    category: BroadcastCategory = Field(
        BroadcastCategory.BROADCAST, description="Broadcast category"
    )
    priority: BroadcastPriority = Field(
        BroadcastPriority.LOW, description="Delivery priority"
    )
    audience: List[str] = Field(
        ..., description="Roles that should receive this broadcast"
    )
    sender_name: Optional[str] = Field(
        None,
        description="Custom sender display name (AD category only)",
    )
    attachment_url: Optional[str] = Field(
        None, description="Optional attachment URL"
    )
    expires_at: Optional[datetime] = Field(
        None, description="UTC expiration timestamp (required for AD)"
    )
    # Root-only targeting — ignored for admin broadcasts
    target_estate_ids: Optional[List[UUID]] = Field(
        None, description="Explicit estate IDs to target"
    )
    target_state: Optional[str] = Field(
        None, description="Target all estates in this state"
    )
    target_lga: Optional[str] = Field(
        None, description="Target all estates in this LGA"
    )
    target_estate_type: Optional[str] = Field(
        None, description="Target estates of this type (housing/corporate)"
    )


class UpdateBroadcastRequest(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    priority: Optional[BroadcastPriority] = None
    audience: Optional[List[str]] = None
    sender_name: Optional[str] = None
    attachment_url: Optional[str] = None
    status: Optional[bool] = None
    expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Internal payload schema (UPS → db-service)
# ---------------------------------------------------------------------------


class BroadcastCreatePayload(BaseModel):
    """Typed payload sent to db-service when persisting a new broadcast."""

    estate_id: Optional[str] = None
    sender_id: str
    title: str
    message: str
    category: str
    priority: str
    audience: List[str]
    sender_name: Optional[str] = None
    attachment_url: Optional[str] = None
    status: bool = True
    expires_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Response schemas (db-service → UPS → API consumers)
# ---------------------------------------------------------------------------


class BroadcastItem(BaseModel):
    id: str
    estate_id: Optional[str] = None
    sender_id: str
    title: str
    message: str
    audience: List[str]
    category: str = "BROADCAST"
    priority: str
    sender_name: Optional[str] = None
    attachment_url: Optional[str] = None
    status: bool
    expires_at: Optional[datetime] = None
    is_read: bool = False
    created_at: datetime
    updated_at: datetime


class BroadcastListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BroadcastItem]


class BroadcastCreateResponse(BaseModel):
    id: str
    created_at: datetime


class BroadcastUpdateResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime


class BroadcastDeleteResponse(BaseModel):
    is_deleted: bool
    deleted_at: datetime


class BroadcastReadResponse(BaseModel):
    """Returned by mark_read and dismiss operations."""

    id: str
    created_at: datetime


class DismissAllResponse(BaseModel):
    dismissed: int


class UnreadBroadcastCountResponse(BaseModel):
    count: int
