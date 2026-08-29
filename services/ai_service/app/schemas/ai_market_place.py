"""Request and response models for the AI marketplace consumer API."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RatingSample(BaseModel):
    """One bounded sample from the rating summary (up to 5 per score)."""

    user_id: str
    score: int
    comment: str | None = None
    created_at: str | None = None


class MarketplaceListItem(BaseModel):
    """One parent product on the marketplace list."""

    id: str
    name: str
    category: str
    rating: float | None = None
    rating_count: int = 0
    rating_samples: dict[str, list[RatingSample]] = Field(default_factory=dict)
    purchased: bool = False
    price: float | None = None
    currency_code: str | None = None
    ai_feature_ids: list[str] = Field(default_factory=list)


class MarketplaceListResponse(BaseModel):
    """Paginated marketplace list."""

    items: list[MarketplaceListItem]
    total: int
    page: int
    limit: int


class MarketplaceTier(BaseModel):
    """Child ``ai_feature`` rendered as a tier on the detail page."""

    tier: str
    ai_feature_id: str
    feature_key: str | None = None
    name: str | None = None
    description: str | None = None
    is_free: bool = False
    price: float | None = None
    currency_code: str | None = None
    status: str
    is_installed: bool = False


class MarketplaceDetailResponse(BaseModel):
    """Parent product overview plus child tiers and rating summary."""

    id: str
    name: str
    category: str
    description: str | None = None
    rating: float | None = None
    rating_count: int = 0
    rating_samples: dict[str, list[RatingSample]] = Field(default_factory=dict)
    tiers: list[MarketplaceTier] = Field(default_factory=list)


class RatingRequest(BaseModel):
    """Body for creating or updating a user's product rating."""

    score: int = Field(..., ge=1, le=5)
    comment: str | None = None


class UserRating(BaseModel):
    """The caller's just-created or updated rating row."""

    id: str
    user_id: str
    score: int
    comment: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class RatingResponse(BaseModel):
    """Aggregate rating summary plus the caller's saved rating."""

    id: str
    rating: float | None = None
    rating_count: int = 0
    rating_samples: dict[str, list[RatingSample]] = Field(default_factory=dict)
    user_rating: UserRating


class SubscribeRequest(BaseModel):
    """Body for subscribing to a child ``ai_feature`` tier."""

    ai_feature_id: str
    period_months: int = Field(1, ge=1)


class SubscribeResponse(BaseModel):
    """Quote (paid only) and revenue-service install or activate result."""

    estate_id: str
    ai_feature_id: str
    feature_key: str
    quote: dict[str, Any] | None = None
    activation: dict[str, Any]


PurchaseStatus = Literal["purchased", "not_purchased"]
