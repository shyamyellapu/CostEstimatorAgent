"""Cover Letter API routes."""
import uuid
import io
import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.models import Job, Quotation, CoverLetter, UploadedFile, AuditLog
FileType = type('FileType', (), {'PDF': 'pdf', 'IMAGE': 'image', 'EXCEL': 'excel', 'DOCX': 'docx', 'QUOTATION': 'quotation', 'OTHER': 'other'})()
from app.services.cover_letter_service import cover_letter_service
from app.services.file_storage import storage_service
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate")
async def generate_cover_letter(
    quotation_file: UploadFile = File(...),
    job_id: str = Form(...),
    db: AsyncSession = Depends(db_session)
):
    """
    Generate a cover letter PDF.
    Requires quotation file upload — cannot proceed without it.
    """
    if not quotation_file or not quotation_file.filename:
        raise HTTPException(status_code=400,
            detail="Quotation file is required. Please upload the quotation PDF.")

    from sqlalchemy import select, or_
    result = await db.execute(
        select(Job).where(or_(Job.id == job_id, Job.job_number == job_id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    file_bytes = await quotation_file.read()

    # Save quotation file
    storage = await storage_service.save_upload(file_bytes, quotation_file.filename, str(job.id))
    uf = UploadedFile(
        job_id=job.id,
        original_filename=quotation_file.filename,
        stored_filename=storage["stored_filename"],
        file_type=FileType.QUOTATION,
        mime_type=quotation_file.content_type,
        file_size=storage["file_size"],
        storage_path=storage["storage_path"],
        storage_url=storage["storage_url"],
        is_processed="processing",
    )
    db.add(uf)
    await db.flush()

    # Step 1: Parse quotation
    try:
        quotation_data = await cover_letter_service.parse_quotation(file_bytes, quotation_file.filename)
    except Exception as e:
        logger.error(f"Quotation parsing error: {e}")
        raise HTTPException(status_code=422, detail=f"Failed to parse quotation: {str(e)}")

    # Save quotation record
    q = Quotation(
        job_id=job.id,
        file_id=uf.id,
        client=quotation_data.get("client"),
        reference_number=quotation_data.get("reference_number"),
        project=quotation_data.get("project"),
        subject=quotation_data.get("subject"),
        scope=quotation_data.get("scope"),
        exclusions=quotation_data.get("exclusions", []),
        payment_terms=quotation_data.get("payment_terms"),
        delivery_terms=quotation_data.get("delivery_terms"),
        validity=quotation_data.get("validity"),
        commercial_assumptions=quotation_data.get("commercial_assumptions", []),
        raw_extracted_json=quotation_data,
    )
    db.add(q)
    await db.flush()

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

    # Save output
    pdf_filename = f"{job.job_number}_cover_letter.pdf"
    pdf_storage = await storage_service.save_output(pdf_bytes, pdf_filename, str(job.id))

    cl = CoverLetter(
        job_id=job.id,
        quotation_id=q.id,
        content_json=draft_dict,
        pdf_path=pdf_storage["storage_path"],
        pdf_url=pdf_storage["storage_url"],
    )
    db.add(cl)
    uf.is_processed = "done"
    db.add(AuditLog(job_id=job.id, action="cover_letter_generated",
                    details_json={"pdf_path": pdf_storage["storage_path"]}))
    await db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'}
    )


@router.post("/parse-quotation")
async def parse_quotation_only(
    quotation_file: UploadFile = File(...),
    db: AsyncSession = Depends(db_session)
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
