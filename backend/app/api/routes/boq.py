"""BOQ Parser API routes."""
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import Optional
from app.services.document_parser import get_file_text
from app.ai import get_ai_provider

router = APIRouter()
logger = logging.getLogger(__name__)


def _derive_member_types(result) -> list[str]:
    if getattr(result, "member_types", None):
        return result.member_types

    return sorted(
        {
            dimension.section_type
            for dimension in getattr(result, "dimensions", [])
            if getattr(dimension, "section_type", None)
        }
    )


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
        member_types = _derive_member_types(result)
        return {
            "dimensions": [d.model_dump() for d in result.dimensions],
            "summary": result.summary,
            "overall_confidence": result.overall_confidence,
            "flags": [f.model_dump() for f in result.flags],
            "member_types": member_types,
        }
    except Exception as e:
        logger.error(f"BOQ parse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
