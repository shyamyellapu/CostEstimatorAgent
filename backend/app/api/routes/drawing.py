"""Drawing extraction API routes."""
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from typing import List, Optional
from app.services.document_parser import get_file_text, is_image_file, pdf_to_images
from app.ai import get_ai_provider
from app.config import settings

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
    files: List[UploadFile] = File(...),
    additional_context: Optional[str] = Form(None)
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    ai = get_ai_provider()
    try:
        batch = []
        for f in files:
            if not f.filename:
                continue
            fb = await f.read()
            batch.append({"bytes": fb, "filename": f.filename, "file_type": f.content_type or ""})
        if not batch:
            raise HTTPException(status_code=400, detail="No valid files provided")

        result = await ai.extract_from_multiple_files(batch, additional_context)
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
            "flags": [flag.model_dump() for flag in result.flags],
            "member_types": member_types,
            "material_references": result.material_references,
            "annotations": result.annotations,
            "fabrication_notes": result.fabrication_notes,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Drawing extract error: {e}")
        err_msg = str(e)
        if "invalid_api_key" in err_msg.lower() or "api_key" in err_msg.lower():
            raise HTTPException(status_code=401, detail="Invalid AI Provider API Key. Please check your .env file.")
        if "model_not_found" in err_msg.lower() or "not found" in err_msg.lower():
            raise HTTPException(status_code=404, detail=f"Model not found or no access: {err_msg}")
        raise HTTPException(status_code=500, detail=err_msg)
