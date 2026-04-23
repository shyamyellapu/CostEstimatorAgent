"""
Estimate API routes — main workflow for cost estimation.
POST /api/estimate/upload        — upload files for a job
POST /api/estimate/extract       — trigger AI extraction
POST /api/estimate/confirm       — user confirms extracted data
POST /api/estimate/calculate     — run costing engine
POST /api/estimate/generate-excel — generate Excel file
GET  /api/estimate/jobs          — list all jobs
GET  /api/estimate/jobs/{id}     — get job detail
"""
import uuid
import json
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks, Body
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.models import Job, UploadedFile, ExtractedData, CostingSheet, RateConfiguration, AuditLog
JobStatus = type('JobStatus', (), {
    'DRAFT': 'draft', 'EXTRACTING': 'extracting',
    'PENDING_CONFIRMATION': 'pending_confirmation', 'CALCULATING': 'calculating',
    'COMPLETED': 'completed', 'FAILED': 'failed'
})
FileType = type('FileType', (), {
    'PDF': 'pdf', 'IMAGE': 'image', 'EXCEL': 'excel',
    'DOCX': 'docx', 'QUOTATION': 'quotation', 'OTHER': 'other'
})
from app.services.file_storage import storage_service
from app.services.document_parser import get_file_text, is_image_file, pdf_to_images
from app.services.costing_engine import run_costing_engine, DEFAULT_RATES
from app.services.excel_generator import excel_generator
from app.ai import get_ai_provider
from app.config import settings
import io

router = APIRouter()
logger = logging.getLogger(__name__)


def _extraction_score(extraction) -> int:
    return (
        len(getattr(extraction, "structural_elements", []) or []) * 5
        + len(getattr(extraction, "dimensions", []) or []) * 3
        + len(getattr(extraction, "bolts_and_plates", []) or []) * 2
        + len(getattr(extraction, "member_types", []) or [])
        + (3 if getattr(extraction, "drawing_metadata", None) and getattr(extraction.drawing_metadata, "drawing_number", None) else 0)
    )


def _detect_file_type(filename: str, content_type: str) -> FileType:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return FileType.PDF
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"):
        return FileType.IMAGE
    elif ext in (".xlsx", ".xls"):
        return FileType.EXCEL
    elif ext in (".docx", ".doc"):
        return FileType.DOCX
    else:
        return FileType.OTHER


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    client_name: Optional[str] = Form(None),
    project_name: Optional[str] = Form(None),
    project_ref: Optional[str] = Form(None),
    job_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(db_session)
):
    """Upload one or more files for a new or existing estimate job."""
    # Create or load job
    if job_id:
        from sqlalchemy import or_
        result = await db.execute(
            select(Job).where(or_(Job.id == job_id, Job.job_number == job_id))
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
    else:
        job_number = f"JOB-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        job = Job(
            job_number=job_number,
            client_name=client_name,
            project_name=project_name,
            project_ref=project_ref,
            status=JobStatus.DRAFT,
        )
        db.add(job)
        await db.flush()

    uploaded = []
    for file in files:
        content = await file.read()
        ftype = _detect_file_type(file.filename, file.content_type or "")
        storage = await storage_service.save_upload(content, file.filename, str(job.id))
        uf = UploadedFile(
            job_id=job.id,
            original_filename=file.filename,
            stored_filename=storage["stored_filename"],
            file_type=ftype,
            mime_type=file.content_type,
            file_size=storage["file_size"],
            storage_path=storage["storage_path"],
            storage_url=storage["storage_url"],
            is_processed="pending",
        )
        db.add(uf)
        uploaded.append({
            "file_id": str(uf.id),
            "filename": file.filename,
            "type": ftype,
            "url": storage["storage_url"],
        })

    await db.commit()
    return {
        "job_id": str(job.id),
        "job_number": job.job_number,
        "uploaded_files": uploaded,
        "message": f"{len(uploaded)} file(s) uploaded successfully"
    }


