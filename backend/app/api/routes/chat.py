"""Chat API routes."""
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.models import ChatHistory
from app.ai import get_ai_provider

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    job_id: Optional[str] = None
    session_id: Optional[str] = None


@router.post("")
async def chat(request: ChatRequest, db: AsyncSession = Depends(db_session)):
    """Send a chat message and get AI response."""
    job_context = None
    job_uuid = None

    job_uuid = request.job_id

    ai = get_ai_provider()
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        response = await ai.chat(messages=messages, context=job_context)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Save to history
    session_id = request.session_id or str(uuid.uuid4())
    for msg in request.messages:
        db.add(ChatHistory(
            job_id=job_uuid,
            session_id=session_id,
            role=msg.role,
            content=msg.content,
        ))
    db.add(ChatHistory(
        job_id=job_uuid,
        session_id=session_id,
        role="assistant",
        content=response.content,
        model_used=response.model_used,
    ))
    await db.commit()

    return {
        "response": response.content,
        "model": response.model_used,
        "session_id": session_id,
    }


@router.get("/history")
async def get_chat_history(
    session_id: Optional[str] = None,
    job_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(db_session)
):
    query = select(ChatHistory).order_by(ChatHistory.created_at.asc()).limit(limit)
    if session_id:
        query = query.where(ChatHistory.session_id == session_id)
    if job_id:
        query = query.where(ChatHistory.job_id == job_id)
    result = await db.execute(query)
    msgs = result.scalars().all()
    return [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in msgs]
