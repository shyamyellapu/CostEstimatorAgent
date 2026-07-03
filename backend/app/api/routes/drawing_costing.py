"""
Drawing Costing API routes — LlamaParse + LLM workflow
=======================================================

New simplified pipeline:
  POST /api/drawing-costing/analyse
    1. Upload files
    2. Parse each file via LlamaParse → clean markdown
    3. Send combined markdown to the configured LLM (AI_PROVIDER env)
    4. Store extracted BOM items in database
    5. Compute deterministic costing
    6. Return reviewable structured result

  GET  /api/drawing-costing/{job_id}/review
  PATCH /api/drawing-costing/{job_id}/bom-items/{item_id}
  POST /api/drawing-costing/{job_id}/recalculate
  POST /api/drawing-costing/{job_id}/approve
  POST /api/drawing-costing/{job_id}/generate-excel
"""
import io
import logging
import math
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.api.deps import db_session
from app.models import (
    Job, UploadedFile, BomItem, QuantityResult, CostingSheet, AuditLog,
)
from app.services.file_storage import storage_service
from app.services.llama_parser import parse_to_markdown, save_parsed_markdown, is_useful_markdown, pdf_to_page_images
from app.ai import get_ai_provider
from app.ai.prompts import LLAMAPARSE_BOQ_EXTRACTION_PROMPT, SYSTEM_PROMPT_ENGINEER

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024   # 100 MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".xlsx", ".docx"}


def _gen_job_number() -> str:
    return f"DC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _safe_job_no(s: str) -> str:
    return "".join(c for c in str(s) if c.isalnum() or c in "-_.")


