from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import Select, String, cast, func, select
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError, NotFoundError, ValidationError
from app.models import AiMarketplaceFeatureRating as TableModel
from app.schemas.revenue.ai_marketplace_feature_rating import (
    CreateRequest,
    CreateResponse,
    DeleteResponse,
    GetResponse,
    ListResponse,
    RatingSample,
    RatingSummaryItem,
    RatingSummaryResponse,
    SearchRequest,
    UpdateRequest,
    UpdateResponse,
)

logger = logging.getLogger(__name__)

_SAMPLES_PER_SCORE = 5


class AiMarketplaceFeatureRatingRepository:
    """Repository to operate on ai_marketplace_feature_rating table."""

    def __init__(self, session: AsyncSession) -> None:
        """Store the async SQLAlchemy session."""
        self.session: AsyncSession = session

    async def _getitem(
        self,
        session: AsyncSession,
        **kwargs,
    ) -> TableModel:
        """Load a non-deleted row by id, or raise NotFoundError / DatabaseError."""
        id = kwargs.get("id", None)
        query = select(TableModel).where(
            TableModel.is_deleted == False,  # noqa E712
        )
        if isinstance(id, UUID):
            query = query.where(TableModel.id == id)
        else:
            message = "Please specify a valid ID %s" % id
            logger.exception(message)
            raise DatabaseError(message)

        try:
            result = await session.execute(query)
            return result.unique().scalar_one()
        except NoResultFound as e:
            if id is not None:
                message = "Record with ID %s not found" % id
                logger.exception(message)
                raise NotFoundError(message) from e
            else:
                raise NotFoundError
        except SQLAlchemyError as e:
            message = "Database error in retrieving a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in retrieving a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def _setitem(
        self,
        session: AsyncSession,
        request: TableModel,
    ) -> TableModel:
        """Insert or flush an existing row, then refresh it."""
        try:
            if request.id is None:
                session.add(request)
            await session.flush()
            await session.refresh(request)
            return request
        except SQLAlchemyError as e:
            message = "Database error in creating/updating a record"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in creating/updating a record"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def _list(
        self,
        query: Select,
        order_by: tuple,
        page: int = 1,
        limit: int = 10,
    ) -> ListResponse:
        """Paginate ``query`` and return a ListResponse."""
        if not isinstance(query, Select):
            raise ValidationError(
                "query must be an instance of sqlalchemy.sql.selectable.Select"
            )
        if not isinstance(order_by, tuple):
            raise ValidationError("order_by must be a tuple")

        count_query = select(func.count()).select_from(query.subquery())
        paginated_query = (
            query.order_by(*order_by)
            .limit(limit)
            .offset((page - 1) * limit)
            .distinct()
        )
        try:
            total = await self.session.scalar(count_query)
            records = (
                (await self.session.execute(paginated_query))
                .unique()
                .scalars()
                .all()
            )
            return ListResponse(
                items=[
                    GetResponse.model_validate(record) for record in records
                ],
                total=total,
                page=page,
                limit=limit,
            )
        except SQLAlchemyError as e:
            message = "Database error in retrieving records"
            logger.exception(message)
            raise DatabaseError(message) from e
        except Exception as e:
            message = "Unexpected error in retrieving records"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def create(self, request: CreateRequest) -> CreateResponse:
        """Insert a rating and return its id and created_at."""
        try:
            record = await self._setitem(
                session=self.session,
                request=TableModel(**request.model_dump(exclude_unset=True)),
            )
            created_record = CreateResponse.model_validate(record.__dict__)
            return created_record
        except DatabaseError as e:
            message = "Database error in creating the record"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def delete(self, id: UUID4) -> DeleteResponse:
        """Soft-delete a rating by id."""
        try:
            record = await self._getitem(session=self.session, id=id)
            record.is_deleted = True
            record.deleted_at = datetime.now(tz=timezone.utc)
            await self.session.flush()
            return DeleteResponse.model_validate(record)
        except NoResultFound as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in deleting a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get(self, id: UUID4) -> GetResponse:
        """Return a rating by id."""
        try:
            record = await self._getitem(session=self.session, id=id)
            return GetResponse.model_validate(record, from_attributes=True)
        except NotFoundError as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in getting a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def update(
        self, id: UUID4, request: UpdateRequest
    ) -> UpdateResponse:
        """Patch a rating by id."""
        try:
            record = await self._getitem(session=self.session, id=id)
            record.update(**request.model_dump(exclude_unset=True))
            record = await self._setitem(session=self.session, request=record)
            return UpdateResponse.model_validate(record)
        except NotFoundError as e:
            message = "Record with ID %s not found" % id
            logger.exception(message)
            raise NotFoundError(message) from e
        except DatabaseError as e:
            message = "Database error in updating a record with ID %s" % id
            logger.exception(message)
            raise DatabaseError(message) from e

    async def list(self, page: int = 1, limit: int = 20) -> ListResponse:
        """Return a paginated list of non-deleted ratings."""
        query = select(TableModel).where(
            (
                TableModel.is_deleted == False  # noqa E712
            )
        )
        order_by = (TableModel.created_at.desc(),)
        try:
            return await self._list(
                query=query, order_by=order_by, page=page, limit=limit
            )
        except DatabaseError as e:
            message = "Database error in getting a list of items"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def search(
        self, request: SearchRequest, page: int = 1, limit: int = 20
    ) -> ListResponse:
        """Filter ratings and return a paginated list."""
        query = select(TableModel).where(
            TableModel.is_deleted == False  # noqa E712
        )

        for key, info in request.model_fields.items():
            if getattr(request, key) is None:
                continue
            if key in ["from_date", "to_date"]:
                query = (
                    query.where(TableModel.created_at >= request.from_date)
                    if key == "from_date"
                    else query.where(TableModel.created_at <= request.to_date)
                )
            elif hasattr(TableModel, key):
                field_value = getattr(request, key)
                column = getattr(TableModel, key)

                if hasattr(field_value, "value"):
                    field_value = field_value.value

                if isinstance(field_value, str):
                    query = query.where(
                        func.lower(cast(column, String)) == field_value.lower()
                    )
                else:
                    query = query.where(column == field_value)

        order_by = (TableModel.created_at.desc(),)
        try:
            return await self._list(
                query=query,
                order_by=order_by,
                page=page,
                limit=limit,
            )
        except DatabaseError as e:
            message = "Database error in searching for items"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def summary(self, feature_ids: list[UUID]) -> RatingSummaryResponse:
        """Average scores and up to 5 newest samples per star for each feature."""
        if not feature_ids:
            return RatingSummaryResponse(items=[])
        try:
            agg_rows = (
                await self.session.execute(
                    select(
                        TableModel.ai_marketplace_feature_id,
                        func.avg(TableModel.score),
                        func.count(),
                    )
                    .where(
                        TableModel.is_deleted == False,  # noqa E712
                        TableModel.ai_marketplace_feature_id.in_(feature_ids),
                    )
                    .group_by(TableModel.ai_marketplace_feature_id)
                )
            ).all()
            rn = (
                func.row_number()
                .over(
                    partition_by=(
                        TableModel.ai_marketplace_feature_id,
                        TableModel.score,
                    ),
                    order_by=TableModel.created_at.desc(),
                )
                .label("rn")
            )
            ranked = (
                select(
                    TableModel.user_id,
                    TableModel.ai_marketplace_feature_id,
                    TableModel.score,
                    TableModel.comment,
                    TableModel.created_at,
                    rn,
                )
                .where(
                    TableModel.is_deleted == False,  # noqa E712
                    TableModel.ai_marketplace_feature_id.in_(feature_ids),
                )
                .subquery()
            )
            sample_rows = (
                await self.session.execute(
                    select(
                        ranked.c.user_id,
                        ranked.c.ai_marketplace_feature_id,
                        ranked.c.score,
                        ranked.c.comment,
                        ranked.c.created_at,
                    ).where(ranked.c.rn <= _SAMPLES_PER_SCORE)
                )
            ).all()
        except SQLAlchemyError as e:
            message = "Database error in rating summary"
            logger.exception(message)
            raise DatabaseError(message) from e

        by_id: dict[str, RatingSummaryItem] = {}
        for fid in feature_ids:
            key = str(fid)
            by_id[key] = RatingSummaryItem(
                ai_marketplace_feature_id=key,
                samples={str(score): [] for score in range(1, 6)},
            )
        for fid, avg, count in agg_rows:
            key = str(fid)
            item = by_id[key]
            item.rating = round(float(avg), 1) if avg is not None else None
            item.rating_count = int(count)
        for user_id, fid, score, comment, created_at in sample_rows:
            bucket = str(int(score))
            by_id[str(fid)].samples.setdefault(bucket, []).append(
                RatingSample(
                    user_id=str(user_id),
                    score=int(score),
                    comment=comment,
                    created_at=created_at,
                )
            )
        return RatingSummaryResponse(items=list(by_id.values()))
