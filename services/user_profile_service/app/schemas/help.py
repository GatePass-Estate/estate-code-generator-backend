from typing import Literal

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    feedback_type: Literal["suggestion", "issue"] = Field(
        ..., description="Type of feedback: 'suggestion' or 'issue'"
    )
    rating: int | None = Field(
        None,
        ge=1,
        le=5,
        description="Overall experience rating (1–5); suggestions only",
    )
    liked: str | None = Field(
        None, description="What the user liked most; suggestions only"
    )
    improvement: str | None = Field(
        None, description="Suggested improvement; suggestions only"
    )
    description: str | None = Field(
        None, description="Description of the technical issue; issues only"
    )
    attachment_url: str | None = Field(
        None, description="Screenshot or attachment URL; issues only"
    )