# ---------------------------------------------------------------------------
# POST /analyse
# ---------------------------------------------------------------------------
@router.post("/analyse")
async def analyse_drawing(
    files: List[UploadFile] = File(...),
    markup_pct: float = Form(34.0),
    db: AsyncSession = Depends(db_session),
):
    """
    Upload drawing package → LlamaParse → LLM extraction → deterministic costing.
    Returns structured reviewable result. Does NOT auto-generate Excel.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if not (0 <= markup_pct <= 80):
        raise HTTPException(status_code=400, detail="markup_pct must be between 0 and 80.")

    job = Job(job_number=_gen_job_number(), status="extracting")
    db.add(job)
    await db.flush()
    job_id = str(job.id)

    combined_markdown_parts: List[str] = []

    for upload in files:
        fname = upload.filename or "upload"
        ext = Path(fname).suffix.lower()
        ct = (upload.content_type or "").lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: '{fname}'")

        file_bytes = await upload.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File '{fname}' exceeds 100 MB limit.")
        if not file_bytes:
            raise HTTPException(status_code=400, detail=f"File '{fname}' is empty.")

        # Save to storage
        storage = await storage_service.save_upload(file_bytes, fname, job_id)
        uf = UploadedFile(
            job_id=job_id,
            original_filename=fname,
            stored_filename=storage["stored_filename"],
            file_type=ext.lstrip(".") or "pdf",
            file_origin="upload",
            mime_type=ct or "application/octet-stream",
            file_size=storage["file_size"],
            storage_path=storage["storage_path"],
            storage_url=storage.get("storage_url"),
            storage_provider=storage.get("storage_provider"),
            blob_reference=storage.get("blob_reference"),
            checksum_sha256=storage.get("checksum_sha256"),
            is_processed="pending",
            processing_status="uploading",
            metadata_json={"source": "drawing_workflow"},
        )
        db.add(uf)
        await db.flush()

        # ── LlamaParse (with cache) ─────────────────────────────────────────
        llama_ok = False
        markdown = None

        # Check for a previously parsed .md file — avoids re-parsing during testing
        cached_md = _find_cached_markdown(fname)
        if cached_md:
            logger.info("Job %s: using cached LlamaParse result for '%s' ← %s", job_id, fname, cached_md)
            try:
                import aiofiles as _af
                async with _af.open(cached_md, "r", encoding="utf-8") as _f:
                    markdown = await _f.read()
            except Exception as _ce:
                logger.warning("Job %s: could not read cached file %s: %s", job_id, cached_md, _ce)
                markdown = None

        if markdown is None:
            try:
                markdown = await parse_to_markdown(file_bytes, fname)
                await save_parsed_markdown(markdown, fname, job_id)
            except Exception as exc:
                logger.error("Job %s: LlamaParse failed for '%s': %s", job_id, fname, exc)

        if markdown is not None:
            # Treat result as unusable if it's too short or dominated by binary stream markers
            if not is_useful_markdown(markdown):
                logger.warning(
                    "Job %s: LlamaParse returned low-quality markdown for '%s' (%d chars) — "
                    "will fall back to LLM vision",
                    job_id, fname, len(markdown),
                )
            else:
                combined_markdown_parts.append(f"## File: {fname}\n\n{markdown}")
                uf.processing_status = "completed"
                uf.is_processed = "done"
                llama_ok = True
                logger.info("Job %s: LlamaParse ready for '%s' (%d chars)", job_id, fname, len(markdown))
            uf.processing_status = "failed"

        # Vision fallback: convert PDF pages to PNG then send to the LLM vision API
        if not llama_ok and ext in {".pdf", ".png", ".jpg", ".jpeg"}:
            try:
                ai_fb = get_ai_provider()
                logger.info("Job %s: vision fallback via %s for '%s'", job_id, ai_fb.provider_name, fname)

                if ext == ".pdf":
                    # Convert PDF pages to PNG images (max 8 pages, low DPI to stay within size limits)
                    page_images = pdf_to_page_images(file_bytes, max_pages=8, dpi=120)
                    if not page_images:
                        raise RuntimeError("PDF rendered 0 pages")
                    extracted_fb = await ai_fb.extract_from_image(page_images, fname)
                else:
                    extracted_fb = await ai_fb.extract_from_image(file_bytes, fname)

                import json as _json
                fb_text = _json.dumps(
                    extracted_fb.model_dump() if hasattr(extracted_fb, "model_dump") else vars(extracted_fb),
                    default=str,
                )
                combined_markdown_parts.append(f"## File: {fname} (vision fallback)\n\n{fb_text}")
                uf.processing_status = "completed"
                uf.is_processed = "done"
                logger.info("Job %s: vision fallback produced %d chars for '%s'", job_id, len(fb_text), fname)
            except Exception as fb_exc:
                logger.error("Job %s: vision fallback failed for '%s': %s", job_id, fname, fb_exc)
                # Last resort — raw UTF-8 decode (works for text-based files)
                try:
                    raw_text = file_bytes.decode("utf-8", errors="ignore")
                    if len(raw_text.strip()) > 100:
                        combined_markdown_parts.append(f"## File: {fname}\n\n{raw_text}")
                        uf.processing_status = "completed"
                        uf.is_processed = "done"
                except Exception:
                    pass

    if not combined_markdown_parts:
        job.status = "failed"
        await db.commit()
        raise HTTPException(status_code=422, detail="No parseable content found in uploaded files.")

    combined_text = "\n\n---\n\n".join(combined_markdown_parts)

    # Send combined parsed text to the configured LLM using focused BOQ prompt
    ai = get_ai_provider()
    logger.info("Job %s: %d chars from LlamaParse → %s", job_id, len(combined_text), ai.provider_name)

    # Token-safe limits (engineering markdown ≈ 2.4 chars/token — much denser than prose)
    # Groq llama-4-scout: 30K TPM → budget ~22K tokens for doc (~52K chars)
    # Claude / OpenAI: large context, no tight per-minute limit
    _CHAR_LIMITS = {
        "groq":       35_000,   # ~14.6K tokens — well under 30K TPM (prompt adds ~3-4K)
        "openai":    380_000,
        "claude":    380_000,
        "openrouter": 380_000,
        "gemini":    380_000,   # Gemini 3 Flash has 1M token context
    }
    MAX_CHARS = _CHAR_LIMITS.get(ai.provider_name, 50_000)

    if len(combined_text) > MAX_CHARS:
        logger.warning(
            "Job %s: truncating %d chars → %d for provider '%s'",
            job_id, len(combined_text), MAX_CHARS, ai.provider_name,
        )
        combined_text = combined_text[:MAX_CHARS]

    logger.info(
        "Job %s: sending %d chars to %s",
        job_id, len(combined_text), ai.provider_name,
    )

    prompt = LLAMAPARSE_BOQ_EXTRACTION_PROMPT.format(text=combined_text)

    try:
        chat_resp = await ai.chat(
            messages=[{"role": "user", "content": prompt}],
            context=None,  # system prompt already set inside each provider
        )
        raw_json = chat_resp.content if hasattr(chat_resp, "content") else str(chat_resp)
    except Exception as exc:
        logger.error("Job %s: LLM extraction failed: %s", job_id, exc, exc_info=True)
        job.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {exc}")

    # ── Full raw LLM response — logged to console AND log file ───────────────
    logger.info(
        "Job %s: ═══ RAW LLM RESPONSE (%d chars) ═══\n%s\n═══ END RAW LLM RESPONSE ═══",
        job_id, len(raw_json), raw_json,
    )

    # Parse the JSON response
    import json
    from json_repair import repair_json
    try:
        extracted = json.loads(raw_json)
    except Exception:
        try:
            extracted = json.loads(repair_json(raw_json))
        except Exception as parse_exc:
            logger.error("Job %s: JSON parse failed: %s\nRaw: %s", job_id, parse_exc, raw_json[:500])
            extracted = {}

    logger.info(
        "Job %s: ═══ PARSED EXTRACTION ═══\n%s\n═══ END EXTRACTION ═══",
        job_id, json.dumps(extracted, indent=2),
    )

    # ── Map extracted fields → BomItem records ──────────────────────────────
    bom_items_out: List[Dict] = []

    def _add_bom(description: str, category: str, weight_kg: float | None,
                 qty: float | None, confidence: float, extra: dict | None = None) -> None:
        bi = BomItem(
            job_id=job_id,
            description=description,
            category=category,
            qty=qty,
            total_weight_kg=weight_kg,
            confidence=confidence,
            review_required=confidence < 0.7,
            **(extra or {}),
        )
        db.add(bi)

    # 1. Structural Steel
    ss = extracted.get("structural_steel") or {}
    ss_kg = float(ss.get("weight_kg") or 0)
    ss_conf = float(ss.get("confidence") or 0.8)
    if ss_kg > 0:
        _add_bom(
            description=f"Structural Steel Material — {ss.get('source_description', '')}",
            category="structural_steel",
            weight_kg=ss_kg,
            qty=None,
            confidence=ss_conf,
        )

    # 2. Handrails
    hr = extracted.get("handrails") or {}
    hr_kg = float(hr.get("weight_kg") or 0)
    hr_linear_m = float(hr.get("linear_m") or 0)
    hr_conf = float(hr.get("confidence") or 0.5)
    # Fallback: if LLM returned linear_m but no weight_kg, calculate using 42NB pipe default (5.41 kg/m)
    if hr_kg == 0 and hr_linear_m > 0:
        hr_kg = round(hr_linear_m * 5.41, 2)
        logger.info("Handrail weight calculated from linear_m: %.1f m × 5.41 kg/m = %.1f kg", hr_linear_m, hr_kg)
    if hr_kg > 0 or hr_linear_m > 0:
        _add_bom(
            description=f"Handrails — {hr.get('source_description', 'not stated')}",
            category="handrail",
            weight_kg=hr_kg or None,
            qty=hr_linear_m or None,
            confidence=hr_conf,
        )

    # 3. Grating
    gr = extracted.get("grating") or {}
    gr_kg = float(gr.get("weight_kg") or 0)
    gr_conf = float(gr.get("confidence") or 0.5)
    if gr_kg > 0 or gr.get("area_m2"):
        _add_bom(
            description=f"Grating — {gr.get('source_description', 'not stated')}",
            category="grating",
            weight_kg=gr_kg or None,
            qty=gr.get("area_m2"),
            confidence=gr_conf,
        )

    # 4. M20×90 Bolts
    bl = extracted.get("bolts_m20x90") or {}
    if bl.get("found") and bl.get("qty"):
        _add_bom(
            description=bl.get("description") or "M20×90 Long Bolts HEX HD & Nut to BS 4190 Gr.8.8",
            category="bolt",
            weight_kg=None,
            qty=float(bl.get("qty") or 0),
            confidence=0.9,
        )
    for ob in (bl.get("other_bolts") or []):
        # Handle both dict and string formats from LLM response
        if isinstance(ob, dict):
            desc = ob.get("description") or f"{ob.get('size', 'Bolt')} Gr.{ob.get('grade', '8.8')}"
            qty = float(ob.get("qty") or 0)
        else:
            # LLM returned a simple string like "M16" or "M20"
            desc = str(ob)
            qty = 0  # No quantity specified
        
        if qty > 0:  # Only add if qty is specified
            _add_bom(
                description=desc,
                category="bolt",
                weight_kg=None,
                qty=qty,
                confidence=0.8,
            )

    # 5. Paint Material
    pm = extracted.get("paint_material") or {}
    pm_litres = float(pm.get("litres") or 0)
    pm_conf = float(pm.get("confidence") or 0.7)
    if pm_litres > 0:
        spec = pm.get("paint_spec") or ""
        method = pm.get("paint_calc_method") or ""
        _add_bom(
            description=f"Paint Material — {spec} ({method})",
            category="paint",
            weight_kg=None,
            qty=pm_litres,   # qty = litres for paint
            confidence=pm_conf,
        )

    await db.flush()

    # Re-query to get IDs
    bom_result = await db.execute(select(BomItem).where(BomItem.job_id == job_id))
    bom_items_out = [_bom_item_to_dict(i) for i in bom_result.scalars().all()]

    # Resolve total steel weight
    total_steel_kg = ss_kg

    # Deterministic costing
    costing = _compute_costing(total_steel_kg, markup_pct / 100.0)

    overall_confidence = float(extracted.get("overall_confidence") or 0.8)

    # Store quantity result
    qr = QuantityResult(
        job_id=job_id,
        category="structural_steel",
        quantity_unit="kg",
        quantity_value=total_steel_kg,
        weight_kg=total_steel_kg,
        source="llm_extraction",
        calculation_method="llama_parse_boq_prompt",
        confidence=overall_confidence,
        is_approved=False,
    )
    db.add(qr)

    job.status = "pending_review"
    job.total_weight_kg = total_steel_kg

    db.add(AuditLog(
        job_id=job_id,
        action="llama_parse_extraction_complete",
        details_json={
            "bom_items": len(bom_items_out),
            "total_steel_kg": total_steel_kg,
            "confidence": overall_confidence,
            "provider": ai.provider_name,
            "paint_litres": pm_litres,
            "bolts_found": bl.get("found", False),
        },
    ))
    await db.commit()

    return {
        "job_id": job_id,
        "job_number": job.job_number,
        "project_information": {
            "project_name": job.project_name,
            "client_name": job.client_name,
            "drawing_number": None,
        },
        "bom_items": bom_items_out,
        "total_steel_kg": round(total_steel_kg, 2),
        "costing": costing,
        "overall_confidence": overall_confidence,
        "summary": extracted.get("summary") or f"Extracted {len(bom_items_out)} items. Steel: {round(total_steel_kg, 1)} kg.",
        "flags": [],
        "extracted_detail": {
            "structural_steel": extracted.get("structural_steel"),
            "handrails": extracted.get("handrails"),
            "grating": extracted.get("grating"),
            "bolts_m20x90": extracted.get("bolts_m20x90"),
            "paint_material": extracted.get("paint_material"),
        },
        "status": "pending_review",
        "can_generate_excel": True,
        "markup_pct": markup_pct,
    }


# ---------------------------------------------------------------------------
# GET /{job_id}/review
# ---------------------------------------------------------------------------
@router.get("/{job_id}/review")
async def get_review(job_id: str, db: AsyncSession = Depends(db_session)):
    """Return the full review payload for a job."""
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    bom_result = await db.execute(select(BomItem).where(BomItem.job_id == job_id))
    bom_items = [_bom_item_to_dict(i) for i in bom_result.scalars().all()]

    qty_result = await db.execute(select(QuantityResult).where(QuantityResult.job_id == job_id))
    quantities = [
        {
            "id": str(q.id), "category": q.category,
            "weight_kg": q.weight_kg, "confidence": q.confidence,
            "is_approved": q.is_approved,
        }
        for q in qty_result.scalars().all()
    ]

    total_steel_kg = sum(
        float(q["weight_kg"] or 0) for q in quantities
        if q.get("category") == "structural_steel"
    )

    return {
        "job_id": job_id,
        "job_number": job.job_number,
        "status": job.status,
        "can_generate_excel": True,
        "bom_items": bom_items,
        "quantity_results": quantities,
        "total_steel_kg": round(total_steel_kg, 2),
    }


# ---------------------------------------------------------------------------
# PATCH /{job_id}/bom-items/{item_id}
# ---------------------------------------------------------------------------
class BomItemUpdate(BaseModel):
    description: Optional[str] = None
    qty: Optional[float] = None
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    unit_weight_kg: Optional[float] = None
    total_weight_kg: Optional[float] = None
    material_grade: Optional[str] = None
    category: Optional[str] = None
    review_required: Optional[bool] = None


@router.patch("/{job_id}/bom-items/{item_id}")
async def update_bom_item(
    job_id: str,
    item_id: str,
    body: BomItemUpdate,
    db: AsyncSession = Depends(db_session),
):
    result = await db.execute(
        select(BomItem).where(BomItem.id == item_id, BomItem.job_id == job_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="BOM item not found.")

    for key, value in body.model_dump(exclude_none=True).items():
        setattr(item, key, value)

    await db.commit()
    await db.refresh(item)
    return _bom_item_to_dict(item)


# ---------------------------------------------------------------------------
# POST /{job_id}/recalculate
# ---------------------------------------------------------------------------
@router.post("/{job_id}/recalculate")
async def recalculate(
    job_id: str,
    markup_pct: float = 34.0,
    db: AsyncSession = Depends(db_session),
):
    """Re-run deterministic costing from stored (possibly edited) BOM items."""
    bom_result = await db.execute(select(BomItem).where(BomItem.job_id == job_id))
    bom_items = bom_result.scalars().all()

    total_steel_kg = sum(
        float(b.total_weight_kg or 0)
        for b in bom_items
        if b.category == "structural_steel"
    )

    costing = _compute_costing(total_steel_kg, markup_pct / 100.0)

    await db.execute(
        update(QuantityResult)
        .where(QuantityResult.job_id == job_id, QuantityResult.category == "structural_steel")
        .values(weight_kg=total_steel_kg, quantity_value=total_steel_kg)
    )
    await db.execute(
        update(Job).where(Job.id == job_id).values(total_weight_kg=total_steel_kg)
    )
    db.add(AuditLog(
        job_id=job_id,
        action="recalculate",
        details_json={"total_steel_kg": total_steel_kg, "markup_pct": markup_pct},
    ))
    await db.commit()

    return {
        "job_id": job_id,
        "total_steel_kg": round(total_steel_kg, 2),
        "costing": costing,
        "status": "pending_review",
        "can_generate_excel": True,
    }


# ---------------------------------------------------------------------------
# POST /{job_id}/approve
# ---------------------------------------------------------------------------
@router.post("/{job_id}/approve")
async def approve_quantities(job_id: str, db: AsyncSession = Depends(db_session)):
    await db.execute(
        update(QuantityResult).where(QuantityResult.job_id == job_id).values(is_approved=True)
    )
    await db.execute(
        update(Job).where(Job.id == job_id).values(status="approved")
    )
    db.add(AuditLog(
        job_id=job_id,
        action="drawing_workflow_approved",
        details_json={"approved_at": datetime.utcnow().isoformat()},
    ))
    await db.commit()
    return {"job_id": job_id, "status": "approved", "can_generate_excel": True}


# ---------------------------------------------------------------------------
# POST /{job_id}/generate-excel
# ---------------------------------------------------------------------------
class GenerateExcelRequest(BaseModel):
    customer: Dict[str, Any] = Field(default_factory=dict)
    markup_pct: float = Field(34.0, ge=0, le=80)


@router.post("/{job_id}/generate-excel")
async def generate_excel_endpoint(
    job_id: str,
    body: GenerateExcelRequest,
    db: AsyncSession = Depends(db_session),
):
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    qty_result = await db.execute(select(QuantityResult).where(QuantityResult.job_id == job_id))
    quantities = {q.category: q for q in qty_result.scalars().all()}

    total_steel_kg = float(
        getattr(quantities.get("structural_steel"), "weight_kg", 0) or 0
    )
    costing = _compute_costing(total_steel_kg, body.markup_pct / 100.0)

    # Pull LLM-extracted BOM values from DB and override ratio-derived quantities
    bom_result = await db.execute(select(BomItem).where(BomItem.job_id == job_id))
    bom_items = bom_result.scalars().all()

    extracted_bolt_qty = next(
        (float(b.qty or 0) for b in bom_items if b.category == "bolt" and float(b.qty or 0) > 0), None
    )
    extracted_paint_litres = next(
        (float(b.qty or 0) for b in bom_items if b.category == "paint" and float(b.qty or 0) > 0), None
    )
    extracted_handrail_kg = next(
        (float(b.total_weight_kg or 0) for b in bom_items if b.category == "handrail"), None
    )
    extracted_grating_kg = next(
        (float(b.total_weight_kg or 0) for b in bom_items if b.category == "grating"), None
    )

    # Override ratio-derived values with LLM-extracted ones when available
    if extracted_bolt_qty is not None:
        costing["bolts"] = int(extracted_bolt_qty)
    if extracted_paint_litres is not None:
        costing["paint_litres"] = round(extracted_paint_litres, 3)
    if extracted_handrail_kg is not None:
        costing["handrail_kg"] = round(extracted_handrail_kg, 2)
    if extracted_grating_kg is not None:
        costing["grating_kg"] = round(extracted_grating_kg, 2)

    from app.services.drawing_costing import generate_excel
    project_info = {
        "drawing_no": body.customer.get("jobNo") or job.job_number,
        "title": job.project_name or "",
        "client": job.client_name or "",
        "contractor": "",
    }
    try:
        buf = generate_excel(costing, project_info, body.customer)
    except Exception as exc:
        logger.error("Excel generation failed for job %s: %s", job_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Excel generation failed.")

    job_no_safe = _safe_job_no(body.customer.get("jobNo") or job.job_number)
    filename = f"JobCosting_{job_no_safe}.xlsx"
    excel_bytes = buf.getvalue()

    storage = await storage_service.save_output(excel_bytes, filename, job_id)
    db.add(UploadedFile(
        job_id=job_id,
        original_filename=filename,
        stored_filename=storage["stored_filename"],
        file_type="excel",
        file_origin="generated",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_size=storage["file_size"],
        storage_path=storage["storage_path"],
        storage_url=storage.get("storage_url"),
        is_processed="done",
        processing_status="completed",
        metadata_json={"source": "drawing_workflow_excel"},
    ))
    db.add(CostingSheet(
        job_id=job_id,
        line_items_json=costing,
        totals_json=costing,
        rates_snapshot_json={"markup_pct": body.markup_pct},
        audit_trail_json=[{
            "event": "excel_generated",
            "created_at": datetime.utcnow().isoformat(),
        }],
        excel_path=storage["storage_path"],
        excel_url=storage.get("storage_url"),
    ))
    db.add(AuditLog(
        job_id=job_id,
        action="drawing_workflow_excel_generated",
        details_json={"filename": filename, "markup_pct": body.markup_pct},
    ))
    await db.commit()

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bom_item_to_dict(item: BomItem) -> Dict:
    return {
        "id": str(item.id),
        "description": item.description,
        "category": item.category,
        "section_type": item.section_type,
        "section_size": item.section_size,
        "material_grade": item.material_grade,
        "qty": item.qty,
        "length_mm": item.length_mm,
        "width_mm": item.width_mm,
        "thickness_mm": item.thickness_mm,
        "unit_weight_kg": item.unit_weight_kg,
        "total_weight_kg": item.total_weight_kg,
        "confidence": item.confidence,
        "review_required": item.review_required,
    }


def _extract_boq_relevant_lines(text: str) -> str:
    """
    Keep only lines that are likely to contain BOQ-relevant data.

    Engineering PDFs have tons of revision tables, title blocks, drawing notes,
    and geometry that are useless for BOQ extraction but burn Groq TPM.
    This filter retains lines that mention structural members, weights, bolts,
    paint, handrail, or grating — the five categories in our BOQ prompt.
    """
    import re

    KEEP_PATTERNS = re.compile(
        r"""
        \b(
            steel | structural | fabricat | section | member | beam | column |
            UB | UC | RHS | SHS | CHS | PFC | flat\s*bar | angle | plate |
            kg | tonne | ton | weight | mass |
            bolt | nut | washer | M\d{2} | anchor |
            paint | coat | primer | epoxy | litr | l\b |
            handrail | railing | rail | balustrade |
            grating | grate | chequer | chequered |
            total | qty | quantity | no\.\s*of | number\s*of |
            \d+\s*mm | \d+\s*x\s*\d+ | \d+\.\d+
        )\b
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Always keep table rows (contain | or tabs separating columns)
        if "|" in stripped or "\t" in stripped:
            kept.append(line)
        elif KEEP_PATTERNS.search(stripped):
            kept.append(line)

    result = "\n".join(kept)
    # If filtering removed too much (< 10% remains), return original — better to
    # over-send than to silently lose all data on an atypical document format.
    if len(result) < max(500, len(text) * 0.10):
        return text
    return result


