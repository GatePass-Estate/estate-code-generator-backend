"""HTTP routes for the estate-scoped AI marketplace."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.auth import get_current_user
from app.libs.http_handler import AsyncHttpHandler, get_http_handler
from app.repositories.ai_market_place import AiMarketPlaceRepository
from app.schemas.ai_market_place import (
    MarketplaceDetailResponse,
    MarketplaceListResponse,
    PurchaseStatus,
    RatingRequest,
    RatingResponse,
    SubscribeRequest,
    SubscribeResponse,
)
from app.services.ai_market_place import AiMarketPlaceService

router = APIRouter()


def get_service(
    http_client: AsyncHttpHandler = Depends(get_http_handler),
) -> AiMarketPlaceService:
    """Build an AiMarketPlaceService for the current request."""
    return AiMarketPlaceService(AiMarketPlaceRepository(http_client))


def _estate_id(current_user: dict) -> str:
    """Return the caller's estate id, or 400 if the user has none."""
    estate_id = current_user.get("estate_id")
    if not estate_id:
        raise HTTPException(status_code=400, detail="User has no estate")
    return str(estate_id)


@router.get("", response_model=MarketplaceListResponse)
async def list_features(
    purchase_status: list[PurchaseStatus] | None = Query(None),
    category: list[str] | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    service: AiMarketPlaceService = Depends(get_service),
) -> MarketplaceListResponse:
    """List marketplace products for the caller's estate.

    Optional ``purchase_status`` and ``category`` are repeated query params.
    Unpurchased items include a starting price; ratings are attached per page.
    """
    return await service.list(
        _estate_id(current_user),
        purchase_status=purchase_status,
        category=category,
        page=page,
        limit=limit,
    )


@router.get("/picture")
async def view_feature_picture(
    path: str = Query(..., min_length=1, description="GCS object path"),
    current_user: dict = Depends(get_current_user),
    service: AiMarketPlaceService = Depends(get_service),
):
    """Stream a display picture by GCS object path. JWT only; no extra RBAC."""
    result = await service.stream_picture(path)
    return Response(
        content=result["content"],
        media_type=result["media_type"],
        headers={
            "Content-Disposition": f'inline; filename="{result["filename"]}"',
            "Cache-Control": "private, no-store",
            "Content-Length": str(len(result["content"])),
        },
    )


@router.get("/{id}", response_model=MarketplaceDetailResponse)
async def get_feature(
    id: str,
    current_user: dict = Depends(get_current_user),
    service: AiMarketPlaceService = Depends(get_service),
) -> MarketplaceDetailResponse:
    """Return one marketplace product with child tiers and estate grant status."""
    return await service.get(id, _estate_id(current_user))


@router.post("/{id}/rating", response_model=RatingResponse)
async def rate_feature(
    id: str,
    request: RatingRequest,
    current_user: dict = Depends(get_current_user),
    service: AiMarketPlaceService = Depends(get_service),
) -> RatingResponse:
    """Create or update the caller's rating and return it with the summary."""
    return await service.rate(
        id, str(current_user["id"]), request.score, request.comment
    )


@router.post("/{id}/subscribe", response_model=SubscribeResponse)
async def subscribe_feature(
    id: str,
    request: SubscribeRequest,
    current_user: dict = Depends(get_current_user),
    service: AiMarketPlaceService = Depends(get_service),
) -> SubscribeResponse:
    """Subscribe the estate to a child ``ai_feature`` tier of this product.

    Free features install immediately. Paid features quote then activate via
    revenue-service (Paystack initialize is still stubbed).
    """
    return await service.subscribe(
        id,
        _estate_id(current_user),
        request.ai_feature_id,
        request.period_months,
    )
