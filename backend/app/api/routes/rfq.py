"""
RFQ API routes — full CRUD + extraction + validation + review + costing conversion.
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.models import (
    RFQRecord, RFQAttachment, RFQLineItem, ValidationResult,
    ExtractionReview, TaskQueue, Job,
)
from app.tasks.rfq_tasks import enqueue
from app.services.attachment_classifier import classify_attachment
from app.services.rfq_validation import compare_revisions

router = APIRouter()


# ─── Pydantic schemas ────────────────────────────────────────────────────────

class RFQCreate(BaseModel):
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    project_name: Optional[str] = None
    project_reference: Optional[str] = None
    subject: Optional[str] = None
    scope_summary: Optional[str] = None
    priority: str = "normal"
    notes: Optional[str] = None


class RFQUpdate(BaseModel):
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    project_name: Optional[str] = None
    project_reference: Optional[str] = None
    subject: Optional[str] = None
    scope_summary: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    deadline: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class LineItemUpdate(BaseModel):
    line_number: Optional[str] = None
    tag_number: Optional[str] = None
    description: Optional[str] = None
    material: Optional[str] = None
    material_grade: Optional[str] = None
    material_standard: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    weight_each_kg: Optional[float] = None
    total_weight_kg: Optional[float] = None
    dimensions: Optional[Dict[str, Any]] = None
    pressure_class: Optional[str] = None
    surface_treatment: Optional[str] = None
    drawing_reference: Optional[str] = None
    remarks: Optional[str] = None
    is_confirmed: Optional[bool] = None


class ReviewSubmit(BaseModel):
    review_status: str  # approved | rejected
    reviewed_by: Optional[str] = "reviewer"
    changes_made: Optional[List[dict]] = None
    notes: Optional[str] = None


class ValidationResolve(BaseModel):
    resolved_by: Optional[str] = "reviewer"
    resolution_note: Optional[str] = None


# ─── Helper ──────────────────────────────────────────────────────────────────

def _rfq_to_dict(rfq: RFQRecord) -> dict:
    return {
        "id": rfq.id,
        "rfq_number": rfq.rfq_number,
        "client_name": rfq.client_name,
        "client_email": rfq.client_email,
        "project_name": rfq.project_name,
        "project_reference": rfq.project_reference,
        "enquiry_date": rfq.enquiry_date.isoformat() if rfq.enquiry_date else None,
        "deadline": rfq.deadline.isoformat() if rfq.deadline else None,
        "subject": rfq.subject,
        "scope_summary": rfq.scope_summary,
        "status": rfq.status,
        "priority": rfq.priority,
        "revision_number": rfq.revision_number,
        "parent_rfq_id": rfq.parent_rfq_id,
        "job_id": rfq.job_id,
        "source": rfq.source,
        "assigned_to": rfq.assigned_to,
        "notes": rfq.notes,
        "tags": rfq.tags,
        "created_at": rfq.created_at.isoformat(),
        "updated_at": rfq.updated_at.isoformat() if rfq.updated_at else None,
        "attachment_count": len(rfq.attachments),
        "line_item_count": len(rfq.line_items),
    }


def _attachment_to_dict(att: RFQAttachment) -> dict:
    return {
        "id": att.id,
        "rfq_id": att.rfq_id,
        "email_id": att.email_id,
        "original_filename": att.original_filename,
        "mime_type": att.mime_type,
        "file_size": att.file_size,
        "storage_url": att.storage_url,
        "file_category": att.file_category,
        "document_type": att.document_type,
        "revision_number": att.revision_number,
        "document_number": att.document_number,
        "classification_confidence": att.classification_confidence,
        "extraction_status": att.extraction_status,
        "extracted_at": att.extracted_at.isoformat() if att.extracted_at else None,
        "created_at": att.created_at.isoformat(),
    }


def _line_item_to_dict(li: RFQLineItem) -> dict:
    return {
        "id": li.id,
        "rfq_id": li.rfq_id,
        "source_attachment_id": li.source_attachment_id,
        "line_number": li.line_number,
        "tag_number": li.tag_number,
        "description": li.description,
        "material": li.material,
        "material_grade": li.material_grade,
        "material_standard": li.material_standard,
        "quantity": li.quantity,
        "unit": li.unit,
        "weight_each_kg": li.weight_each_kg,
        "total_weight_kg": li.total_weight_kg,
        "dimensions": li.dimensions,
        "pressure_class": li.pressure_class,
        "surface_treatment": li.surface_treatment,
        "drawing_reference": li.drawing_reference,
        "remarks": li.remarks,
        "confidence_score": li.confidence_score,
        "validation_flags": li.validation_flags,
        "is_confirmed": li.is_confirmed,
        "confirmed_by": li.confirmed_by,
        "confirmed_at": li.confirmed_at.isoformat() if li.confirmed_at else None,
        "created_at": li.created_at.isoformat(),
    }


def _validation_to_dict(v: ValidationResult) -> dict:
    return {
        "id": v.id,
        "rfq_id": v.rfq_id,
        "line_item_id": v.line_item_id,
        "attachment_id": v.attachment_id,
        "validation_type": v.validation_type,
        "severity": v.severity,
        "message": v.message,
        "field_name": v.field_name,
        "extracted_value": v.extracted_value,
        "suggested_value": v.suggested_value,
        "confidence": v.confidence,
        "is_resolved": v.is_resolved,
        "resolved_by": v.resolved_by,
        "resolved_at": v.resolved_at.isoformat() if v.resolved_at else None,
        "resolution_note": v.resolution_note,
        "created_at": v.created_at.isoformat(),
    }


# ─── RFQ CRUD ─────────────────────────────────────────────────────────────────

@router.get("")
async def list_rfqs(
    status: Optional[str] = None,
    client: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(RFQRecord).order_by(RFQRecord.created_at.desc())
    if status:
        q = q.where(RFQRecord.status == status)
    if client:
        q = q.where(RFQRecord.client_name.ilike(f"%{client}%"))
    if priority:
        q = q.where(RFQRecord.priority == priority)
    q = q.offset(offset).limit(limit)
    result = await db.execute(q)
    rfqs = result.scalars().all()
    return [_rfq_to_dict(r) for r in rfqs]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rfq(body: RFQCreate, db: AsyncSession = Depends(get_db)):
    rfq_number = f"RFQ-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    rfq = RFQRecord(
        rfq_number=rfq_number,
        source="manual",
        status="received",
        **body.model_dump(exclude_none=True),
    )
    db.add(rfq)
    await db.commit()
    await db.refresh(rfq)
    return _rfq_to_dict(rfq)


@router.get("/stats")
async def rfq_stats(db: AsyncSession = Depends(get_db)):
    """Pipeline stage counts for dashboard."""
    res = await db.execute(
        select(RFQRecord.status, func.count(RFQRecord.id))
        .group_by(RFQRecord.status)
    )
    counts = {row[0]: row[1] for row in res.all()}
    return {
        "total": sum(counts.values()),
        "by_status": counts,
    }


@router.get("/{rfq_id}")
async def get_rfq(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")
    return _rfq_to_dict(rfq)


@router.put("/{rfq_id}")
async def update_rfq(rfq_id: str, body: RFQUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(rfq, field, val)
    await db.commit()
    await db.refresh(rfq)
    return _rfq_to_dict(rfq)


@router.delete("/{rfq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rfq(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")
    await db.delete(rfq)
    await db.commit()


# ─── Attachments ─────────────────────────────────────────────────────────────

@router.post("/{rfq_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    rfq_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "RFQ not found")

    # Validate file size (100 MB limit)
    MAX_SIZE = 100 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "File too large (max 100 MB)")

    # Validate filename
    safe_name = Path(file.filename or "upload").name
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(400, "Invalid filename")

    stored_name = f"{uuid.uuid4()}_{safe_name}"
    upload_dir = Path(settings.local_storage_path) / "rfq_uploads" / rfq_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    filepath = upload_dir / stored_name

    with open(filepath, "wb") as f:
        f.write(content)

    att = RFQAttachment(
        rfq_id=rfq_id,
        original_filename=safe_name,
        stored_filename=stored_name,
        mime_type=file.content_type,
        file_size=len(content),
        storage_path=str(filepath),
        storage_url=f"/storage/rfq_uploads/{rfq_id}/{stored_name}",
        file_category="other",
        document_type="unknown",
        extraction_status="pending",
    )
    db.add(att)
    await db.flush()

    # Enqueue classification + extraction
    await enqueue(db, "classify_attachment", "attachment", att.id, priority=2)
    await enqueue(db, "extract_attachment", "attachment", att.id, priority=3)
    await enqueue(db, "validate_rfq", "rfq", rfq_id, priority=5)

    await db.commit()
    await db.refresh(att)
    return _attachment_to_dict(att)


@router.get("/{rfq_id}/attachments")
async def list_attachments(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(RFQAttachment).where(RFQAttachment.rfq_id == rfq_id)
        .order_by(RFQAttachment.created_at)
    )
    return [_attachment_to_dict(a) for a in res.scalars().all()]


@router.post("/{rfq_id}/attachments/{att_id}/reclassify")
async def reclassify_attachment(
    rfq_id: str, att_id: str, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(RFQAttachment).where(
            RFQAttachment.id == att_id, RFQAttachment.rfq_id == rfq_id
        )
    )
    att = res.scalar_one_or_none()
    if not att:
        raise HTTPException(404, "Attachment not found")

    # If no local file yet (Gmail attachment), enqueue via task queue instead
    if not att.storage_path:
        task = await enqueue(db, "classify_attachment", "attachment", att.id, priority=1)
        await db.commit()
        return {**_attachment_to_dict(att), "_task_id": task.id, "_queued": True}

    cr = await classify_attachment(att.storage_path, att.original_filename, att.mime_type or "")
    att.file_category = cr.file_category
    att.document_type = cr.document_type
    att.classification_confidence = cr.confidence
    att.revision_number = cr.revision_number
    att.document_number = cr.document_number
    att.classification_metadata = cr.metadata
    await db.commit()
    await db.refresh(att)
    return _attachment_to_dict(att)


@router.post("/{rfq_id}/attachments/{att_id}/re-extract")
async def re_extract_attachment(
    rfq_id: str, att_id: str, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(RFQAttachment).where(
            RFQAttachment.id == att_id, RFQAttachment.rfq_id == rfq_id
        )
    )
    att = res.scalar_one_or_none()
    if not att:
        raise HTTPException(404, "Attachment not found")

    task = await enqueue(db, "extract_attachment", "attachment", att.id, priority=1)
    await db.commit()
    return {"task_id": task.id, "status": "queued"}


# ─── Line Items ───────────────────────────────────────────────────────────────

@router.get("/{rfq_id}/line-items")
async def list_line_items(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(RFQLineItem).where(RFQLineItem.rfq_id == rfq_id)
        .order_by(RFQLineItem.created_at)
    )
    return [_line_item_to_dict(li) for li in res.scalars().all()]


@router.put("/{rfq_id}/line-items/{item_id}")
async def update_line_item(
    rfq_id: str, item_id: str, body: LineItemUpdate, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(RFQLineItem).where(
            RFQLineItem.id == item_id, RFQLineItem.rfq_id == rfq_id
        )
    )
    li = res.scalar_one_or_none()
    if not li:
        raise HTTPException(404, "Line item not found")

    updates = body.model_dump(exclude_none=True)
    if "is_confirmed" in updates and updates["is_confirmed"]:
        updates["confirmed_at"] = datetime.utcnow()

    for field, val in updates.items():
        setattr(li, field, val)

    await db.commit()
    await db.refresh(li)
    return _line_item_to_dict(li)


@router.delete("/{rfq_id}/line-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_line_item(rfq_id: str, item_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(RFQLineItem).where(
            RFQLineItem.id == item_id, RFQLineItem.rfq_id == rfq_id
        )
    )
    li = res.scalar_one_or_none()
    if not li:
        raise HTTPException(404, "Line item not found")
    await db.delete(li)
    await db.commit()


@router.post("/{rfq_id}/line-items/confirm-all")
async def confirm_all_line_items(
    rfq_id: str,
    confirmed_by: str = "reviewer",
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(RFQLineItem).where(
            RFQLineItem.rfq_id == rfq_id, RFQLineItem.is_confirmed == False
        )
    )
    items = res.scalars().all()
    now = datetime.utcnow()
    for li in items:
        li.is_confirmed = True
        li.confirmed_by = confirmed_by
        li.confirmed_at = now
    await db.commit()
    return {"confirmed": len(items)}


# ─── Extraction pipeline ──────────────────────────────────────────────────────

@router.post("/{rfq_id}/extract")
async def trigger_extraction(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")

    att_res = await db.execute(
        select(RFQAttachment).where(RFQAttachment.rfq_id == rfq_id)
    )
    attachments = att_res.scalars().all()

    tasks_created = 0
    for att in attachments:
        await enqueue(db, "classify_attachment", "attachment", att.id, priority=2)
        await enqueue(db, "extract_attachment", "attachment", att.id, priority=3)
        tasks_created += 2

    await enqueue(db, "validate_rfq", "rfq", rfq.id, priority=5)
    rfq.status = "extracting"
    await db.commit()
    return {"status": "queued", "tasks_created": tasks_created + 1}


@router.post("/{rfq_id}/validate")
async def trigger_validation(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "RFQ not found")
    task = await enqueue(db, "validate_rfq", "rfq", rfq_id, priority=2)
    await db.commit()
    return {"task_id": task.id, "status": "queued"}


# ─── Validation results ───────────────────────────────────────────────────────

@router.get("/{rfq_id}/validation")
async def get_validation_results(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(ValidationResult).where(ValidationResult.rfq_id == rfq_id)
        .order_by(ValidationResult.severity, ValidationResult.created_at)
    )
    results = res.scalars().all()
    issues = [_validation_to_dict(v) for v in results]
    errors   = sum(1 for v in issues if v["severity"] == "error")
    warnings = sum(1 for v in issues if v["severity"] == "warning")
    return {"issues": issues, "total": len(issues), "errors": errors, "warnings": warnings}


@router.post("/{rfq_id}/validation/{issue_id}/resolve")
async def resolve_validation(
    rfq_id: str, issue_id: str, body: ValidationResolve, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(ValidationResult).where(
            ValidationResult.id == issue_id, ValidationResult.rfq_id == rfq_id
        )
    )
    vr = res.scalar_one_or_none()
    if not vr:
        raise HTTPException(404, "Validation issue not found")
    vr.is_resolved = True
    vr.resolved_by = body.resolved_by
    vr.resolved_at = datetime.utcnow()
    vr.resolution_note = body.resolution_note
    await db.commit()
    await db.refresh(vr)
    return _validation_to_dict(vr)


# ─── Human review ─────────────────────────────────────────────────────────────

@router.post("/{rfq_id}/review")
async def submit_review(
    rfq_id: str, body: ReviewSubmit, db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")

    review = ExtractionReview(
        rfq_id=rfq_id,
        reviewed_by=body.reviewed_by,
        review_status=body.review_status,
        changes_made=body.changes_made,
        notes=body.notes,
        reviewed_at=datetime.utcnow(),
    )
    db.add(review)

    if body.review_status == "approved":
        rfq.status = "validated"
    elif body.review_status == "rejected":
        rfq.status = "review"

    await db.commit()
    return {"review_id": review.id, "rfq_status": rfq.status}


@router.post("/{rfq_id}/approve")
async def approve_for_costing(rfq_id: str, db: AsyncSession = Depends(get_db)):
    """Move an RFQ to costing stage."""
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")

    rfq.status = "costing"
    await db.commit()
    return {"rfq_id": rfq_id, "status": "costing"}


# ─── Revision management ──────────────────────────────────────────────────────

@router.get("/{rfq_id}/revisions")
async def list_revisions(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")

    # Find root
    root_id = rfq.parent_rfq_id or rfq_id
    rev_res = await db.execute(
        select(RFQRecord).where(
            (RFQRecord.id == root_id) | (RFQRecord.parent_rfq_id == root_id)
        ).order_by(RFQRecord.revision_number)
    )
    return [_rfq_to_dict(r) for r in rev_res.scalars().all()]


@router.post("/{rfq_id}/revisions/compare")
async def compare_rfq_revisions(
    rfq_id: str,
    other_rfq_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Compare line items between two RFQ revisions."""
    ids = [rfq_id, other_rfq_id]
    records = {}
    for rid in ids:
        li_res = await db.execute(
            select(RFQLineItem).where(RFQLineItem.rfq_id == rid)
        )
        records[rid] = [
            {
                "tag_number": li.tag_number,
                "line_number": li.line_number,
                "description": li.description,
                "material": li.material,
                "quantity": li.quantity,
                "unit": li.unit,
                "weight_each_kg": li.weight_each_kg,
                "total_weight_kg": li.total_weight_kg,
            }
            for li in li_res.scalars().all()
        ]

    changes = compare_revisions(records[rfq_id], records[other_rfq_id])
    return {
        "base_rfq_id": rfq_id,
        "compare_rfq_id": other_rfq_id,
        "changes": changes,
        "summary": {
            "added":    sum(1 for c in changes if c["type"] == "added"),
            "removed":  sum(1 for c in changes if c["type"] == "removed"),
            "modified": sum(1 for c in changes if c["type"] == "modified"),
        },
    }


