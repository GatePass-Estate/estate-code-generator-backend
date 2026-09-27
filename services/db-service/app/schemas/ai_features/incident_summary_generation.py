"""Schemas for the per-estate third-party summary generation counter."""

from __future__ import annotations

from datetime import date

from pydantic import UUID4, BaseModel

from app.schemas.base import model_config


class ConsumeRequest(BaseModel):
    """Estate asking to spend one new third-party summary generation."""

    model_config = model_config

    estate_id: UUID4


class ConsumeResponse(BaseModel):
    """Counter after a generation was reserved."""

    model_config = model_config

    estate_id: UUID4
    generation_date: date
    generation_count: int
