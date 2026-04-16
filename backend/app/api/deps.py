"""Shared FastAPI dependencies."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.ai import get_ai_provider


async def db_session(db: AsyncSession = Depends(get_db)):
    return db
