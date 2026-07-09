from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlencode

from app.core.config import settings
from app.libs.http_handler import AsyncHttpHandler
from app.schemas.incident_report import (
    CreateIncidentReportResponse,
    IncidentReportItem,
    IncidentReportListResponse,
    ReporterDetails,
)

logger = logging.getLogger(__name__)

_ENDPOINT = "api/v1/userprofile/incidentreport"


class IncidentReportRepository:
    def __init__(self, http_client: AsyncHttpHandler) -> None:
        self.client = http_client
        self.base_url = settings.DB_SERVICE_URL.rstrip("/")
        self.endpoint = f"{self.base_url}/{_ENDPOINT}"

    async def categories(self) -> list[str]:
        url = f"{self.endpoint}/categories"
        response = await self.client.async_get(url)
        return response or []

    async def create(
        self,
        *,
        estate_id: str,
        reported_by_user_id: str,
        title: Optional[str],
        category: list[str],
        custom_category: Optional[str],
        narrative: str,
        occurred_at: str,
    ) -> CreateIncidentReportResponse:
        payload = {
            "estate_id": estate_id,
            "reported_by_user_id": reported_by_user_id,
            "title": title,
            "category": category,
            "custom_category": custom_category,
            "narrative": narrative,
            "occurred_at": occurred_at,
        }
        response = await self.client.async_post(
            self.endpoint, json_data=payload
        )
        return CreateIncidentReportResponse(
            id=response["id"],
            created_at=response["created_at"],
        )

    async def get(self, incident_id: str, admin_id: str) -> IncidentReportItem:
        params = {"admin_id": admin_id}
        url = f"{self.endpoint}/{incident_id}?{urlencode(params)}"
        response = await self.client.async_get(url)
        return _parse_item(response)

    async def list(
        self,
        admin_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> IncidentReportListResponse:
        params = {
            "admin_id": admin_id,
            "page": page,
            "limit": limit,
        }
        url = f"{self.endpoint}?{urlencode(params)}"
        response = await self.client.async_get(url)
        return _parse_list(response, page, limit)

    async def search(
        self,
        *,
        estate_id: str,
        admin_id: str,
        category: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> IncidentReportListResponse:
        params: dict = {
            "estate_id": estate_id,
            "admin_id": admin_id,
            "page": page,
            "limit": limit,
        }
        if category:
            params["category"] = category
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        url = f"{self.endpoint}/search?{urlencode(params)}"
        response = await self.client.async_get(url)
        return _parse_list(response, page, limit)

    async def mark_read(self, incident_id: str, admin_id: str) -> dict:
        url = f"{self.endpoint}/{incident_id}/read"
        response = await self.client.async_post(
            url, json_data={"admin_id": admin_id}
        )
        return response or {}

    async def mark_all_read(self, estate_id: str, admin_id: str) -> dict:
        url = f"{self.endpoint}/read-all"
        response = await self.client.async_post(
            url,
            json_data={
                "admin_id": admin_id,
                "estate_id": estate_id,
            },
        )
        return response or {}

    async def clear_read(self, estate_id: str, admin_id: str) -> dict:
        url = f"{self.endpoint}/clear-read"
        response = await self.client.async_delete(
            url,
            json_data={
                "admin_id": admin_id,
                "estate_id": estate_id,
            },
        )
        return response or {}


def _parse_reporter(data: Optional[dict]) -> Optional[ReporterDetails]:
    if not data:
        return None
    return ReporterDetails(
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        email=data.get("email"),
        phone_number=data.get("phone_number"),
        home_address=data.get("home_address"),
    )


def _parse_item(data: dict) -> IncidentReportItem:
    return IncidentReportItem(
        id=str(data["id"]),
        estate_id=str(data["estate_id"]),
        reported_by_user_id=(
            str(data["reported_by_user_id"])
            if data.get("reported_by_user_id")
            else None
        ),
        title=data.get("title"),
        category=data.get("category") or [],
        custom_category=data.get("custom_category"),
        narrative=data["narrative"],
        occurred_at=data["occurred_at"],
        created_at=data["created_at"],
        updated_at=data.get("updated_at"),
        is_read=data.get("is_read", False),
        read_at=data.get("read_at"),
        reporter=_parse_reporter(data.get("reporter")),
    )


def _parse_list(
    data: Optional[dict], page: int, limit: int
) -> IncidentReportListResponse:
    if not data:
        return IncidentReportListResponse(
            items=[], total=0, page=page, limit=limit
        )
    return IncidentReportListResponse(
        items=[_parse_item(item) for item in data.get("items", [])],
        total=data.get("total", 0),
        page=data.get("page", page),
        limit=data.get("limit", limit),
    )
