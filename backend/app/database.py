"""Database engine and session factory."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

from app.config import settings


class Base(DeclarativeBase):
    pass


# Database engine configuration
engine_config = {
    "echo": settings.debug,
}

# Optimize connection pooling for PostgreSQL
if "postgresql" in settings.database_url:
    engine_config.update({
        "pool_size": settings.db_pool_size,  # Max connections in pool
        "max_overflow": settings.db_max_overflow,  # Additional connections beyond pool_size
        "pool_timeout": settings.db_pool_timeout,  # Timeout for getting connection from pool
        "pool_recycle": settings.db_pool_recycle,  # Recycle connections after 1 hour
        "pool_pre_ping": True,  # Verify connections before using
        "poolclass": AsyncAdaptedQueuePool,
    })
elif "sqlite" in settings.database_url:
    # SQLite-specific settings
    engine_config.update({
        "connect_args": {"check_same_thread": False},
    })

engine = create_async_engine(
    settings.database_url,
    **engine_config
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
