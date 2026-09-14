"""Estate-type pricing multipliers (field names match EstateType values)."""

from pydantic import BaseModel, Field


class EstateTypeMultiplier(BaseModel):
    """Unit-price multipliers keyed like EstateType (housing | corporate)."""

    housing: float = Field(..., gt=0)
    corporate: float = Field(..., gt=0)
