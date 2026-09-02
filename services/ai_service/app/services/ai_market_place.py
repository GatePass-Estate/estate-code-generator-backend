"""Estate-scoped AI marketplace list, detail, rating, and subscribe logic."""

from typing import Any

from fastapi import HTTPException

from app.repositories.ai_market_place import AiMarketPlaceRepository
from app.schemas.ai_market_place import (
    MarketplaceDetailResponse,
    MarketplaceListItem,
    MarketplaceListResponse,
    MarketplaceTier,
    RatingResponse,
    RatingSample,
    SubscribeResponse,
    UserRating,
)


def _tier_entries(tiers: Any) -> list[dict]:
    """Normalize parent ``tiers`` JSON into ``[{tier, ai_feature_id}, ...]``."""
    if isinstance(tiers, list):
        return [t for t in tiers if isinstance(t, dict)]
    if isinstance(tiers, dict):
        entries = []
        for key, value in tiers.items():
            fid = (
                value.get("ai_feature_id")
                if isinstance(value, dict)
                else value
            )
            entries.append({"tier": str(key), "ai_feature_id": str(fid)})
        return entries
    return []


def _ai_feature_ids(tiers: Any) -> list[str]:
    """Return child ``ai_feature_id`` values from parent ``tiers`` JSON."""
    ids = []
    for entry in _tier_entries(tiers):
        fid = entry.get("ai_feature_id")
        if fid:
            ids.append(str(fid))
    return ids


def _price_map(prices: list[dict]) -> tuple[dict[str, float], str | None]:
    """Map ``ai_feature_id`` to unit price and pick the first currency code."""
    mapped: dict[str, float] = {}
    currency = None
    for row in prices:
        fid = row.get("ai_feature_id")
        if not fid:
            continue
        mapped[str(fid)] = float(row["feature_unit_price"])
        currency = currency or row.get("currency_code")
    return mapped, currency


def _grant_map(grants: list[dict]) -> dict[str, dict]:
    """Index estate AI grants by ``ai_feature_id``."""
    return {
        str(g["ai_feature_id"]): g for g in grants if g.get("ai_feature_id")
    }


def _is_purchased(feature_ids: list[str], grants: dict[str, dict]) -> bool:
    """True if the estate has a grant for any child ``ai_feature_id``."""
    return any(fid in grants for fid in feature_ids)


def _tier_status(grant: dict | None) -> str:
    """Map an estate grant to a marketplace tier status label."""
    if not grant:
        return "not_purchased"
    if grant.get("is_installed"):
        return "installed"
    status = (grant.get("status") or "").lower()
    if status == "active":
        return "subscribed"
    return status or "subscribed"


def _min_price(
    feature_ids: list[str], prices: dict[str, float]
) -> float | None:
    """Return the lowest child unit price, or None if none are priced."""
    amounts = [prices[fid] for fid in feature_ids if fid in prices]
    return min(amounts) if amounts else None


def _parse_samples(raw: dict | None) -> dict[str, list[RatingSample]]:
    """Normalize summary samples into score keys ``1``–``5``, max 5 each."""
    samples = {str(score): [] for score in range(1, 6)}
    if not isinstance(raw, dict):
        return samples
    for score in range(1, 6):
        key = str(score)
        rows = raw.get(key) or []
        samples[key] = [
            RatingSample(
                user_id=str(row.get("user_id")),
                score=int(row.get("score", score)),
                comment=row.get("comment"),
                created_at=(
                    str(row["created_at"]) if row.get("created_at") else None
                ),
            )
            for row in rows[:5]
            if isinstance(row, dict) and row.get("user_id")
        ]
    return samples


def _as_str(value: Any) -> str | None:
    """Stringify ``value``, or None if it is missing."""
    return str(value) if value is not None else None


def _user_rating(
    row: dict,
    *,
    user_id: str,
    score: int,
    comment: str | None,
) -> UserRating:
    """Build the caller's rating payload from a create/update row."""
    resolved_comment = row["comment"] if "comment" in row else comment
    return UserRating(
        id=str(row["id"]),
        user_id=str(row.get("user_id") or user_id),
        score=int(row.get("score") or score),
        comment=resolved_comment,
        created_at=_as_str(row.get("created_at")),
        updated_at=_as_str(row.get("updated_at")),
    )


