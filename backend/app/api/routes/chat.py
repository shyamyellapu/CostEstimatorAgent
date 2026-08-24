"""Chat API routes."""
import io
import mimetypes
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.models import ChatHistory
from app.ai import get_ai_provider
from app.services.excel_generator import excel_generator

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024        # 50 MB per file
MAX_TOTAL_FILE_SIZE = 50 * 1024 * 1024  # 50 MB combined across all attachments
MAX_FILES = 10
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
_IMAGE_MIME = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "webp": "image/webp",
}
# Non-image files passed through to the provider as `input_file` items — text is
# extracted server-side by OpenAI, no local parsing/conversion happens here.
_DOCUMENT_EXTENSIONS = {
    "txt", "md", "json", "html", "xml", "csv", "tsv",
    "xls", "xlsx", "doc", "docx", "rtf", "odt", "ppt", "pptx",
}


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


@router.post("/inference")
async def chat_inference(
    prompt: str = Form(...),
    files: List[UploadFile] = File(default=[]),
    session_id: Optional[str] = Form(None),
    previous_response_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(db_session),
):
    """Raw LLM inference test: a free-form prompt plus optional file attachments
    (PDFs, images, and office/text documents).

    Bypasses the costing-domain system prompt and JSON extraction schemas used
    elsewhere in the app — this is a plain playground call to the configured provider.
    Files are forwarded as raw bytes; no text extraction or page rasterizing happens
    here. Pass `previous_response_id` (from a prior response, when the active
    provider supports it) to continue that conversation natively instead of
    resending earlier files/messages.
    """
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"At most {MAX_FILES} files are allowed")

    images: List[Dict[str, Any]] = []
    pdfs: List[Dict[str, Any]] = []
    documents: List[Dict[str, Any]] = []
    attached_names: List[str] = []
    total_size = 0

    for f in files:
        if not f.filename:
            continue
        fb = await f.read()
        if len(fb) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File '{f.filename}' exceeds 50 MB limit.")
        total_size += len(fb)
        if total_size > MAX_TOTAL_FILE_SIZE:
            raise HTTPException(status_code=413, detail="Combined file size cannot exceed 50 MB")

        attached_names.append(f.filename)
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext in _IMAGE_EXTENSIONS:
            images.append({"bytes": fb, "mime": _IMAGE_MIME[ext]})
        elif ext == "pdf":
            pdfs.append({"bytes": fb, "filename": f.filename})
        elif ext in _DOCUMENT_EXTENSIONS:
            mime = f.content_type or mimetypes.guess_type(f.filename)[0] or "application/octet-stream"
            documents.append({"bytes": fb, "filename": f.filename, "mime": mime})
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type for '{f.filename}'."
            )

    ai = get_ai_provider()
    try:
        response = await ai.chat_with_attachments(
            prompt=prompt,
            images=images or None,
            pdfs=pdfs or None,
            documents=documents or None,
            previous_response_id=previous_response_id,
        )
    except Exception as e:
        logger.error(f"Chat inference error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    session_id = session_id or str(uuid.uuid4())
    user_record = prompt + (f"\n\n[attached: {', '.join(attached_names)}]" if attached_names else "")
    db.add(ChatHistory(session_id=session_id, role="user", content=user_record))
    db.add(ChatHistory(
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
        "response_id": response.response_id,
        "usage": response.usage,
    }


class ExtractionItem(BaseModel):
    description: Optional[str] = None
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    remarks: Optional[str] = None
    rate: Optional[float] = None


class ExportExcelRequest(BaseModel):
    items: List[ExtractionItem]
    customer: Dict[str, Any] = {}


@router.post("/export-excel")
async def export_excel(body: ExportExcelRequest):
    """Fill the Sample Job Costing Sheet template from a Chat-page LLM extraction.

    `"Structural Steel Material"` lands in G23 (keeping the sheet's standard
    rate); items matching a row already in the template (handrails, grating,
    paint) fill that row's quantity and rate; anything else is inserted as a
    new row right after the material block.
    """
    if not body.items:
        raise HTTPException(status_code=400, detail="No items to export")

    try:
        excel_bytes = excel_generator.generate_from_extraction_items(
            [item.model_dump() for item in body.items],
            customer=body.customer,
        )
    except FileNotFoundError as e:
        logger.error(f"Excel template missing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    filename = f"ChatExtraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
