"""
Drawing Costing API routes.

POST /api/drawing-costing/analyse
  - Accepts a PDF upload (max 32 MB)
  - Calls Claude vision API with the structural steel takeoff prompt
  - Returns extraction JSON + computed costing

POST /api/drawing-costing/generate-excel
  - Accepts computed costing + customer fields + markup %
  - Returns the Job Costing Sheet .xlsx as a file download
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.drawing_costing import (
    compute_costing,
    extract_from_pdf,
    generate_excel,
)

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_PDF_SIZE = 32 * 1024 * 1024  # 32 MB


# ---------------------------------------------------------------------------
# POST /analyse
# ---------------------------------------------------------------------------
@router.post("/analyse")
async def analyse_drawing(
    file: UploadFile = File(..., description="Engineering drawing PDF, max 32 MB"),
    markup_pct: float = Form(34.0, description="Markup percentage (0-80)"),
):
    """
    Upload a drawing PDF → Claude extracts members → backend computes costing.
    Returns extraction + costing payload for the review screen.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=413, detail="PDF exceeds 32 MB limit.")
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Validate markup range
    if not (0 <= markup_pct <= 80):
        raise HTTPException(status_code=400, detail="markup_pct must be between 0 and 80.")

    try:
        extraction = await extract_from_pdf(pdf_bytes)
    except ValueError as exc:
        logger.warning("Drawing extraction failed: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Could not read drawing — please try again or use a clearer PDF.",
        )
    except Exception as exc:
        logger.error("Unexpected error during extraction: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during PDF analysis.")

    members = extraction.get("members") or []
    if not members:
        # Return extraction with warning so the frontend can offer manual entry
        return {
            "warning": "No structural members were detected in this drawing.",
            "extraction": extraction,
            "costing": None,
        }

    try:
        costing = compute_costing(extraction, markup_pct=markup_pct / 100.0)
    except Exception as exc:
        logger.error("Costing calculation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during cost calculation.")

    return {
        "warning": None,
        "extraction": extraction,
        "costing": costing,
    }


# ---------------------------------------------------------------------------
# POST /generate-excel
# ---------------------------------------------------------------------------
class GenerateExcelRequest(BaseModel):
    extraction: Dict[str, Any] = Field(..., description="Full extraction dict returned by /analyse")
    customer: Dict[str, Any]   = Field(..., description="Customer / reference fields")
    markup_pct: float          = Field(34.0, ge=0, le=80, description="Markup percentage")


@router.post("/generate-excel")
async def generate_excel_endpoint(body: GenerateExcelRequest):
    """
    Receive review-screen payload → generate and stream the Job Costing Sheet xlsx.
    D58 is hardcoded; J33 / I40 / I41 / S54 / D56 remain as Excel formulas.
    """
    job_no = (
        body.customer.get("jobNo")
        or body.extraction.get("project", {}).get("drawing_no", "XXXX")
    )
    # Sanitise job_no for use in a filename
    safe_job_no = "".join(c for c in str(job_no) if c.isalnum() or c in "-_.")

    try:
        costing = compute_costing(body.extraction, markup_pct=body.markup_pct / 100.0)
    except Exception as exc:
        logger.error("Costing calculation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during cost calculation.")

    try:
        buf = generate_excel(costing, body.extraction.get("project", {}), body.customer)
    except Exception as exc:
        logger.error("Excel generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error generating Excel file.")

    filename = f"JobCosting_{safe_job_no}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
