"""BOQ Parser API routes."""
import csv
import io
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.services.document_parser import get_file_text
from app.services.file_storage import storage_service
from app.ai import get_ai_provider
from app.config import settings
from app.models import Job, UploadedFile, ExtractedData

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


def _detect_boq_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".xlsx", ".xls"):
        return "excel"
    if ext in (".docx", ".doc"):
        return "docx"
    if ext in (".csv", ".txt"):
        return "other"
    return "other"


def _sanitize_stem(name: str) -> str:
    stem = Path(name or "boq").stem
    safe = "".join(ch for ch in stem if ch.isalnum() or ch in ("-", "_"))
    return safe or "boq"


class BoqCsvExportRequest(BaseModel):
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = ""
    original_filename: Optional[str] = None
    job_id: Optional[str] = None


def _build_csv_bytes(dimensions: list[dict[str, Any]]) -> bytes:
    headers = [
        "Item Tag",
        "Description",
        "Section Type",
        "Qty",
        "Length (mm)",
        "Width (mm)",
        "Thickness (mm)",
        "OD (mm)",
        "Material",
        "Confidence",
    ]
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    for item in dimensions:
        writer.writerow([
            item.get("item_tag") or "",
            item.get("description") or "",
            item.get("section_type") or "",
            item.get("quantity") or "",
            item.get("length_mm") or "",
            item.get("width_mm") or "",
            item.get("thickness_mm") or "",
            item.get("od_mm") or "",
            item.get("material_grade") or "",
            item.get("confidence") or "",
        ])
    return stream.getvalue().encode("utf-8")


@router.post("/parse")
async def parse_boq(
    file: UploadFile = File(...),
    additional_context: Optional[str] = Form(None),
    db: AsyncSession = Depends(db_session),
):
    """Parse a BOQ file and extract structured line items."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="File required")
    file_bytes = await file.read()
    ai = get_ai_provider()
    try:
        is_pdf = file.filename.lower().endswith(".pdf") or "pdf" in (file.content_type or "").lower()

        # Claude path: send full PDF directly for extraction.
        if settings.ai_provider.lower() == "claude" and is_pdf:
            result = await ai.extract_from_document(file_bytes, "pdf", file.filename, additional_context)
            text = ""
        else:
            text = get_file_text(file_bytes, file.filename, file.content_type)
            if not text.strip():
                raise HTTPException(status_code=422, detail="Could not extract text from BOQ file")
            result = await ai.parse_boq(text, additional_context)

        member_types = _derive_member_types(result)

        job_number = f"BOQ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        job = Job(
            job_number=job_number,
            project_name=f"BOQ Parse - {file.filename}",
            status="completed",
        )
        db.add(job)
        await db.flush()

        storage = await storage_service.save_upload(file_bytes, file.filename, str(job.id))
        uploaded_file = UploadedFile(
            job_id=job.id,
            company_id=job.company_id,
            original_filename=file.filename,
            stored_filename=storage["stored_filename"],
            file_type=_detect_boq_file_type(file.filename),
            file_origin="upload",
            mime_type=file.content_type,
            file_size=storage["file_size"],
            storage_path=storage["storage_path"],
            storage_url=storage["storage_url"],
            storage_provider=storage.get("storage_provider"),
            blob_reference=storage.get("blob_reference"),
            checksum_sha256=storage.get("checksum_sha256"),
            is_processed="done",
            processing_status="completed",
            metadata_json={"source": "boq_parser", "module": "boq_parser"},
        )
        db.add(uploaded_file)
        await db.flush()

        extracted = ExtractedData(
            job_id=job.id,
            file_id=uploaded_file.id,
            data_type="boq_parse",
            extracted_json={
                "dimensions": [d.model_dump() for d in result.dimensions],
                "summary": result.summary,
                "overall_confidence": result.overall_confidence,
                "flags": [f.model_dump() for f in result.flags],
                "member_types": member_types,
            },
            raw_text=text,
            confidence=result.overall_confidence,
            is_confirmed=True,
            confirmed_at=datetime.utcnow(),
            flags=[f.model_dump() for f in result.flags],
            extraction_model="boq_parser",
        )
        db.add(extracted)
        await db.commit()

        return {
            "dimensions": [d.model_dump() for d in result.dimensions],
            "summary": result.summary,
            "overall_confidence": result.overall_confidence,
            "flags": [f.model_dump() for f in result.flags],
            "member_types": member_types,
            "job_id": str(job.id),
            "job_number": job.job_number,
            "uploaded_file_id": str(uploaded_file.id),
            "extraction_id": str(extracted.id),
        }
    except Exception as e:
        logger.error(f"BOQ parse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-csv")
async def export_boq_csv(
    body: BoqCsvExportRequest = Body(...),
    db: AsyncSession = Depends(db_session),
):
    if not body.dimensions:
        raise HTTPException(status_code=400, detail="No parsed BOQ dimensions to export")

    job = None
    if body.job_id:
        result = await db.execute(select(Job).where(or_(Job.id == body.job_id, Job.job_number == body.job_id)))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

    if not job:
        job_number = f"BOQ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        job = Job(
            job_number=job_number,
            project_name=f"BOQ Export - {body.original_filename or 'parsed'}",
            status="completed",
        )
        db.add(job)
        await db.flush()

    safe_stem = _sanitize_stem(body.original_filename or "boq")
    filename = f"{safe_stem}_parsed.csv"
    csv_bytes = _build_csv_bytes(body.dimensions)

    storage = await storage_service.save_output(csv_bytes, filename, str(job.id))

    exported_file = UploadedFile(
        job_id=job.id,
        company_id=job.company_id,
        original_filename=filename,
        stored_filename=storage["stored_filename"],
        file_type="csv",
        file_origin="generated",
        mime_type="text/csv",
        file_size=storage["file_size"],
        storage_path=storage["storage_path"],
        storage_url=storage["storage_url"],
        storage_provider=storage.get("storage_provider"),
        blob_reference=storage.get("blob_reference"),
        checksum_sha256=storage.get("checksum_sha256"),
        is_processed="done",
        processing_status="completed",
        metadata_json={
            "source": "boq_parser",
            "module": "boq_parser",
            "summary": body.summary or "",
            "rows": len(body.dimensions),
        },
    )
    db.add(exported_file)
    await db.commit()

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