def _find_cached_markdown(filename: str) -> "Path | None":
    """
    Return the most recently saved LlamaParse .md file for this filename, or None.
    Searches storage/llama_parsed/<any-job-id>/<stem>.md.
    Used to skip re-parsing during testing.
    """
    from app.config import settings as _settings
    stem = Path(filename).stem
    base = Path(_settings.local_storage_path) / "llama_parsed"
    if not base.exists():
        return None
    candidates = sorted(base.glob(f"*/{stem}.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _compute_costing(total_steel_kg: float, markup_pct: float = 0.34) -> Dict[str, Any]:
    """Pure Python deterministic costing from total steel weight. No LLM."""
    from app.services.drawing_costing import RATIOS

    surface_area = round(total_steel_kg * RATIOS["surfaceAreaPerKg"])
    bolts = math.ceil(total_steel_kg / 1000 * RATIOS["boltsPer1000Kg"])
    paint_litres = math.ceil(surface_area * RATIOS["paintLitresPerSqm"])
    mpi_visits = max(1, math.ceil(total_steel_kg / 1000 * RATIOS["mpiVisitsPer1000Kg"]))
    welding_mh = math.ceil(total_steel_kg * RATIOS["weldingMHPerKg"])
    fabrication_mh = math.ceil(total_steel_kg * RATIOS["fabricationMHPerKg"])

    steel_mat_cost  = total_steel_kg * RATIOS["rateSteelPerKg"]
    bolt_cost       = bolts          * RATIOS["rateBoltPerNo"]
    paint_mat_cost  = paint_litres   * RATIOS["ratePaintPerLitre"]
    weld_cost       = welding_mh     * RATIOS["rateWeldingPerMH"]
    fab_cost        = fabrication_mh * RATIOS["rateFabricationPerMH"]
    blast_cost      = surface_area   * RATIOS["rateBlastingPerSqm"]
    paint_app_cost  = surface_area   * RATIOS["ratePaintingPerSqm"]
    mpi_cost        = mpi_visits     * RATIOS["rateMPIPerVisit"]
    qaqc_cost       = RATIOS["rateQAQC"]
    packing_cost    = RATIOS["ratePacking"]

    subtotal = (
        steel_mat_cost + bolt_cost + paint_mat_cost + weld_cost + fab_cost
        + blast_cost + paint_app_cost + mpi_cost + qaqc_cost + packing_cost
    )

    oh_rate     = 230000 / 30 / 30 / 8
    blast_mh    = (1 / 13.3) * surface_area * 3
    paint_mh    = (1 / 6.65) * surface_area * 3
    overhead    = oh_rate * (welding_mh + fabrication_mh + blast_mh + paint_mh)

    selling_price = (subtotal + overhead) * (1 + markup_pct)
    consumables   = selling_price / 20
    grand_total   = subtotal + consumables + overhead
    net_profit    = selling_price - grand_total
    profit_pct    = (net_profit / selling_price * 100) if selling_price else 0.0

    return {
        "total_steel_kg":     round(total_steel_kg, 2),
        "surface_area_sqm":   int(surface_area),
        "bolts":              bolts,
        "paint_litres":       paint_litres,
        "mpi_visits":         mpi_visits,
        "welding_mh":         welding_mh,
        "fabrication_mh":     fabrication_mh,
        "steel_mat_cost":     round(steel_mat_cost, 2),
        "bolt_cost":          round(bolt_cost, 2),
        "paint_mat_cost":     round(paint_mat_cost, 2),
        "weld_cost":          round(weld_cost, 2),
        "fab_cost":           round(fab_cost, 2),
        "blast_cost":         round(blast_cost, 2),
        "paint_app_cost":     round(paint_app_cost, 2),
        "mpi_cost":           round(mpi_cost, 2),
        "qaqc_cost":          round(qaqc_cost, 2),
        "packing_cost":       round(packing_cost, 2),
        "subtotal":           round(subtotal, 2),
        "overhead":           round(overhead, 2),
        "consumables":        round(consumables, 2),
        "grand_total":        round(grand_total, 2),
        "selling_price":      round(selling_price, 2),
        "net_profit":         round(net_profit, 2),
        "profit_pct":         round(profit_pct, 2),
        "markup_pct":         round(markup_pct * 100, 2),
    }