# ─── Convert to Job ────────────────────────────────────────────────────────────

@router.post("/{rfq_id}/convert-to-job")
async def convert_to_job(rfq_id: str, db: AsyncSession = Depends(get_db)):
    """Convert an approved RFQ to a Job for full costing."""
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")
    if rfq.job_id:
        return {"job_id": rfq.job_id, "message": "Already converted"}

    import random
    job_number = f"JOB-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(100, 999)}"
    job = Job(
        job_number=job_number,
        client_name=rfq.client_name,
        project_name=rfq.project_name,
        project_ref=rfq.project_reference,
        status="draft",
        currency="AED",
    )
    db.add(job)
    await db.flush()

    rfq.job_id = job.id
    rfq.status = "quoted"
    await db.commit()
    return {"job_id": job.id, "job_number": job_number, "rfq_id": rfq_id}


# ─── Task status ──────────────────────────────────────────────────────────────

@router.get("/{rfq_id}/tasks")
async def get_rfq_tasks(rfq_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(TaskQueue).where(
            TaskQueue.entity_id == rfq_id,
        ).order_by(TaskQueue.created_at.desc()).limit(20)
    )
    return [
        {
            "id": t.id,
            "task_type": t.task_type,
            "status": t.status,
            "attempts": t.attempts,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "error_message": t.error_message,
        }
        for t in res.scalars().all()
    ]


