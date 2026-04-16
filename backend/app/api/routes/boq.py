"""BOQ Parser API routes."""
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import Optional
from app.services.document_parser import get_file_text
from app.ai import get_ai_provider

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/parse")
async def parse_boq(
    file: UploadFile = File(...),
    additional_context: Optional[str] = Form(None)
):
    """Parse a BOQ file and extract structured line items."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File required")
    file_bytes = await file.read()
    text = get_file_text(file_bytes, file.filename, file.content_type)
    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from BOQ file")
    ai = get_ai_provider()
    try:
        result = await ai.parse_boq(text, additional_context)
        return {
            "dimensions": [d.model_dump() for d in result.dimensions],
            "summary": result.summary,
            "overall_confidence": result.overall_confidence,
            "flags": [f.model_dump() for f in result.flags],
            "member_types": result.member_types,
        }
    except Exception as e:
        logger.error(f"BOQ parse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
