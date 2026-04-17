"""Drawing extraction API routes."""
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import Optional
from app.services.document_parser import get_file_text, is_image_file, pdf_to_images
from app.ai import get_ai_provider

router = APIRouter()
logger = logging.getLogger(__name__)


def _derive_member_types(result) -> list[str]:
    if getattr(result, "member_types", None):
        return result.member_types

    member_types = {
        dimension.section_type
        for dimension in getattr(result, "dimensions", [])
        if getattr(dimension, "section_type", None)
    }
    member_types.update(
        element.section_type
        for element in getattr(result, "structural_elements", [])
        if getattr(element, "section_type", None)
    )
    return sorted(member_types)


def _result_score(result) -> int:
    return (
        len(getattr(result, "structural_elements", []) or []) * 5
        + len(getattr(result, "dimensions", []) or []) * 3
        + len(getattr(result, "bolts_and_plates", []) or []) * 2
        + len(getattr(result, "member_types", []) or [])
        + (3 if getattr(result, "drawing_metadata", None) and getattr(result.drawing_metadata, "drawing_number", None) else 0)
    )


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
        if file.filename.lower().endswith(".pdf"):
            text = get_file_text(file_bytes, file.filename, file.content_type)
            text_result = None
            vision_result = None

            # Only bother with text extraction if there's meaningful text (> 200 chars)
            if len(text.strip()) > 200:
                logger.info(f"Extracting PDF text for {file.filename} ({len(text)} chars)")
                text_result = await ai.extract_from_document(
                    text.encode("utf-8"), file.content_type or "", file.filename, additional_context
                )

            vision_bytes = pdf_to_images(file_bytes)
            if vision_bytes and (text_result is None or _result_score(text_result) == 0):
                logger.info(f"Using vision extraction for PDF {file.filename} ({len(vision_bytes)} pages)")
                vision_result = await ai.extract_from_image(vision_bytes, file.filename, additional_context)

            if text_result and vision_result:
                result = text_result if _result_score(text_result) >= _result_score(vision_result) else vision_result
            elif text_result:
                result = text_result
            elif vision_result:
                result = vision_result
            else:
                raise HTTPException(status_code=422, detail="Could not extract readable text or images from the PDF")
        elif is_image_file(file.filename):
            result = await ai.extract_from_image(file_bytes, file.filename, additional_context)
        else:
            text = get_file_text(file_bytes, file.filename, file.content_type)
            result = await ai.extract_from_document(
                text.encode("utf-8"), file.content_type or "", file.filename, additional_context
            )
        member_types = _derive_member_types(result)
        return {
            "drawing_metadata": result.drawing_metadata.model_dump() if result.drawing_metadata else None,
            "structural_elements": [element.model_dump() for element in result.structural_elements],
            "bolts_and_plates": [item.model_dump() for item in result.bolts_and_plates],
            "surface_treatment": result.surface_treatment.model_dump() if result.surface_treatment else None,
            "weight_summary": result.weight_summary.model_dump() if result.weight_summary else None,
            "cost_estimation_inputs": result.cost_estimation_inputs.model_dump() if result.cost_estimation_inputs else None,
            "ambiguities": [item.model_dump() for item in result.ambiguities],
            "dimensions": [d.model_dump() for d in result.dimensions],
            "summary": result.summary,
            "overall_confidence": result.overall_confidence,
            "flags": [f.model_dump() for f in result.flags],
            "member_types": member_types,
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
