"""Database connection and session management."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bids_server.config import settings

logger = logging.getLogger(__name__)

engine_kwargs = {
    "echo": settings.database_echo,
    "pool_size": 20,
    "max_overflow": 10,
}

engine = create_async_engine(settings.database_url, **engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """Dependency that yields a session and commits on success."""
    session = async_session()
    try:
        yield session
        await session.commit()
    except Exception:
        logger.error("Database session error", exc_info=True)
        await session.rollback()
        raise
    finally:
        await session.close()
