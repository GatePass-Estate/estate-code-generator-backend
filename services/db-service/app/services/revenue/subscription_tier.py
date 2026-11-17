import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.revenue.subscription_tier import (
    SubscriptionTierRepository as Repository,
)
from app.schemas.revenue.subscription_tier import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)
from app.services.revenue.tier_feature_availability import (
    build_tier_feature_availability,
    load_feature_catalog_rows,
    tier_dict_from_response_fields,
)

logger = logging.getLogger(__name__)


class SubscriptionTierService:
    """
    Service class for subscription_tier table.
    """

    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = Repository(db_session)
        self._session = db_session
        self._catalog_cache: tuple[list, list] | None = None

    async def _catalog_rows(self) -> tuple[list, list]:
        if self._catalog_cache is None:
            self._catalog_cache = await load_feature_catalog_rows(
                self._session
            )
        return self._catalog_cache

    async def _enrich_tier_response(self, item: GetResponse) -> GetResponse:
        service_rows, ai_rows = await self._catalog_rows()
        tier = tier_dict_from_response_fields(
            slug=item.slug,
            is_custom=item.is_custom,
            entitlements=item.entitlements,
            included_ai_features=item.included_ai_features,
        )
        free, paid, ai = build_tier_feature_availability(
            tier,
            service_catalog_rows=service_rows,
            ai_feature_rows=ai_rows,
        )
        return item.model_copy(
            update={
                "free_features": free,
                "paid_non_ai_features": paid,
                "paid_ai_features": ai,
            }
        )

    async def create(self, request: CreateRequest) -> CreateResponse:
        return await self.repository.create(request=request)

    async def delete(self, id: str) -> DeleteResponse:
        return await self.repository.delete(id=id)

    async def get(self, id: str) -> GetResponse:
        item = await self.repository.get(id=id)
        return await self._enrich_tier_response(item)

    async def update(self, id: str, request: UpdateRequest) -> UpdateResponse:
        return await self.repository.update(id=id, request=request)

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        result = await self.repository.list(page=page, limit=limit)
        enriched = [
            await self._enrich_tier_response(item) for item in result.items
        ]
        return result.model_copy(update={"items": enriched})

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        result = await self.repository.search(
            request=request, page=page, limit=limit
        )
        enriched = [
            await self._enrich_tier_response(item) for item in result.items
        ]
        return result.model_copy(update={"items": enriched})
