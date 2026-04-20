"""Cover Letter API routes."""
import io
import logging
import re
from datetime import datetime
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.services.cover_letter_service import cover_letter_service
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate")
async def generate_cover_letter(
    quotation_file: UploadFile = File(...)
):
    """
    Generate a cover letter PDF.
    Requires quotation file upload — cannot proceed without it.
    """
    if not quotation_file or not quotation_file.filename:
        raise HTTPException(status_code=400,
            detail="Quotation file is required. Please upload the quotation PDF.")

    file_bytes = await quotation_file.read()

    # Step 1: Parse quotation
    try:
        quotation_data = await cover_letter_service.parse_quotation(file_bytes, quotation_file.filename)
    except Exception as e:
        logger.error(f"Quotation parsing error: {e}")
        raise HTTPException(status_code=422, detail=f"Failed to parse quotation: {str(e)}")

    # Step 2: Generate AI draft
    company_info = {
        "name": settings.company_name,
        "address": settings.company_address,
        "phone": settings.company_phone,
        "email": settings.company_email,
        "website": settings.company_website,
        "signatory_name": settings.signatory_name,
        "signatory_title": settings.signatory_title,
    }
    try:
        draft = await cover_letter_service.generate_draft(quotation_data, company_info)
        draft_dict = draft.model_dump() if hasattr(draft, "model_dump") else draft.__dict__
    except Exception as e:
        logger.error(f"Cover letter draft error: {e}")
        raise HTTPException(status_code=500, detail=f"Draft generation failed: {str(e)}")

    # Step 3: Render PDF
    try:
        pdf_bytes = cover_letter_service.render_pdf(draft_dict, company_info)
    except Exception as e:
        logger.error(f"PDF render error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF rendering failed: {str(e)}")

    ref = quotation_data.get("reference_number") or quotation_data.get("project") or "cover_letter"
    safe_ref = re.sub(r"[^A-Za-z0-9._-]+", "_", str(ref)).strip("_") or "cover_letter"
    pdf_filename = f"{safe_ref}_{datetime.utcnow().strftime('%Y%m%d')}_cover_letter.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'}
    )


@router.post("/parse-quotation")
async def parse_quotation_only(
    quotation_file: UploadFile = File(...)
):
    """Parse quotation and return structured data without generating cover letter."""
    if not quotation_file or not quotation_file.filename:
        raise HTTPException(status_code=400, detail="Quotation file is required.")
    file_bytes = await quotation_file.read()
    try:
        data = await cover_letter_service.parse_quotation(file_bytes, quotation_file.filename)
        return {"parsed_data": data, "message": "Quotation parsed successfully"}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
