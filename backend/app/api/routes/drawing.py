"""Drawing extraction API routes."""
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import Optional
from app.services.document_parser import get_file_text, is_image_file, pdf_page_to_image
from app.ai import get_ai_provider

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/extract")
async def extract_drawing(
    file: UploadFile = File(...),
    additional_context: Optional[str] = Form(None)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File required")
    file_bytes = await file.read()
    ai = get_ai_provider()
    try:
        if is_image_file(file.filename) or file.filename.lower().endswith(".pdf"):
            # For drawings, we always prefer Vision AI today.
            # If it's a PDF, convert first page to image first.
            if file.filename.lower().endswith(".pdf"):
                logger.info(f"Converting PDF {file.filename} to image for Vision AI")
                vision_bytes = pdf_page_to_image(file_bytes)
                if not vision_bytes:
                    # Fallback to text if conversion fails
                    logger.warning("PDF conversion failed, falling back to text extraction")
                    text = get_file_text(file_bytes, file.filename, file.content_type)
                    result = await ai.extract_from_document(
                        text.encode("utf-8"), file.content_type or "", file.filename, additional_context
                    )
                else:
                    result = await ai.extract_from_image(vision_bytes, file.filename, additional_context)
            else:
                result = await ai.extract_from_image(file_bytes, file.filename, additional_context)
        else:
            text = get_file_text(file_bytes, file.filename, file.content_type)
            result = await ai.extract_from_document(
                text.encode("utf-8"), file.content_type or "", file.filename, additional_context
            )
        return {
            "dimensions": [d.model_dump() for d in result.dimensions],
            "summary": result.summary,
            "overall_confidence": result.overall_confidence,
            "flags": [f.model_dump() for f in result.flags],
            "member_types": result.member_types,
            "material_references": result.material_references,
            "annotations": result.annotations,
            "fabrication_notes": result.fabrication_notes,
        }
    except Exception as e:
        logger.error(f"Drawing extract error: {e}")
        # Identify specific Groq errors for better UX
        err_msg = str(e)
        if "invalid_api_key" in err_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid Groq API Key. Please check your .env file.")
        if "model_not_found" in err_msg.lower() or "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=f"Model not found or no access: {err_msg}")
        raise HTTPException(status_code=500, detail=err_msg)
