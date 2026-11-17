from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import List, Optional

from pydantic import (
    UUID4,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

__all__ = [
    "IncidentCategory",
    "CreateIncidentReportRequest",
    "CreateIncidentReportResponse",
    "ReporterDetails",
    "IncidentReportItem",
    "IncidentReportListResponse",
]

model_config = ConfigDict(from_attributes=True, extra="ignore")


class IncidentCategory(StrEnum):
    SECURITY = "security"
    ACCESS_CONTROL = "access_control"
    NOISE_DISTURBANCE = "noise_disturbance"
    PROPERTY_DAMAGE = "property_damage"
    MAINTENANCE = "maintenance"
    FIRE_SAFETY = "fire_safety"
    MEDICAL_EMERGENCY = "medical_emergency"
    THEFT = "theft"
    HARASSMENT = "harassment"
    DISPUTE = "dispute"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    OTHER = "other"


class CreateIncidentReportRequest(BaseModel):
    title: Optional[str] = None
    category: List[IncidentCategory] = Field(default_factory=list)
    custom_category: Optional[str] = None
    narrative: str
    occurred_at: datetime

    model_config = model_config

    @model_validator(mode="after")
    def _validate_category_exclusive(
        self,
    ) -> CreateIncidentReportRequest:
        has_category = bool(self.category)
        has_custom = bool(
            self.custom_category and self.custom_category.strip()
        )
        if not has_category and not has_custom:
            raise ValueError("Provide either a category or a custom_category.")
        if has_category and has_custom:
            raise ValueError(
                "Provide either a category or a custom_category," " not both."
            )
        return self


class CreateIncidentReportResponse(BaseModel):
    id: UUID4

    @field_serializer("id")
    def serialize_id(self, value: UUID4) -> str:
        return str(value)

    created_at: datetime
    model_config = model_config


class ReporterDetails(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    home_address: Optional[str] = None

    model_config = model_config


class IncidentReportItem(BaseModel):
    id: str
    estate_id: str
    reported_by_user_id: Optional[str] = None
    title: Optional[str] = None
    category: List[IncidentCategory] = Field(default_factory=list)
    custom_category: Optional[str] = None
    narrative: str
    occurred_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    reporter: Optional[ReporterDetails] = None

    model_config = model_config


class IncidentReportListResponse(BaseModel):
    items: List[IncidentReportItem]
    total: int
    page: int
    limit: int

    model_config = model_config
