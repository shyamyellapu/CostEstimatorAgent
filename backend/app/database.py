"""Database engine and session factory for PostgreSQL."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


if not settings.database_url.startswith("postgresql+asyncpg://"):
    raise ValueError("DATABASE_URL must be PostgreSQL asyncpg URL")

# PostgreSQL engine configuration
engine_config = {
    "echo": False,
    "pool_size": settings.db_pool_size,
    "max_overflow": settings.db_max_overflow,
    "pool_timeout": settings.db_pool_timeout,
    "pool_recycle": settings.db_pool_recycle,
    "pool_pre_ping": True,
}

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


async def check_database_connection() -> dict:
    """Verify PostgreSQL connectivity and return connection metadata."""
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        result.scalar_one()

    return {
        "database": "connected",
        "status": "healthy",
        "driver": "asyncpg",
        "pool_status": engine.pool.status() if hasattr(engine.pool, "status") else "unavailable",
    }
