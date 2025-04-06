import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import text

from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class AsyncDBSession:
    def __init__(self) -> None:
        self._engine = None
        self._session = None

    async def init(self):
        echo = settings.ENV in ["local", "develop"]
        self._engine = create_async_engine(
            settings.DB_CONFIG,
            echo=echo,
            future=True,
            pool_size=5,
            max_overflow=10,
        )

    async def close(self):
        if self._engine:
            await self._engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self._engine:
            await self.init()

        if not await self._ensure_connection(self._engine):
            await self.close()
            await self.init()

        async_session = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                logger.exception("Error in the session: %s", str(session.info))
                await session.rollback()
                raise

    async def _ensure_connection(self, engine):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True
        except DBAPIError:
            logger.exception("Error in connection")
            return False

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session() as session:
            yield session


db_session = AsyncDBSession()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session.

    Returns:
        AsyncGenerator[AsyncSession, None]: Database session
    """
    async with db_session.session() as session:
        yield session
