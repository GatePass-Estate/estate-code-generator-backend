from pydantic import BaseModel
from typing import Literal


class FeedbackEmailRequest(BaseModel):
    feedback_type: Literal["suggestion", "issue"]
    user_name: str
    user_email: str
    estate_name: str
    rating: int | None = None
    liked: str | None = None
    improvement: str | None = None
    description: str | None = None
    attachment_url: str | None = None