def _rating_map(summaries: list[dict]) -> dict[str, dict]:
    """Index rating summaries by parent marketplace feature id."""
    mapped: dict[str, dict] = {}
    for row in summaries:
        fid = str(row.get("ai_marketplace_feature_id") or "")
        if not fid:
            continue
        mapped[fid] = {
            "rating": row.get("rating"),
            "rating_count": int(row.get("rating_count") or 0),
            "rating_samples": _parse_samples(row.get("samples")),
        }
    return mapped


class AiMarketPlaceService:
    """Assemble marketplace payloads from db-service and revenue-service."""

    def __init__(self, repository: AiMarketPlaceRepository) -> None:
        """Store the HTTP repository used for catalog, ratings, and billing."""
        self.repository = repository

    async def _catalog(
        self, estate_id: str
    ) -> tuple[dict[str, dict], dict[str, float], str | None, dict[str, dict]]:
        """Load AI catalog, country prices, and estate grants for detail."""
        estate = await self.repository.get_estate(estate_id)
        country = (estate.get("country") or "").upper()
        prices_raw = (
            await self.repository.list_prices(country) if country else []
        )
        prices, currency = _price_map(prices_raw)
        grants = _grant_map(
            await self.repository.list_estate_ai_features(estate_id)
        )
        catalog = {
            str(item["id"]): item
            for item in await self.repository.list_ai_features()
        }
        return catalog, prices, currency, grants

    async def list(
        self,
        estate_id: str,
        *,
        purchase_status: list[str] | None = None,
        category: list[str] | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> MarketplaceListResponse:
        """List active products, filtered and priced for this estate."""
        raw = await self.repository.list_products(
            category=category, page=1, limit=200
        )
        estate = await self.repository.get_estate(estate_id)
        country = (estate.get("country") or "").upper()
        prices, currency = _price_map(
            await self.repository.list_prices(country) if country else []
        )
        grants = _grant_map(
            await self.repository.list_estate_ai_features(estate_id)
        )

        items: list[MarketplaceListItem] = []
        for product in raw.get("items") or []:
            fids = _ai_feature_ids(product.get("tiers"))
            purchased = _is_purchased(fids, grants)
            if purchase_status:
                label = "purchased" if purchased else "not_purchased"
                if label not in purchase_status:
                    continue
            items.append(
                MarketplaceListItem(
                    id=str(product["id"]),
                    name=product["name"],
                    category=product["category"],
                    purchased=purchased,
                    price=(None if purchased else _min_price(fids, prices)),
                    currency_code=None if purchased else currency,
                    ai_feature_ids=fids,
                )
            )

        total = len(items)
        start = (page - 1) * limit
        page_items = items[start : start + limit]
        ratings = _rating_map(
            await self.repository.rating_summaries(
                [item.id for item in page_items]
            )
        )
        for item in page_items:
            summary = ratings.get(item.id) or {}
            item.rating = summary.get("rating")
            item.rating_count = int(summary.get("rating_count") or 0)
            item.rating_samples = summary.get(
                "rating_samples"
            ) or _parse_samples(None)
        return MarketplaceListResponse(
            items=page_items,
            total=total,
            page=page,
            limit=limit,
        )

    async def get(
        self, product_id: str, estate_id: str
    ) -> MarketplaceDetailResponse:
        """Return one product with child tiers, prices, and grant status."""
        product = await self.repository.get_product(product_id)
        catalog, prices, currency, grants = await self._catalog(estate_id)
        rating_row = (
            _rating_map(
                await self.repository.rating_summaries([product_id])
            ).get(product_id)
            or {}
        )

        tiers: list[MarketplaceTier] = []
        for i, entry in enumerate(_tier_entries(product.get("tiers"))):
            fid = str(entry.get("ai_feature_id") or "")
            if not fid:
                continue
            feature = catalog.get(fid) or {}
            grant = grants.get(fid)
            tiers.append(
                MarketplaceTier(
                    tier=str(entry.get("tier") or f"tier_{i + 1}"),
                    ai_feature_id=fid,
                    feature_key=feature.get("feature_key"),
                    name=feature.get("name"),
                    description=feature.get("description"),
                    is_free=bool(feature.get("is_free")),
                    price=prices.get(fid),
                    currency_code=currency if fid in prices else None,
                    status=_tier_status(grant),
                    is_installed=bool(grant and grant.get("is_installed")),
                )
            )

        return MarketplaceDetailResponse(
            id=str(product["id"]),
            name=product["name"],
            category=product["category"],
            description=product.get("description"),
            rating=rating_row.get("rating"),
            rating_count=int(rating_row.get("rating_count") or 0),
            rating_samples=rating_row.get("rating_samples")
            or _parse_samples(None),
            tiers=tiers,
            display_picture_url=product.get("display_picture_path"),
            video_url=product.get("explanatory_video_path"),
        )

    async def rate(
        self,
        product_id: str,
        user_id: str,
        score: int,
        comment: str | None = None,
    ) -> RatingResponse:
        """Upsert the user's rating and return it with the product summary."""
        await self.repository.get_product(product_id)
        existing = await self.repository.search_rating(
            feature_id=product_id, user_id=user_id
        )
        if existing:
            saved = await self.repository.update_rating(
                str(existing["id"]), score, comment
            )
            rating_row = {
                **existing,
                **saved,
                "score": score,
                "comment": (
                    comment if comment is not None else existing.get("comment")
                ),
            }
        else:
            saved = await self.repository.create_rating(
                feature_id=product_id,
                user_id=user_id,
                score=score,
                comment=comment,
            )
            rating_row = {
                **saved,
                "user_id": user_id,
                "score": score,
                "comment": comment,
            }
        summary = (
            _rating_map(
                await self.repository.rating_summaries([product_id])
            ).get(product_id)
            or {}
        )
        return RatingResponse(
            id=product_id,
            rating=summary.get("rating"),
            rating_count=int(summary.get("rating_count") or 0),
            rating_samples=summary.get("rating_samples")
            or _parse_samples(None),
            user_rating=_user_rating(
                rating_row,
                user_id=user_id,
                score=score,
                comment=comment,
            ),
        )

    async def subscribe(
        self,
        product_id: str,
        estate_id: str,
        ai_feature_id: str,
        period_months: int,
    ) -> SubscribeResponse:
        """Install a free child feature, or quote and activate a paid one."""
        product = await self.repository.get_product(product_id)
        allowed = set(_ai_feature_ids(product.get("tiers")))
        if ai_feature_id not in allowed:
            raise HTTPException(
                status_code=400,
                detail="ai_feature_id is not a tier of this feature",
            )
        feature = await self.repository.get_ai_feature(ai_feature_id)
        if not feature:
            raise HTTPException(status_code=404, detail="AI feature not found")
        feature_key = feature["feature_key"]

        quote = None
        if feature.get("is_free"):
            # Free: skip Paystack; install grant immediately.
            activation = await self.repository.install_ai(
                estate_id, feature_key
            )
        else:
            quote = await self.repository.quote_ai(
                estate_id, [feature_key], period_months
            )
            # Paystack sits here: POST revenue-service
            # /api/v1/checkout/initialize with the quote (amount, email,
            # metadata: estate_id, feature_key, period_months). Return
            # authorization_url to the client and stop — do not activate yet.
            activation = await self.repository.activate_ai(
                estate_id, [feature_key], period_months
            )
            # Paystack: activate_ai moves to charge.success on
            # revenue-service POST /api/v1/webhooks/paystack, after verify.
        return SubscribeResponse(
            estate_id=estate_id,
            ai_feature_id=ai_feature_id,
            feature_key=feature_key,
            quote=quote,
            activation=activation,
        )

    async def stream_picture(self, gcs_path: str) -> dict[str, Any]:
        """Fetch display picture bytes from db-service by GCS object path."""
        content, media_type = await self.repository.get_picture_bytes(gcs_path)
        return {
            "media_type": media_type,
            "filename": "picture",
            "content": content,
        }