# ─── Auto Drawing Costing ─────────────────────────────────────────────────────

class AutoCostingRequest(BaseModel):
    markup_pct: float = 34.0


@router.post("/{rfq_id}/auto-costing")
async def trigger_auto_costing(
    rfq_id: str,
    body: AutoCostingRequest = AutoCostingRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Enqueue the auto drawing costing pipeline for this RFQ.
    All PDF attachments are fed to the drawing-costing AI model;
    results (extraction + cost sheet) are stored in the RFQ record.
    """
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")

    if not (0 <= body.markup_pct <= 80):
        raise HTTPException(400, "markup_pct must be between 0 and 80")

    task = await enqueue(
        db,
        "auto_drawing_costing",
        "rfq",
        rfq_id,
        payload={"markup_pct": body.markup_pct},
        priority=1,
    )
    rfq.status = "costing"
    await db.commit()
    return {"task_id": task.id, "status": "queued", "markup_pct": body.markup_pct}


@router.get("/{rfq_id}/auto-costing")
async def get_auto_costing(rfq_id: str, db: AsyncSession = Depends(get_db)):
    """Return the latest auto-costing result stored on the RFQ."""
    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")

    meta = rfq.extra_metadata or {}
    costing_result = meta.get("auto_costing")
    if not costing_result:
        raise HTTPException(404, "No auto-costing result available yet. Run auto-costing first.")

    return {
        "rfq_id": rfq_id,
        "rfq_number": rfq.rfq_number,
        "client_name": rfq.client_name,
        "project_name": rfq.project_name,
        **costing_result,
    }


@router.post("/{rfq_id}/auto-costing/download-excel")
async def download_auto_costing_excel(rfq_id: str, db: AsyncSession = Depends(get_db)):
    """
    Generate and download the Job Costing Sheet Excel using the stored auto-costing
    result and the RFQ's client/project details as customer fields.
    """
    from app.services.drawing_costing import generate_excel

    res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq = res.scalar_one_or_none()
    if not rfq:
        raise HTTPException(404, "RFQ not found")

    meta = rfq.extra_metadata or {}
    costing_data = meta.get("auto_costing")
    if not costing_data:
        raise HTTPException(
            400,
            "No costing data found. Please run auto-costing first via POST /auto-costing.",
        )

    costing = costing_data.get("costing", {})
    extraction = costing_data.get("extraction", {})
    project_meta = extraction.get("project", {})

    # Use the customer fields built by the task (which include email metadata),
    # falling back to the RFQ record fields if the task predates this change.
    customer = costing_data.get("customer") or {
        "customerName": rfq.client_name or project_meta.get("client", ""),
        "refNo": rfq.project_reference or rfq.rfq_number,
        "jobNo": rfq.rfq_number,
        "enquiryNo": rfq.project_reference or "",
        "attention": "",
        "contact": rfq.client_email or "",
    }

    try:
        buf = generate_excel(costing, project_meta, customer)
    except FileNotFoundError as exc:
        raise HTTPException(500, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Excel generation failed: {exc}")

    safe_number = rfq.rfq_number.replace("/", "-").replace(" ", "_")
    filename = f"{safe_number}_costing_sheet.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
