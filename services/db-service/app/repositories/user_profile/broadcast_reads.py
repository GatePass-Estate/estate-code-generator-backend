import logging
from typing import List
from uuid import UUID

from pydantic import UUID4
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.models import BroadcastReads as TableModel
from app.models import Broadcasts as BroadcastsModel
from app.schemas.user_profile.broadcast_reads import (
    CreateRequest,
    CreateResponse,
    DismissAllRequest,
    DismissRequest,
    GetResponse,
    ListResponse,
    SearchRequest,
)
from app.schemas.user_profile.notifications import UnreadCountResponse

logger = logging.getLogger(__name__)


class BroadcastReadsRepository:
    """Repository for the broadcast_reads table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, request: CreateRequest) -> CreateResponse:
        """
        Insert a broadcast read record, silently ignoring duplicates.

        Arguments:
            request: broadcast_id + user_id to mark as read.

        Returns:
            The created (or existing) record's id and created_at.
        """
        try:
            stmt = (
                pg_insert(TableModel)
                .values(
                    broadcast_id=request.broadcast_id,
                    user_id=request.user_id,
                )
                .on_conflict_do_nothing(
                    constraint="uq_broadcast_reads_broadcast_user"
                )
                .returning(TableModel.id, TableModel.created_at)
            )
            result = await self.session.execute(stmt)
            row = result.first()
            if row:
                return CreateResponse(id=row.id, created_at=row.created_at)
            # Already existed — fetch the existing row
            existing = await self.session.scalar(
                select(TableModel).where(
                    TableModel.broadcast_id == request.broadcast_id,
                    TableModel.user_id == request.user_id,
                )
            )
            return CreateResponse.model_validate(existing.__dict__)
        except SQLAlchemyError as e:
            message = "Database error upserting broadcast read"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def dismiss(self, request: DismissRequest) -> CreateResponse:
        """
        Mark a broadcast as dismissed for a user (upsert + set is_dismissed).

        Arguments:
            request: broadcast_id + user_id to dismiss.

        Returns:
            The upserted record's id and created_at.
        """
        try:
            stmt = (
                pg_insert(TableModel)
                .values(
                    broadcast_id=request.broadcast_id,
                    user_id=request.user_id,
                    is_dismissed=True,
                )
                .on_conflict_do_update(
                    constraint="uq_broadcast_reads_broadcast_user",
                    set_={"is_dismissed": True},
                )
                .returning(TableModel.id, TableModel.created_at)
            )
            result = await self.session.execute(stmt)
            row = result.first()
            return CreateResponse(id=row.id, created_at=row.created_at)
        except SQLAlchemyError as e:
            message = "Database error dismissing broadcast"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def dismiss_all(self, request: DismissAllRequest) -> int:
        """
        Dismiss all undismissed BROADCAST-category broadcasts for a user
        within their estate (does not affect AD-category broadcasts).

        Returns the number of rows affected.
        """
        try:
            # Subquery: IDs of BROADCAST-category broadcasts in scope
            broadcast_subq = select(BroadcastsModel.id).where(
                BroadcastsModel.is_deleted == False,  # noqa E712
                BroadcastsModel.category == "BROADCAST",
                (
                    (BroadcastsModel.estate_id == request.estate_id)
                    | (BroadcastsModel.estate_id.is_(None))
                ),
            )

            # Upsert all matching broadcasts as dismissed
            # First update existing rows
            update_stmt = (
                update(TableModel)
                .where(
                    TableModel.user_id == request.user_id,
                    TableModel.broadcast_id.in_(broadcast_subq),
                    TableModel.is_dismissed == False,  # noqa E712
                )
                .values(is_dismissed=True)
            )
            result = await self.session.execute(update_stmt)
            updated = result.rowcount

            # Insert rows for broadcasts not yet in broadcast_reads
            already_read_subq = select(TableModel.broadcast_id).where(
                TableModel.user_id == request.user_id
            )
            missing_subq = select(BroadcastsModel.id).where(
                BroadcastsModel.is_deleted == False,  # noqa E712
                BroadcastsModel.category == "BROADCAST",
                (
                    (BroadcastsModel.estate_id == request.estate_id)
                    | (BroadcastsModel.estate_id.is_(None))
                ),
                BroadcastsModel.id.not_in(already_read_subq),
            )
            missing_ids = (
                (await self.session.execute(missing_subq)).scalars().all()
            )
            for bid in missing_ids:
                self.session.add(
                    TableModel(
                        broadcast_id=bid,
                        user_id=request.user_id,
                        is_dismissed=True,
                    )
                )
            await self.session.flush()
            return updated + len(missing_ids)
        except SQLAlchemyError as e:
            message = "Database error dismissing all broadcasts"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def get_read_ids_for_user(
        self, user_id: UUID4, broadcast_ids: List[UUID]
    ) -> List[UUID]:
        """
        Return the subset of broadcast_ids that the user has already read.
        """
        if not broadcast_ids:
            return []
        try:
            result = await self.session.execute(
                select(TableModel.broadcast_id).where(
                    TableModel.user_id == user_id,
                    TableModel.broadcast_id.in_(broadcast_ids),
                )
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            message = "Database error fetching read broadcast ids"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def unread_count(
        self, user_id: UUID4, estate_id: UUID4, roles: List[str]
    ) -> UnreadCountResponse:
        """
        Count broadcasts visible to this user that are unread and not
        dismissed, and have not yet expired.

        A broadcast is visible when:
          - Its estate_id matches OR is NULL (root/platform-wide)
          - Its audience array overlaps the user's roles
          - It is not soft-deleted
          - It has not expired (expires_at IS NULL or > now)
          - It has not been read OR dismissed by this user
        """
        try:
            dismissed_or_read_subq = select(TableModel.broadcast_id).where(
                TableModel.user_id == user_id
            )
            query = (
                select(func.count())
                .select_from(BroadcastsModel)
                .where(
                    BroadcastsModel.is_deleted == False,  # noqa E712
                    BroadcastsModel.status == True,  # noqa E712
                    (
                        (BroadcastsModel.estate_id == estate_id)
                        | (BroadcastsModel.estate_id.is_(None))
                    ),
                    BroadcastsModel.audience.overlap(roles),
                    BroadcastsModel.id.not_in(dismissed_or_read_subq),
                    (
                        BroadcastsModel.expires_at.is_(None)
                        | (BroadcastsModel.expires_at > func.now())
                    ),
                )
            )
            count = await self.session.scalar(query)
            return UnreadCountResponse(count=count or 0)
        except SQLAlchemyError as e:
            message = "Database error counting unread broadcasts"
            logger.exception(message)
            raise DatabaseError(message) from e

    async def search(self, request: SearchRequest) -> ListResponse:
        """
        List broadcast read records filtered by broadcast_id and/or user_id.
        """
        try:
            query = select(TableModel).where(
                TableModel.is_deleted == False  # noqa E712
            )
            if request.broadcast_id is not None:
                query = query.where(
                    TableModel.broadcast_id == request.broadcast_id
                )
            if request.user_id is not None:
                query = query.where(TableModel.user_id == request.user_id)

            count_query = select(func.count()).select_from(query.subquery())
            total = await self.session.scalar(count_query)

            paginated = (
                query.order_by(TableModel.created_at.desc())
                .limit(request.limit)
                .offset((request.page - 1) * request.limit)
            )
            records = (
                (await self.session.execute(paginated))
                .unique()
                .scalars()
                .all()
            )
            return ListResponse(
                items=[
                    GetResponse.model_validate(r, from_attributes=True)
                    for r in records
                ],
                total=total,
                page=request.page,
                limit=request.limit,
            )
        except SQLAlchemyError as e:
            message = "Database error searching broadcast reads"
            logger.exception(message)
            raise DatabaseError(message) from e
