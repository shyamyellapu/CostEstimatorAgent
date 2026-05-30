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
import uuid
import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import db_session
from app.models import Job, UploadedFile, ExtractedData, CostingSheet, AuditLog
from app.services.file_storage import storage_service

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
    db: AsyncSession = Depends(db_session),
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

    project = extraction.get("project") or {}
    drawing_ref = (project.get("drawing_no") or "DRAWING").strip() or "DRAWING"
    job_number = f"DC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    job = Job(
        job_number=job_number,
        client_name=(project.get("contractor") or project.get("client") or None),
        project_name=(project.get("title") or None),
        project_ref=drawing_ref,
        status="calculating",
    )
    db.add(job)
    await db.flush()

    storage = await storage_service.save_upload(pdf_bytes, file.filename, str(job.id))
    uploaded_file = UploadedFile(
        job_id=job.id,
        company_id=job.company_id,
        original_filename=file.filename,
        stored_filename=storage["stored_filename"],
        file_type="pdf",
        file_origin="upload",
        mime_type=file.content_type or "application/pdf",
        file_size=storage["file_size"],
        storage_path=storage["storage_path"],
        storage_url=storage["storage_url"],
        storage_provider=storage.get("storage_provider"),
        blob_reference=storage.get("blob_reference"),
        checksum_sha256=storage.get("checksum_sha256"),
        is_processed="done",
        processing_status="completed",
        metadata_json={"source": "drawing_costing", "module": "drawing_costing"},
    )
    db.add(uploaded_file)
    await db.flush()

    db.add(ExtractedData(
        job_id=job.id,
        file_id=uploaded_file.id,
        data_type="drawing_costing_extraction",
        extracted_json=extraction,
        raw_text=extraction.get("notes"),
        confidence=None,
        is_confirmed=True,
        confirmed_at=datetime.utcnow(),
        flags=[],
        extraction_model="drawing_costing",
    ))

    try:
        costing = compute_costing(extraction, markup_pct=markup_pct / 100.0)
    except Exception as exc:
        logger.error("Costing calculation failed: %s", exc, exc_info=True)
        job.status = "failed"
        db.add(AuditLog(job_id=job.id, action="drawing_costing_failed", details_json={"error": str(exc)}))
        await db.commit()
        raise HTTPException(status_code=500, detail="Internal error during cost calculation.")

    costing_sheet = CostingSheet(
        job_id=job.id,
        line_items_json={
            "member_rows": costing.get("member_rows", []),
            "plates": costing.get("plates", []),
        },
        totals_json=costing,
        rates_snapshot_json={"markup_pct": markup_pct},
        audit_trail_json=[
            {
                "event": "drawing_costing_analyse",
                "uploaded_filename": file.filename,
                "created_at": datetime.utcnow().isoformat(),
            }
        ],
    )
    db.add(costing_sheet)
    job.status = "completed"
    job.total_weight_kg = costing.get("total_steel_kg")
    job.total_cost = costing.get("grand_total")
    job.selling_price = costing.get("selling_price")

    db.add(AuditLog(
        job_id=job.id,
        action="drawing_costing_completed",
        details_json={
            "file_id": str(uploaded_file.id),
            "drawing_ref": drawing_ref,
            "selling_price": costing.get("selling_price"),
        },
    ))
    await db.commit()

    return {
        "warning": None,
        "extraction": extraction,
        "costing": costing,
        "job_id": str(job.id),
        "job_number": job.job_number,
        "uploaded_file_id": str(uploaded_file.id),
        "costing_sheet_id": str(costing_sheet.id),
    }


# ---------------------------------------------------------------------------
# POST /generate-excel
# ---------------------------------------------------------------------------
class GenerateExcelRequest(BaseModel):
    extraction: Dict[str, Any] = Field(..., description="Full extraction dict returned by /analyse")
    customer: Dict[str, Any]   = Field(..., description="Customer / reference fields")
    markup_pct: float          = Field(34.0, ge=0, le=80, description="Markup percentage")
    job_id: Optional[str]      = Field(default=None, description="Optional persisted job id from /analyse")


@router.post("/generate-excel")
async def generate_excel_endpoint(
    body: GenerateExcelRequest,
    db: AsyncSession = Depends(db_session),
):
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
    excel_bytes = buf.getvalue()

    job: Optional[Job] = None
    if body.job_id:
        result = await db.execute(select(Job).where(Job.id == body.job_id))
        job = result.scalar_one_or_none()

    if job:
        storage = await storage_service.save_output(excel_bytes, filename, str(job.id))
        output_file = UploadedFile(
            job_id=job.id,
            company_id=job.company_id,
            original_filename=filename,
            stored_filename=storage["stored_filename"],
            file_type="excel",
            file_origin="generated",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size=storage["file_size"],
            storage_path=storage["storage_path"],
            storage_url=storage["storage_url"],
            storage_provider=storage.get("storage_provider"),
            blob_reference=storage.get("blob_reference"),
            checksum_sha256=storage.get("checksum_sha256"),
            is_processed="done",
            processing_status="completed",
            metadata_json={"source": "drawing_costing_excel", "job_no": safe_job_no},
        )
        db.add(output_file)

        cs = CostingSheet(
            job_id=job.id,
            line_items_json={
                "member_rows": costing.get("member_rows", []),
                "plates": costing.get("plates", []),
            },
            totals_json=costing,
            rates_snapshot_json={"markup_pct": body.markup_pct},
            audit_trail_json=[
                {
                    "event": "drawing_costing_generate_excel",
                    "filename": filename,
                    "customer": body.customer,
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
            excel_path=storage["storage_path"],
            excel_url=storage["storage_url"],
        )
        db.add(cs)

        db.add(AuditLog(
            job_id=job.id,
            action="drawing_costing_excel_generated",
            details_json={"filename": filename, "markup_pct": body.markup_pct},
        ))
        await db.commit()

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
