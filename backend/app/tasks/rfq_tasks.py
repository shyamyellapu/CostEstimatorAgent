"""
Database-backed async task processor.

Tasks are stored in the task_queue table and processed by background workers.
No external message broker required — uses asyncio + SQLAlchemy.

Supported task types:
  - classify_attachment   : run attachment classification on an RFQAttachment
  - extract_attachment    : run extraction pipeline on an RFQAttachment
  - validate_rfq          : run validation on all line items of an RFQRecord
  - sync_gmail            : sync a Gmail mailbox
  - process_email         : classify and link an RFQEmail to an RFQ
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import (
    TaskQueue, RFQAttachment, RFQRecord, RFQEmail,
    RFQLineItem, ValidationResult, GmailCredential,
)
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task creation helpers
# ---------------------------------------------------------------------------

async def enqueue(
    db: AsyncSession,
    task_type: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    priority: int = 5,
) -> TaskQueue:
    task = TaskQueue(
        task_type=task_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        priority=priority,
        status="pending",
    )
    db.add(task)
    await db.flush()
    logger.info(
        "task_enqueued task_id=%s type=%s entity_type=%s entity_id=%s priority=%d",
        task.id,
        task_type,
        entity_type,
        entity_id,
        priority,
    )
    return task


# ---------------------------------------------------------------------------
# Task handlers
# ---------------------------------------------------------------------------

async def _ensure_attachment_downloaded(att: RFQAttachment, db: AsyncSession) -> bool:
    """
    If the attachment has no storage_path but has a gmail_attachment_id,
    download the file from Gmail and update att.storage_path.
    Returns True if storage_path is available (existing or freshly downloaded).
    """
    if att.storage_path:
        return True

    if not att.gmail_attachment_id or not att.email_id:
        logger.warning("attachment_download_unavailable attachment_id=%s reason=missing_gmail_reference", att.id)
        return False

    from app.services.gmail_service import GmailSyncService
    from app.models import RFQEmail, GmailCredential
    from app.config import settings
    import os

    # Load parent email to find mailbox
    email_res = await db.execute(select(RFQEmail).where(RFQEmail.id == att.email_id))
    email: Optional[RFQEmail] = email_res.scalar_one_or_none()
    if not email or not email.mailbox_id:
        logger.warning("attachment_download_unavailable attachment_id=%s reason=email_or_mailbox_missing", att.id)
        return False

    mailbox_res = await db.execute(
        select(GmailCredential).where(GmailCredential.id == email.mailbox_id)
    )
    mailbox: Optional[GmailCredential] = mailbox_res.scalar_one_or_none()
    if not mailbox or not mailbox.credentials_json:
        logger.warning("attachment_download_unavailable attachment_id=%s mailbox_id=%s reason=credentials_missing", att.id, email.mailbox_id)
        return False

    dest_dir = os.path.join(settings.local_storage_path, "rfq_uploads", att.rfq_id or "unlinked")
    svc = GmailSyncService(db)
    filepath = await svc.download_attachment(att, mailbox, dest_dir)
    if not filepath:
        logger.warning("attachment_download_failed attachment_id=%s", att.id)
        return False

    att.storage_path = filepath
    await db.flush()
    logger.info("attachment_downloaded attachment_id=%s path=%s", att.id, filepath)
    return True


async def _handle_classify_attachment(task: TaskQueue, db: AsyncSession) -> Dict[str, Any]:
    from app.services.attachment_classifier import classify_attachment

    att_id = task.entity_id
    result = await db.execute(select(RFQAttachment).where(RFQAttachment.id == att_id))
    att: Optional[RFQAttachment] = result.scalar_one_or_none()
    if not att:
        return {"error": f"Attachment {att_id} not found"}

    if not await _ensure_attachment_downloaded(att, db):
        return {"error": "No storage path and Gmail download failed for attachment"}

    cr = await classify_attachment(
        filepath=att.storage_path,
        filename=att.original_filename,
        mime_type=att.mime_type or "",
    )
    att.file_category = cr.file_category
    att.document_type = cr.document_type
    att.classification_confidence = cr.confidence
    att.revision_number = cr.revision_number
    att.document_number = cr.document_number
    att.classification_metadata = cr.metadata
    await db.flush()
    return cr.to_dict()


async def _handle_extract_attachment(task: TaskQueue, db: AsyncSession) -> Dict[str, Any]:
    from app.services.rfq_extractor import extract_from_attachment

    att_id = task.entity_id
    result = await db.execute(select(RFQAttachment).where(RFQAttachment.id == att_id))
    att: Optional[RFQAttachment] = result.scalar_one_or_none()
    if not att:
        return {"error": f"Attachment {att_id} not found"}

    if not await _ensure_attachment_downloaded(att, db):
        return {"error": "No storage path and Gmail download failed for attachment"}

    att.extraction_status = "running"
    await db.flush()

    try:
        extraction = await extract_from_attachment(
            filepath=att.storage_path,
            filename=att.original_filename,
            file_category=att.file_category or "other",
            document_type=att.document_type or "other",
        )
    except Exception:
        att.extraction_status = "failed"
        await db.flush()
        raise

    line_items = extraction.get("line_items", [])
    metadata = extraction.get("metadata", {})

    # Persist line items to the parent RFQ
    if att.rfq_id:
        for item_data in line_items:
            dims = item_data.get("dimensions")
            if dims and not isinstance(dims, dict):
                dims = None
            li = RFQLineItem(
                rfq_id=att.rfq_id,
                source_attachment_id=att.id,
                line_number=str(item_data.get("line_number") or ""),
                tag_number=item_data.get("tag_number"),
                description=item_data.get("description"),
                material=item_data.get("material"),
                material_grade=item_data.get("material_grade"),
                material_standard=item_data.get("material_standard"),
                quantity=_to_float(item_data.get("quantity")),
                unit=item_data.get("unit"),
                weight_each_kg=_to_float(item_data.get("weight_each_kg")),
                total_weight_kg=_to_float(item_data.get("total_weight_kg")),
                dimensions=dims,
                pressure_class=item_data.get("pressure_class"),
                surface_treatment=item_data.get("surface_treatment"),
                drawing_reference=item_data.get("drawing_reference"),
                remarks=item_data.get("remarks"),
                confidence_score=_to_float(item_data.get("confidence_score")),
                raw_extracted=item_data.get("raw_extracted"),
            )
            db.add(li)

        # Update RFQ metadata fields that were extracted
        rfq_res = await db.execute(select(RFQRecord).where(RFQRecord.id == att.rfq_id))
        rfq: Optional[RFQRecord] = rfq_res.scalar_one_or_none()
        if rfq and metadata:
            if not rfq.client_name and metadata.get("client_name"):
                rfq.client_name = metadata["client_name"]
            if not rfq.project_name and metadata.get("project_name"):
                rfq.project_name = metadata["project_name"]
            if not rfq.project_reference and metadata.get("project_reference"):
                rfq.project_reference = metadata["project_reference"]
            if not rfq.scope_summary and metadata.get("scope_summary"):
                rfq.scope_summary = metadata["scope_summary"]

    att.extraction_status = "completed"
    att.extracted_at = datetime.utcnow()
    await db.flush()

    return {"line_items_extracted": len(line_items), "source_stage": extraction.get("source_stage")}


async def _handle_validate_rfq(task: TaskQueue, db: AsyncSession) -> Dict[str, Any]:
    from app.services.rfq_validation import validate_rfq_extraction

    rfq_id = task.entity_id
    rfq_res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq: Optional[RFQRecord] = rfq_res.scalar_one_or_none()
    if not rfq:
        return {"error": f"RFQ {rfq_id} not found"}

    # Load line items
    li_res = await db.execute(select(RFQLineItem).where(RFQLineItem.rfq_id == rfq_id))
    line_items = [
        {
            "description": li.description,
            "material": li.material,
            "quantity": li.quantity,
            "unit": li.unit,
            "weight_each_kg": li.weight_each_kg,
            "total_weight_kg": li.total_weight_kg,
            "tag_number": li.tag_number,
            "dimensions": li.dimensions,
            "confidence_score": li.confidence_score,
        }
        for li in li_res.scalars().all()
    ]

    metadata = {
        "client_name": rfq.client_name,
        "scope_summary": rfq.scope_summary,
    }

    issues, summary = validate_rfq_extraction(line_items, metadata)

    # Remove old unresolved results then insert fresh ones
    old_res = await db.execute(
        select(ValidationResult).where(
            ValidationResult.rfq_id == rfq_id,
            ValidationResult.is_resolved == False,
        )
    )
    for old in old_res.scalars().all():
        await db.delete(old)

    for issue in issues:
        vr = ValidationResult(
            rfq_id=rfq_id,
            validation_type=issue["validation_type"],
            severity=issue["severity"],
            message=issue["message"],
            field_name=issue.get("field_name"),
            extracted_value=str(issue["extracted_value"]) if issue.get("extracted_value") else None,
            suggested_value=str(issue["suggested_value"]) if issue.get("suggested_value") else None,
            confidence=issue.get("confidence"),
        )
        db.add(vr)

    # Update RFQ status
    if summary["errors"] == 0 and summary["warnings"] == 0:
        rfq.status = "validated"
    elif rfq.status == "extracting":
        rfq.status = "review"

    await db.flush()
    return summary


async def _handle_sync_gmail(task: TaskQueue, db: AsyncSession) -> Dict[str, Any]:
    from app.services.gmail_service import GmailSyncService

    mailbox_id = task.entity_id or task.payload.get("mailbox_id")
    svc = GmailSyncService(db)

    if mailbox_id:
        mailbox = await svc.get_mailbox(mailbox_id)
        if not mailbox:
            return {"error": f"Mailbox {mailbox_id} not found"}
        return await svc.sync_mailbox(mailbox)

    # Sync all active mailboxes
    mailboxes = await svc.get_active_mailboxes()
    total_counters: Dict[str, int] = {"fetched": 0, "new_rfq": 0, "skipped": 0}
    for mb in mailboxes:
        counters = await svc.sync_mailbox(mb)
        for k in ("fetched", "new_rfq", "skipped"):
            total_counters[k] = total_counters.get(k, 0) + counters.get(k, 0)
    return total_counters


async def _handle_process_email(task: TaskQueue, db: AsyncSession) -> Dict[str, Any]:
    """
    Create an RFQRecord from a detected RFQ email.
    """
    email_id = task.entity_id
    email_res = await db.execute(select(RFQEmail).where(RFQEmail.id == email_id))
    email: Optional[RFQEmail] = email_res.scalar_one_or_none()
    if not email:
        return {"error": f"Email {email_id} not found"}

    if email.rfq_id:
        return {"skipped": "already linked to RFQ", "rfq_id": email.rfq_id}

    from app.services.rfq_extractor import extract_from_email_body
    import uuid

    meta = await extract_from_email_body(email.subject or "", email.body_text or "")
    metadata = meta.get("metadata", {})

    _raw_rfq_num = metadata.get("rfq_number", "") or ""
    # Validate: must have at least one digit and be ≥4 chars to be a real reference
    import re as _re
    rfq_number = (
        _raw_rfq_num
        if len(_raw_rfq_num) >= 4 and _re.search(r'\d', _raw_rfq_num)
        else f"RFQ-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    )

    rfq = RFQRecord(
        rfq_number=rfq_number,
        client_name=email.sender_name or email.sender_email,
        client_email=email.sender_email,
        project_reference=metadata.get("project_reference"),
        subject=email.subject,
        scope_summary=metadata.get("scope_summary"),
        enquiry_date=email.received_at,
        source="gmail",
        status="received",
    )
    db.add(rfq)
    await db.flush()

    # Link email → RFQ
    email.rfq_id = rfq.id
    email.is_processed = True

    # Link unattached attachments from this email → RFQ
    for att in email.attachments:
        att.rfq_id = rfq.id

    await db.flush()

    # Enqueue classification + extraction for each attachment
    for att in email.attachments:
        await enqueue(db, "classify_attachment", "attachment", att.id, priority=3)
        await enqueue(db, "extract_attachment", "attachment", att.id, priority=4)

    # Enqueue validation
    await enqueue(db, "validate_rfq", "rfq", rfq.id, priority=5)

    # Auto-trigger drawing costing pipeline from email attachments
    await enqueue(db, "auto_drawing_costing", "rfq", rfq.id, priority=6)

    return {"rfq_id": rfq.id, "rfq_number": rfq_number}


# ---------------------------------------------------------------------------
# Auto Drawing Costing Task
# ---------------------------------------------------------------------------

async def _handle_auto_drawing_costing(task: TaskQueue, db: AsyncSession) -> Dict[str, Any]:
    """
    Automatically run the drawing costing pipeline on all PDF attachments of an RFQ.
    The linked email body (subject + body_text) is passed as context to the AI so it
    can correctly identify the client name, project reference, and scope from the email.
    Customer fields in the Excel are populated from the RFQ / email metadata.
    Results are stored in rfq.extra_metadata["auto_costing"] for retrieval and download.
    """
    from app.services.drawing_costing import extract_from_pdf, compute_costing

    rfq_id = task.entity_id
    markup_pct = float((task.payload or {}).get("markup_pct", 34.0))

    # Load RFQ
    rfq_res = await db.execute(select(RFQRecord).where(RFQRecord.id == rfq_id))
    rfq: Optional[RFQRecord] = rfq_res.scalar_one_or_none()
    if not rfq:
        return {"error": f"RFQ {rfq_id} not found"}

    # ── Load email body for extraction context ────────────────────────────────
    # Find the linked email (most recent one linked to this RFQ)
    email_res = await db.execute(
        select(RFQEmail)
        .where(RFQEmail.rfq_id == rfq_id)
        .order_by(RFQEmail.received_at.desc())
        .limit(1)
    )
    linked_email: Optional[RFQEmail] = email_res.scalar_one_or_none()

    # Build a rich context block from the email for the AI extraction prompt
    context_parts: list[str] = []
    if linked_email:
        if linked_email.subject:
            context_parts.append(f"Subject: {linked_email.subject}")
        if linked_email.sender_name or linked_email.sender_email:
            sender = linked_email.sender_name or ""
            if linked_email.sender_email:
                sender = f"{sender} <{linked_email.sender_email}>".strip()
            context_parts.append(f"From: {sender}")
        if linked_email.body_text:
            context_parts.append(f"\nEmail Body:\n{linked_email.body_text}")
    # Also add any RFQ-level fields that were already parsed
    if rfq.client_name:
        context_parts.append(f"Client Name: {rfq.client_name}")
    if rfq.project_name:
        context_parts.append(f"Project Name: {rfq.project_name}")
    if rfq.project_reference:
        context_parts.append(f"Project Reference: {rfq.project_reference}")
    if rfq.scope_summary:
        context_parts.append(f"Scope Summary: {rfq.scope_summary}")

    context_text = "\n".join(context_parts)

    # ── Load all PDF attachments ──────────────────────────────────────────────
    att_res = await db.execute(
        select(RFQAttachment).where(RFQAttachment.rfq_id == rfq_id)
    )
    attachments = att_res.scalars().all()

    pdf_attachments = [
        a for a in attachments
        if (a.original_filename or "").lower().endswith(".pdf")
        or (a.mime_type or "").lower() == "application/pdf"
    ]

    if not pdf_attachments:
        return {"error": "No PDF attachments found for auto costing"}

    combined_members: list = []
    combined_plates: list = []
    combined_project: dict = {}
    processed: list = []
    failed: list = []

    for att in pdf_attachments:
        # Ensure file is downloaded from Gmail if needed
        if not await _ensure_attachment_downloaded(att, db):
            failed.append({"filename": att.original_filename, "reason": "Download failed"})
            continue

        try:
            with open(att.storage_path, "rb") as f:
                pdf_bytes = f.read()
        except OSError as e:
            failed.append({"filename": att.original_filename, "reason": str(e)})
            continue

        try:
            # Pass the email body context so the AI knows who the client is, etc.
            extraction = await extract_from_pdf(pdf_bytes, context_text=context_text)
        except Exception as e:
            logger.warning("Auto costing extraction failed for %s: %s", att.original_filename, e)
            failed.append({"filename": att.original_filename, "reason": str(e)})
            continue

        combined_members.extend(extraction.get("members") or [])
        combined_plates.extend(extraction.get("plates") or [])
        # Prefer project metadata from the first successful extraction
        if not combined_project and extraction.get("project"):
            combined_project = extraction["project"]
        processed.append(att.original_filename)

    if not combined_members and not combined_plates:
        return {
            "error": "No structural members extracted from any PDF",
            "processed": processed,
            "failed": failed,
        }

    combined_extraction = {
        "project": combined_project,
        "members": combined_members,
        "plates": combined_plates,
    }

    try:
        costing = compute_costing(combined_extraction, markup_pct=markup_pct / 100.0)
    except Exception as e:
        logger.error("Auto costing compute failed for RFQ %s: %s", rfq_id, e)
        return {"error": f"Cost calculation failed: {e}", "processed": processed}

    # ── Build customer fields from email + RFQ metadata ───────────────────────
    # Prefer email-extracted project metadata over AI-extracted drawing metadata
    client_name = (
        rfq.client_name
        or combined_project.get("client")
        or (linked_email.sender_name if linked_email else None)
        or ""
    )
    project_name = (
        rfq.project_name
        or combined_project.get("title")
        or (rfq.subject if rfq.subject else "")
    )
    contact_email = (
        rfq.client_email
        or (linked_email.sender_email if linked_email else "")
        or ""
    )

    customer_fields = {
        "customerName": client_name,
        "refNo": rfq.project_reference or rfq.rfq_number,
        "jobNo": rfq.rfq_number,
        "enquiryNo": rfq.project_reference or "",
        "attention": "",
        "contact": contact_email,
    }

    # ── Store result in RFQ metadata ──────────────────────────────────────────
    meta = dict(rfq.extra_metadata or {})
    meta["auto_costing"] = {
        "extraction": combined_extraction,
        "costing": costing,
        "customer": customer_fields,
        "markup_pct": markup_pct,
        "computed_at": datetime.utcnow().isoformat(),
        "source_files": processed,
        "failed_files": failed,
        "email_context_used": bool(context_text),
    }
    rfq.extra_metadata = meta
    rfq.status = "costing_ready"
    await db.flush()

    return {
        "status": "costing_ready",
        "total_steel_kg": costing["total_steel_kg"],
        "selling_price": costing["selling_price"],
        "source_files": processed,
        "failed_files": failed,
        "email_context_used": bool(context_text),
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

HANDLERS = {
    "classify_attachment":   _handle_classify_attachment,
    "extract_attachment":    _handle_extract_attachment,
    "validate_rfq":          _handle_validate_rfq,
    "sync_gmail":            _handle_sync_gmail,
    "process_email":         _handle_process_email,
    "auto_drawing_costing":  _handle_auto_drawing_costing,
}


async def execute_task(task: TaskQueue, db: AsyncSession) -> None:
    """Execute a single task and update its status."""
    handler = HANDLERS.get(task.task_type)
    if not handler:
        task.status = "failed"
        task.error_message = f"Unknown task type: {task.task_type}"
        await db.flush()
        return

    task.status = "running"
    task.started_at = datetime.utcnow()
    task.attempts += 1
    await db.flush()
    logger.info(
        "task_started task_id=%s type=%s entity_type=%s entity_id=%s attempt=%d",
        task.id,
        task.task_type,
        task.entity_type,
        task.entity_id,
        task.attempts,
    )

    try:
        result = await handler(task, db)
        task.status = "completed"
        task.result = result
        task.completed_at = datetime.utcnow()
        logger.info("task_completed task_id=%s type=%s result=%s", task.id, task.task_type, result)
    except Exception as exc:
        logger.exception("Task %s failed: %s", task.id, exc)
        task.status = "failed" if task.attempts >= task.max_attempts else "retrying"
        task.error_message = str(exc)[:2000]
        logger.warning("task_marked_%s task_id=%s type=%s attempts=%d", task.status, task.id, task.task_type, task.attempts)

    await db.flush()


# ---------------------------------------------------------------------------
# Background worker loop
# ---------------------------------------------------------------------------

_worker_running = False


async def run_worker(poll_interval: float = 3.0, max_concurrent: int = 3) -> None:
    """
    Continuously poll the task_queue table and execute pending tasks.
    Designed to be launched as a background asyncio task on app startup.
    """
    global _worker_running
    if _worker_running:
        return
    _worker_running = True
    logger.info("Task queue worker started (poll_interval=%.1fs)", poll_interval)

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_one(task_id: str) -> None:
        async with semaphore:
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    res = await db.execute(select(TaskQueue).where(TaskQueue.id == task_id))
                    task = res.scalar_one_or_none()
                    if task:
                        await execute_task(task, db)

    while True:
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(
                    select(TaskQueue)
                    .where(TaskQueue.status.in_(["pending", "retrying"]))
                    .order_by(TaskQueue.priority, TaskQueue.created_at)
                    .limit(max_concurrent * 2)
                )
                tasks = res.scalars().all()

            task_ids = [t.id for t in tasks]
            if task_ids:
                await asyncio.gather(*[_run_one(tid) for tid in task_ids])
        except Exception as exc:
            logger.error("Worker loop error: %s", exc)

        await asyncio.sleep(poll_interval)


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