@router.post("/extract")
async def extract_from_files(
    job_id: str,
    additional_context: Optional[str] = None,
    db: AsyncSession = Depends(db_session)
):
    """Trigger AI extraction on all uploaded files for a job."""
    from sqlalchemy import or_
    result = await db.execute(
        select(Job).where(or_(Job.id == job_id, Job.job_number == job_id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    files_result = await db.execute(
        select(UploadedFile).where(UploadedFile.job_id == job.id)
    )
    files = files_result.scalars().all()
    if not files:
        raise HTTPException(status_code=400, detail="No uploaded files found for this job")

    job.status = JobStatus.EXTRACTING
    ai = get_ai_provider()
    all_extractions = []

    for uf in files:
        try:
            file_bytes = await storage_service.get_file(uf.storage_path)

            # Determine extraction method
            is_drawing = is_image_file(uf.original_filename) or uf.original_filename.lower().endswith(".pdf")
            
            if is_drawing:
                if uf.original_filename.lower().endswith(".pdf"):
                    text = get_file_text(file_bytes, uf.original_filename, uf.mime_type)
                    text_extraction = None
                    vision_extraction = None

                    # Only use text if there's meaningful extractable text (> 200 chars)
                    if len(text.strip()) > 200:
                        text_extraction = await ai.extract_from_document(
                            text.encode("utf-8"), uf.file_type, uf.original_filename, additional_context
                        )

                    vision_bytes = pdf_to_images(file_bytes)
                    if vision_bytes and (text_extraction is None or _extraction_score(text_extraction) == 0):
                        vision_extraction = await ai.extract_from_image(vision_bytes, uf.original_filename, additional_context)

                    if text_extraction and vision_extraction:
                        extraction = text_extraction if _extraction_score(text_extraction) >= _extraction_score(vision_extraction) else vision_extraction
                    elif text_extraction:
                        extraction = text_extraction
                    elif vision_extraction:
                        extraction = vision_extraction
                    else:
                        raise ValueError("Could not extract readable text or images from the PDF")
                else:
                    extraction = await ai.extract_from_image(file_bytes, uf.original_filename, additional_context)
            else:
                # Use Text for everything else (BOQs, docs)
                text = get_file_text(file_bytes, uf.original_filename, uf.mime_type)
                extraction = await ai.extract_from_document(text.encode("utf-8"), uf.file_type, uf.original_filename, additional_context)

            ed = ExtractedData(
                job_id=job.id,
                file_id=uf.id,
                data_type="full_extraction",
                extracted_json=extraction.model_dump(),
                raw_text=extraction.raw_text,
                confidence=extraction.overall_confidence,
                is_confirmed=False,
                flags=[f.model_dump() for f in extraction.flags],
                extraction_model=ai.provider_name,
            )
            db.add(ed)
            uf.is_processed = "done"
            all_extractions.append({
                "file_id": str(uf.id),
                "filename": uf.original_filename,
                "extraction_id": str(ed.id),
                "confidence": extraction.overall_confidence,
                "dimensions_found": len(extraction.dimensions),
                "flags": [f.model_dump() for f in extraction.flags],
                "summary": extraction.summary,
                "data": extraction.model_dump(),
            })
        except Exception as e:
            import traceback
            logger.error(f"Extraction failed for {uf.original_filename}: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            uf.is_processed = "failed"
            all_extractions.append({
                "file_id": str(uf.id),
                "filename": uf.original_filename,
                "error": str(e),
            })

    job.status = JobStatus.PENDING_CONFIRMATION

    # Audit
    db.add(AuditLog(job_id=job.id, action="extraction_completed",
                    details_json={"files_processed": len(files)}))
    await db.commit()

    return {
        "job_id": job_id,
        "status": "pending_confirmation",
        "extractions": all_extractions,
        "message": "Extraction complete. Please review and confirm extracted data before costing."
    }


@router.post("/confirm")
async def confirm_extraction(
    job_id: str,
    confirmed_items: list = Body(...),
    db: AsyncSession = Depends(db_session)
):
    """User confirms the extracted data (with any manual corrections)."""
    from sqlalchemy import or_
    result = await db.execute(
        select(Job).where(or_(Job.id == job_id, Job.job_number == job_id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Fetch the original full extraction to preserve costing_sheet_inputs and metadata
    orig_result = await db.execute(
        select(ExtractedData).where(
            ExtractedData.job_id == job.id,
            ExtractedData.data_type == "full_extraction"
        ).order_by(ExtractedData.extracted_at.desc())
    )
    orig_extraction = orig_result.scalar_one_or_none()
    orig_metadata = orig_extraction.extracted_json if orig_extraction else {}

    # Save confirmed items with original metadata preserved
    confirmed_ed = ExtractedData(
        job_id=job.id,
        data_type="confirmed_items",
        extracted_json={
            "items": confirmed_items,
            # Preserve original extraction metadata
            "drawing_metadata": orig_metadata.get("drawing_metadata"),
            "costing_sheet_inputs": orig_metadata.get("costing_sheet_inputs"),
            "surface_treatment": orig_metadata.get("surface_treatment"),
            "weight_summary": orig_metadata.get("weight_summary"),
        },
        is_confirmed=True,
        confirmed_at=datetime.utcnow(),
        confidence=1.0,
    )
    db.add(confirmed_ed)
    db.add(AuditLog(job_id=job.id, action="data_confirmed",
                    details_json={"item_count": len(confirmed_items)}))
    await db.commit()

    return {
        "job_id": job_id,
        "confirmed_items": len(confirmed_items),
        "message": "Data confirmed. Ready to calculate costs.",
        "extraction_id": str(confirmed_ed.id),
    }


@router.post("/calculate")
async def calculate_costs(
    job_id: str,
    db: AsyncSession = Depends(db_session)
):
    """Run deterministic costing engine on confirmed extracted data."""
    from sqlalchemy import or_
    result = await db.execute(
        select(Job).where(or_(Job.id == job_id, Job.job_number == job_id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Get confirmed extraction
    ed_result = await db.execute(
        select(ExtractedData).where(
            ExtractedData.job_id == job.id,
            ExtractedData.data_type == "confirmed_items",
            ExtractedData.is_confirmed == True
        ).order_by(ExtractedData.extracted_at.desc())
    )
    confirmed_ed = ed_result.scalar_one_or_none()
    if not confirmed_ed:
        raise HTTPException(
            status_code=400,
            detail=f"No confirmed extraction found for job {job_id}. Please confirm the data on the screen first."
        )

    line_items = confirmed_ed.extracted_json.get("items", [])

    # Pass aggregate costing inputs from AI extraction (steel kg, welding hrs, etc.)
    costing_inputs = confirmed_ed.extracted_json.get("costing_sheet_inputs") or {}

    # Load rates from DB
    rates_result = await db.execute(select(RateConfiguration).where(RateConfiguration.is_active == True))
    rate_rows = rates_result.scalars().all()
    db_rates = {r.key: r.value for r in rate_rows}
    rates = {**DEFAULT_RATES, **db_rates}

    job.status = JobStatus.CALCULATING
    try:
        costing = run_costing_engine(
            job_id=job_id,
            line_items=line_items,
            rates=rates,
            costing_inputs=costing_inputs,
        )
    except Exception as e:
        logger.error(f"Costing engine error: {e}")
        job.status = JobStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Costing calculation failed: {str(e)}")

    # Save costing sheet
    from dataclasses import asdict
    costing_dict = {}
    try:
        costing_dict = asdict(costing)
    except Exception:
        costing_dict = costing.__dict__

    cs = CostingSheet(
        job_id=job.id,
        line_items_json=[asdict(item) if hasattr(item, '__dataclass_fields__') else item
                         for item in costing.line_items],
        totals_json={
            "total_weight_kg":                costing.total_weight_kg,
            "total_material_cost":            costing.total_material_cost,
            "total_manhours":                 costing.total_manhours,
            "total_fabrication_cost":         costing.total_fabrication_cost,
            "total_welding_manhours":         costing.total_welding_manhours,
            "total_welding_cost":             costing.total_welding_cost,
            "total_consumables_cost":         costing.total_consumables_cost,
            "total_cutting_cost":             costing.total_cutting_cost,
            "total_surface_treatment_cost":   costing.total_surface_treatment_cost,
            "total_direct_cost":              costing.total_direct_cost,
            "overhead_cost":                  costing.overhead_cost,
            "overhead_percentage":            costing.overhead_percentage,
            "grand_total":                    costing.grand_total,
            "profit_amount":                  costing.profit_amount,
            "profit_margin_percentage":       costing.profit_margin_percentage,
            "selling_price":                  costing.selling_price,
            # Detailed breakdown for Excel
            "bolt_qty":        costing.bolt_qty,
            "bolt_cost":       costing.bolt_cost,
            "paint_litres":    costing.paint_litres,
            "paint_cost":      costing.paint_cost,
            "welding_hrs":     costing.welding_hrs,
            "fab_hrs":         costing.fab_hrs,
            "blasting_m2":     costing.blasting_m2,
            "blasting_cost":   costing.blasting_cost,
            "painting_m2":     costing.painting_m2,
            "painting_cost":   costing.painting_cost,
            "galv_kg":         costing.galv_kg,
            "galv_cost":       costing.galv_cost,
            "mpi_visits":      costing.mpi_visits,
            "mpi_cost":        costing.mpi_cost,
            "qaqc_cost":       costing.qaqc_cost,
            "packing_cost":    costing.packing_cost,
        },
        rates_snapshot_json=rates,
        audit_trail_json=costing.audit_trail,
    )
    db.add(cs)

    job.status = JobStatus.COMPLETED
    job.total_weight_kg = costing.total_weight_kg
    job.total_cost = costing.total_direct_cost
    job.selling_price = costing.selling_price

    db.add(AuditLog(job_id=job.id, action="costing_completed",
                    details_json={"selling_price": costing.selling_price}))
    await db.commit()

    return {
        "job_id": job_id,
        "costing_sheet_id": str(cs.id),
        "totals": cs.totals_json,
        "line_items_count": len(costing.line_items),
        "message": "Costing complete.",
    }


@router.post("/generate-excel")
async def generate_excel(
    job_id: str,
    costing_sheet_id: Optional[str] = None,
    db: AsyncSession = Depends(db_session)
):
    """Generate Excel costing sheet for a job."""
    from sqlalchemy import or_
    result = await db.execute(
        select(Job).where(or_(Job.id == job_id, Job.job_number == job_id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if costing_sheet_id:
        cs_result = await db.execute(
            select(CostingSheet).where(CostingSheet.id == costing_sheet_id)
        )
    else:
        cs_result = await db.execute(
            select(CostingSheet).where(CostingSheet.job_id == job.id)
            .order_by(CostingSheet.created_at.desc())
        )
    cs = cs_result.scalar_one_or_none()
    if not cs:
        raise HTTPException(status_code=404, detail="No costing sheet found")

    # Fetch extracted data (prefer confirmed items, fallback to full extraction)
    confirmed_result = await db.execute(
        select(ExtractedData).where(
            ExtractedData.job_id == job.id,
            ExtractedData.data_type == "confirmed_items",
            ExtractedData.is_confirmed == True
        ).order_by(ExtractedData.extracted_at.desc())
    )
    confirmed_data_record = confirmed_result.scalar_one_or_none()
    
    if confirmed_data_record:
        extracted_metadata = confirmed_data_record.extracted_json or {}
    else:
        # Fallback to full extraction if no confirmed items yet
        extracted_result = await db.execute(
            select(ExtractedData).where(
                ExtractedData.job_id == job.id,
                ExtractedData.data_type == "full_extraction"
            ).order_by(ExtractedData.extracted_at.desc())
        )
        extracted_data_record = extracted_result.scalar_one_or_none()
        extracted_metadata = extracted_data_record.extracted_json if extracted_data_record else {}

    job_data = {
        "job_number": job.job_number,
        "client_name": job.client_name or "",
        "project_name": job.project_name or "",
        "project_ref": job.project_ref or "",
        "currency": job.currency or "AED",
        "extracted_data": extracted_metadata,  # Include extracted costing inputs and metadata
    }

    costing_result = {
        **cs.totals_json,
        "line_items": cs.line_items_json,
        "audit_trail": cs.audit_trail_json,
    }

    try:
        excel_bytes = excel_generator.generate(job_data, costing_result, cs.rates_snapshot_json)
    except Exception as e:
        logger.error(f"Excel generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {str(e)}")

    filename = f"{job.job_number}_costing_sheet.xlsx"
    storage = await storage_service.save_output(excel_bytes, filename, str(job.id))
    cs.excel_path = storage["storage_path"]
    cs.excel_url = storage["storage_url"]
    await db.commit()

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/jobs")
async def list_jobs(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(db_session)
):
    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).offset(skip).limit(limit)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "job_number": j.job_number,
            "client_name": j.client_name,
            "project_name": j.project_name,
            "status": j.status,
            "selling_price": j.selling_price,
            "currency": j.currency,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(db_session)):
    from sqlalchemy import or_
    result = await db.execute(
        select(Job).where(or_(Job.id == job_id, Job.job_number == job_id))
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    files_r = await db.execute(select(UploadedFile).where(UploadedFile.job_id == job.id))
    files = files_r.scalars().all()

    sheets_r = await db.execute(
        select(CostingSheet).where(CostingSheet.job_id == job.id).order_by(CostingSheet.created_at.desc())
    )
    sheets = sheets_r.scalars().all()

    return {
        "id": str(job.id),
        "job_number": job.job_number,
        "client_name": job.client_name,
        "project_name": job.project_name,
        "project_ref": job.project_ref,
        "status": job.status,
        "total_weight_kg": job.total_weight_kg,
        "total_cost": job.total_cost,
        "selling_price": job.selling_price,
        "currency": job.currency,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "uploaded_files": [{"id": str(f.id), "filename": f.original_filename,
                            "type": f.file_type, "url": f.storage_url} for f in files],
        "costing_sheets": [{"id": str(s.id), "totals": s.totals_json,
                            "excel_url": s.excel_url, "created_at": s.created_at.isoformat()} for s in sheets],
    }
