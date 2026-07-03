"""
Drawing Costing Service
-----------------------
Handles the full pipeline for Job Costing Sheet automation from a drawing PDF:
  1. Calls Claude vision API with the structural steel takeoff prompt
  2. Computes steel weight from extracted members + plates
  3. Computes all derived quantities and cost line items
  4. Resolves the D58 ↔ J33 circular reference
  5. Stamps computed values into the Sample Job Costing Sheet.xlsx template
     (preserving all formatting, merges, and pre-built formulas)
"""
import base64
import json
import logging
import math
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import openpyxl

from app.config import settings
from app.ai.prompts import IMAGE_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

# Claude's API limit for base64-encoded PDFs is 32 MB.
# base64 inflates size by ~33%, so the original file must be ≤ 24 MB.
CLAUDE_MAX_PDF_BYTES = 24 * 1024 * 1024

# ---------------------------------------------------------------------------
# Section-weight lookup table (kg/m)
# ---------------------------------------------------------------------------
SECTION_WEIGHTS: Dict[str, float] = {
    # Universal Columns
    "UC 152x152x23": 23.0,  "UC 152x152x30": 30.0,  "UC 152x152x37": 37.0,
    "UC 203x203x46": 46.1,  "UC 203x203x52": 52.0,  "UC 203x203x60": 60.0,
    # Universal Beams
    "UB 127x76x13":  13.0,  "UB 152x89x16":  16.0,  "UB 178x102x19": 19.0,
    "UB 203x102x23": 23.1,  "UB 203x133x25": 25.1,  "UB 203x133x30": 30.0,
    # Split tees — UCT weight = parent UC weight / 2; UBT weight = parent UB weight / 2
    # Source: SCI Blue Book. Verified against C&J calibration job CNJ-142676
    # (authoritative weight: 7802.27 kg). DO NOT change without re-verifying.
    "UCT 152x152x15":  15.0, "UCT 152x152x11.5": 11.5, "UCT 152x152x18.5": 18.5,
    "UCT 203x203x23":  23.0, "UCT 203x203x26":   26.0, "UCT 203x203x30":   30.0,
    "UCT 203x203x35.5":35.5, "UCT 203x203x43":   43.0, "UCT 203x203x46":   23.0,
    "UCT 203x203x52":  26.0, "UCT 254x254x36.5": 36.5, "UCT 254x254x44.5": 44.5,
    "UCT 254x254x53.5":53.5, "UCT 254x254x73":   36.5, "UCT 254x254x89":   44.5,
    "UCT 254x254x107": 53.5, "UCT 305x305x48.5": 48.5, "UCT 305x305x59":   59.0,
    "UCT 305x305x68.5":68.5, "UCT 305x305x79":   79.0, "UCT 305x305x97":   48.5,
    "UCT 305x305x118": 59.0, "UCT 305x305x137":  68.5, "UCT 305x305x158":  79.0,
    "UCT 356x368x64.5":64.5, "UCT 356x368x76.5": 76.5, "UCT 356x368x88.5": 88.5,
    "UCT 356x368x129": 64.5, "UCT 356x368x153":  76.5, "UCT 356x368x177":  88.5,
    "UBT 127x76x6.5":   6.5, "UBT 127x76x13":     6.5, "UBT 152x89x8":     8.0,
    "UBT 152x89x16":    8.0, "UBT 178x102x9.5":   9.5, "UBT 178x102x19":   9.5,
    "UBT 203x102x11.5":11.5, "UBT 203x102x23":   11.5, "UBT 254x102x12.5":12.5,
    "UBT 254x102x25":  12.5, "UBT 254x102x14":   14.0, "UBT 254x102x28":   14.0,
    "UBT 254x146x15.5":15.5, "UBT 254x146x31":   15.5, "UBT 254x146x18.5":18.5,
    "UBT 254x146x37":  18.5, "UBT 305x102x14":   14.0, "UBT 305x102x28":   14.0,
    "UBT 305x127x18.5":18.5, "UBT 305x127x37":   18.5, "UBT 305x165x20":   20.0,
    "UBT 305x165x40":  20.0, "UBT 305x165x23":   23.0, "UBT 305x165x46":   23.0,
    "UBT 356x127x16.5":16.5, "UBT 356x127x33":   16.5, "UBT 356x171x22.5":22.5,
    "UBT 356x171x45":  22.5, "UBT 356x171x25.5": 25.5, "UBT 356x171x51":   25.5,
    "UBT 406x140x19.5":19.5, "UBT 406x140x39":   19.5, "UBT 406x178x27":   27.0,
    "UBT 406x178x54":  27.0, "UBT 457x152x26":   26.0, "UBT 457x152x52":   26.0,
    "UBT 457x191x33.5":33.5, "UBT 457x191x67":   33.5, "UBT 533x210x41":   41.0,
    "UBT 533x210x82":  41.0, "UBT 133x101x15":   15.0, "UBT 133x102x15":   15.0,
    # Parallel Flange Channels
    "PFC 100x50x10": 10.2,  "PFC 125x65x15": 14.8,  "PFC 150x75x18": 17.9,
    "PFC 150x90x24": 23.9,  "PFC 180x90x26": 26.1,  "PFC 200x75x23": 23.4,
    "PFC 230x75x26": 25.7,  "PFC 230x90x32": 32.2,
    # Equal Angles
    "L 50x50x6":  4.47,  "L 75x75x8":  8.99,
    "L 100x100x10": 15.0, "L 100x100x12": 17.8, "L 150x150x12": 27.3,
}

PLATE_DENSITY = 7.85   # kg per m² per mm thickness

# ---------------------------------------------------------------------------
# Derived-ratio constants (reverse-engineered from drawing 1349001-B)
# ---------------------------------------------------------------------------
RATIOS: Dict[str, float] = {
    "paintLitresPerSqm":   0.6,
    "surfaceAreaPerKg":    0.02564,
    "boltsPer1000Kg":      3.85,
    "mpiVisitsPer1000Kg":  1.28,
    "weldingMHPerKg":      0.02050,
    "fabricationMHPerKg":  0.04101,
    # Unit rates (AED)
    "rateSteelPerKg":       4.0,
    "rateBoltPerNo":        12.5,
    "ratePaintPerLitre":    21.0,
    "rateWeldingPerMH":     10.5,
    "rateFabricationPerMH": 9.5,
    "rateBlastingPerSqm":   9.0,
    "ratePaintingPerSqm":   11.0,
    "rateMPIPerVisit":      600.0,
    "rateQAQC":             3000.0,
    "ratePacking":          3000.0,
    "defaultMarkupPct":     0.34,
}

# ---------------------------------------------------------------------------
# Vision extraction prompt — imported from app.ai.prompts
# IMAGE_EXTRACTION_PROMPT enforces a 5-pass extraction process with:
#   TYP multipliers, revision cloud exclusions, and tag enumeration cross-check.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helper: fallback weight for sections not in lookup table
# ---------------------------------------------------------------------------
def estimate_section_weight(section: str) -> float:
    m = re.search(r"(\d+)x(\d+)x(\d+)", section or "")
    if not m:
        return 25.0
    thk = int(m.group(3))
    return max(8.0, float(thk) * 1.0)


def get_kg_per_m(section: str) -> tuple[float, bool]:
    """Return (kg/m, is_estimated). Tries exact lookup, then normalised lookup, then fallback."""
    if section in SECTION_WEIGHTS:
        return SECTION_WEIGHTS[section], False
    # Normalise spacing (e.g. "UC152x152x30" → "UC 152x152x30")
    normalised = re.sub(r"([A-Za-z]+)(\d)", r"\1 \2", section).strip()
    if normalised in SECTION_WEIGHTS:
        return SECTION_WEIGHTS[normalised], False
    return estimate_section_weight(section), True


# ---------------------------------------------------------------------------
# Step 1: Call AI vision API (OpenAI primary / Claude fallback)
# ---------------------------------------------------------------------------
def _build_prompt(context_text: str) -> str:
    """
    Build the final extraction prompt, injecting the email body as context
    so the AI can correctly identify the client, project reference, and scope.
    """
    if not context_text or not context_text.strip():
        return IMAGE_EXTRACTION_PROMPT
    header = (
        "=== EMAIL / RFQ CONTEXT (use to populate project.client, project.title, etc.) ===\n"
        + context_text.strip()[:3000]   # cap to avoid token overflow
        + "\n=== END OF EMAIL CONTEXT ===\n\n"
    )
    return header + IMAGE_EXTRACTION_PROMPT


def _looks_like_valid_takeoff(result: dict) -> bool:
    """Multi-gate validation: extraction is usable only if it passes all gates."""
    INVALID_TOKENS = {"", "unknown", "n/a", "na", "tbd", "?", "-", "none"}

    # Support both old schema (members/plates) and new schema
    members = (
        result.get("structural_elements") or
        result.get("members") or []
    )
    plates = (
        result.get("bolts_and_plates") or
        result.get("plates") or []
    )

    # Gate 1: Minimum meaningful item count
    # A real drawing always has at least 2 structural members
    if len(members) < 2 and len(plates) < 1:
        return False
    if len(members) < 1:
        return False

    # Gate 2: At least one section designation that looks real
    valid_sections = [
        m for m in members
        if str(m.get("section", "")).strip().lower() not in INVALID_TOKENS
    ]
    if not valid_sections:
        return False

    # Gate 3: At least one member has usable geometry (length or weight)
    has_geometry = False
    for m in members:
        length = (
            m.get("total_length_m") or
            m.get("length_m") or
            (float(m.get("length_mm", 0)) / 1000)
        )
        weight = m.get("weight_kg") or m.get("total_weight_kg") or 0
        if (length and float(length) > 0.05) or (weight and float(weight) > 1):
            has_geometry = True
            break
    if not has_geometry:
        return False

    # Gate 4: LLM did not explicitly signal failure
    if result.get("error") or result.get("extraction_failed"):
        return False
    completeness = result.get("completeness_check", {})
    if completeness.get("extraction_failed"):
        return False

    # Gate 5: Confidence not catastrophically low (catches garbled responses)
    confidence = (
        result.get("overall_confidence") or
        result.get("weight_summary", {}).get("confidence") or
        1.0
    )
    if float(confidence) < 0.15:
        return False

    return True


async def _extract_via_openai(pdf_bytes: bytes, context_text: str = "") -> dict:
    """Convert PDF pages to images and send to OpenAI vision."""
    import fitz  # PyMuPDF
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = _build_prompt(context_text)

    # Render each PDF page to a PNG image
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    user_content: list = [{"type": "text", "text": prompt}]
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}
        })
    doc.close()

    response = await client.chat.completions.create(
        model=settings.openai_model_vision,
        messages=[
            {"role": "system", "content": "You are a structural steel takeoff engineer."},
            {"role": "user", "content": user_content},
        ],
        max_tokens=4000,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    return _parse_extraction_response(raw)


async def _extract_via_claude(pdf_bytes: bytes, context_text: str = "") -> dict:
    """
    Claude drawing extraction — always uses image mode for accurate spatial extraction.
    """
    print("[AI] Drawing costing: Claude image mode (all pages)")
    return await _extract_via_claude_images(pdf_bytes, context_text)


async def _extract_via_claude_native_pdf(pdf_bytes: bytes, context_text: str = "") -> dict:
    """Send full PDF natively to Claude vision API."""
    if len(pdf_bytes) > CLAUDE_MAX_PDF_BYTES:
        logger.warning(
            "PDF (%d MB) exceeds Claude's 24 MB native-PDF limit; "
            "automatically falling back to image mode.",
            len(pdf_bytes) // (1024 * 1024),
        )
        return await _extract_via_claude_images(pdf_bytes, context_text)

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    prompt = _build_prompt(context_text)

    message = await client.messages.create(
        model=settings.claude_model_drawing,
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    raw = message.content[0].text if message.content else ""
    return _parse_extraction_response(raw)


async def _extract_via_claude_images(pdf_bytes: bytes, context_text: str = "") -> dict:
    """Render all PDF pages to PNG and send as Claude image blocks."""
    import anthropic
    import fitz  # PyMuPDF

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(context_text)
    dpi = int(getattr(settings, "claude_drawing_image_dpi", 150) or 150)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        content_blocks: list = [{"type": "text", "text": prompt}]
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img_b64 = base64.standard_b64encode(pix.tobytes("png")).decode("utf-8")
            content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_b64,
                    },
                }
            )
    finally:
        doc.close()

    message = await client.messages.create(
        model=settings.claude_model_drawing,
        max_tokens=4000,
        messages=[{"role": "user", "content": content_blocks}],
    )
    raw = message.content[0].text if message.content else ""
    return _parse_extraction_response(raw)


async def extract_from_pdf(pdf_bytes: bytes, context_text: str = "") -> dict:
    """
    Route PDF extraction to the configured AI provider (with automatic fallback).
    context_text is the raw email body + subject injected into the prompt so the
    AI can correctly populate project.client, project.title, etc.
    """
    provider = settings.ai_provider.lower()

    if provider == "openai":
        try:
            print("[AI] Drawing costing: using PRIMARY model OpenAI", settings.openai_model_vision)
            return await _extract_via_openai(pdf_bytes, context_text)
        except Exception as e:
            print(f"[AI] OpenAI failed for drawing extraction ({type(e).__name__}: {e}). Falling back to Claude...")
            logger.warning(f"OpenAI drawing extraction failed: {e}. Retrying with Claude.")
            print("[AI] Drawing costing: using FALLBACK model Claude", settings.claude_model_drawing)
            return await _extract_via_claude(pdf_bytes, context_text)

    if provider == "claude":
        print("[AI] Drawing costing: using Claude", settings.claude_model_drawing)
        return await _extract_via_claude(pdf_bytes, context_text)

    # groq does not support native PDF vision — fall back to Claude
    print("[AI] Drawing costing: Groq unsupported for PDFs, using Claude", settings.claude_model_drawing)
    return await _extract_via_claude(pdf_bytes, context_text)


# ---------------------------------------------------------------------------
# Multi-file extraction (PDFs + images + text files)
# ---------------------------------------------------------------------------
_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
_IMAGE_EXTENSIONS    = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_TEXT_EXTENSIONS     = {".txt", ".csv", ".md", ".text"}


def _classify_file(filename: str, content_type: str):
    """Return 'pdf', 'image', or 'text' for a given file."""
    fname = (filename or "").lower()
    ct    = (content_type or "").lower()
    if ct == "application/pdf" or fname.endswith(".pdf"):
        return "pdf"
    if ct in _IMAGE_CONTENT_TYPES or any(fname.endswith(ext) for ext in _IMAGE_EXTENSIONS):
        return "image"
    return "text"


def _safe_image_media_type(content_type: str, filename: str) -> str:
    """Return a valid Claude/OpenAI image media type string."""
    ct = (content_type or "").lower()
    if ct in _IMAGE_CONTENT_TYPES:
        return ct.replace("image/jpg", "image/jpeg")
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")


async def _extract_multi_via_claude(
    pdf_files: list, image_files: list, context_text: str = ""
) -> dict:
    """Send multiple PDFs + images to Claude in a single message — always image mode."""
    import anthropic
    import fitz  # PyMuPDF

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = _build_prompt(context_text)

    content_blocks: list = []

    # Always render PDFs as images (never native PDF document blocks)
    for pf in pdf_files:
        pdf_bytes = pf["bytes"]
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            dpi = int(getattr(settings, "claude_drawing_image_dpi", 300) or 300)
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img_b64 = base64.standard_b64encode(pix.tobytes("png")).decode("utf-8")
                content_blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": img_b64},
                })
        finally:
            doc.close()

    for img_f in image_files:
        media_type = _safe_image_media_type(img_f["content_type"], img_f["filename"])
        img_b64    = base64.standard_b64encode(img_f["bytes"]).decode("utf-8")
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": img_b64},
        })

    content_blocks.append({"type": "text", "text": prompt})

    message = await client.messages.create(
        model=settings.claude_model_drawing,
        max_tokens=4000,
        messages=[{"role": "user", "content": content_blocks}],
    )
    raw = message.content[0].text if message.content else ""
    return _parse_extraction_response(raw)


async def _extract_multi_via_openai(
    pdf_files: list, image_files: list, context_text: str = ""
) -> dict:
    """Render multiple PDFs + images and send to OpenAI vision in one call."""
    import fitz  # PyMuPDF
    from openai import AsyncOpenAI

    client  = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt  = _build_prompt(context_text)
    content: list = [{"type": "text", "text": prompt}]

    for pf in pdf_files:
        doc = fitz.open(stream=pf["bytes"], filetype="pdf")
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                b64 = base64.standard_b64encode(pix.tobytes("png")).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })
        finally:
            doc.close()

    for img_f in image_files:
        media_type = _safe_image_media_type(img_f["content_type"], img_f["filename"])
        b64 = base64.standard_b64encode(img_f["bytes"]).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{b64}"},
        })

    from openai import AsyncOpenAI
    response = await client.chat.completions.create(
        model=settings.openai_model_vision,
        messages=[
            {"role": "system", "content": "You are a structural steel takeoff engineer."},
            {"role": "user",   "content": content},
        ],
        max_tokens=4000,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    return _parse_extraction_response(raw)


async def extract_from_files(files_data: list) -> dict:
    """
    Multi-file extraction entry point.
    files_data: list of {"bytes": bytes, "filename": str, "content_type": str}

    Handles PDFs, images (PNG/JPG/GIF/WEBP), and plain-text files.
    All files are combined into a single AI call.
    Falls back to extract_from_pdf when only one PDF is supplied.
    """
    pdf_files:   list = []
    image_files: list = []
    text_chunks: list = []

    for f in files_data:
        kind = _classify_file(f.get("filename", ""), f.get("content_type", ""))
        if kind == "pdf":
            pdf_files.append(f)
        elif kind == "image":
            image_files.append(f)
        else:
            try:
                text_chunks.append(f["bytes"].decode("utf-8", errors="ignore"))
            except Exception:
                pass

    context_text = "\n\n".join(text_chunks)

    # Fast-path: single PDF with no extras → use existing well-tested pipeline
    if len(pdf_files) == 1 and not image_files:
        return await extract_from_pdf(pdf_files[0]["bytes"], context_text)

    if not pdf_files and not image_files:
        raise ValueError("No visual content (PDF or image) found in uploaded files.")

    provider = settings.ai_provider.lower()
    if provider == "openai":
        try:
            print("[AI] Drawing costing (multi-file): OpenAI", settings.openai_model_vision)
            return await _extract_multi_via_openai(pdf_files, image_files, context_text)
        except Exception as exc:
            print(f"[AI] OpenAI multi-file failed ({exc}). Falling back to Claude.")
            logger.warning("OpenAI multi-file extraction failed: %s", exc)
            return await _extract_multi_via_claude(pdf_files, image_files, context_text)

    print("[AI] Drawing costing (multi-file): Claude", settings.claude_model_drawing)
    return await _extract_multi_via_claude(pdf_files, image_files, context_text)


def _parse_extraction_response(raw: str) -> dict:
    """Defensively parse Claude's response — strip markdown fences, find first {…}."""
    if not raw or not raw.strip():
        raise ValueError("Empty response from Claude")

    text = raw
    # Strip markdown fences
    m = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m = re.search(r"```\s*\n(.*?)\n```", text, re.DOTALL)
        if m:
            text = m.group(1)

    # Extract first {...} block
    if not text.strip().startswith("{"):
        m = re.search(r"(\{.*\})", text, re.DOTALL)
        if m:
            text = m.group(1)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try json_repair if available
        try:
            from json_repair import repair_json
            parsed = json.loads(repair_json(text))
        except Exception:
            raise ValueError(f"Could not parse JSON from Claude response: {raw[:500]}")

    # Normalize new schema (IMAGE_EXTRACTION_PROMPT) to old schema field names
    # for downstream compatibility with compute_costing() and related functions
    if "structural_elements" in parsed and "members" not in parsed:
        parsed["members"] = parsed.pop("structural_elements", [])
    if "bolts_and_plates" in parsed and "plates" not in parsed:
        parsed["plates"] = parsed.pop("bolts_and_plates", [])
    if "drawing_metadata" in parsed and "project" not in parsed:
        parsed["project"] = parsed.pop("drawing_metadata", {})

    # Capture completeness self-check from the LLM
    completeness = parsed.get("completeness_check", {})
    if not completeness.get("tags_match", True):
        parsed["_completeness_warning"] = True
        parsed["_missing_tags_note"] = str(
            completeness.get("missing_tags", "LLM reported incomplete extraction")
        )

    return parsed


# ---------------------------------------------------------------------------
# Step 2: Post-extraction reconciliation
# ---------------------------------------------------------------------------

def reconcile_extraction(
    extracted_members: list,
    extracted_bom_items: list,
) -> dict:
    """
    Validates extracted drawing data before it enters the quantity engine.
    Returns a reconciliation report that is stored with the job and shown
    to the engineer in the review UI.
    """
    from app.services import steel_section_reference as section_ref

    issues = []
    resolved_members = []
    unknown_sections = []
    fuzzy_matches = {}
    INVALID_TOKENS = {"", "unknown", "n/a", "na", "tbd", "?", "-", "none"}

    # ── Section validation ──────────────────────────────────────────────
    for member in extracted_members:
        m = dict(member)
        raw_section = str(m.get("section", "")).strip()
        normalized = raw_section.upper().replace("  ", " ").strip()

        if normalized.lower() in INVALID_TOKENS:
            issues.append({
                "type": "MISSING_SECTION",
                "severity": "WARNING",
                "message": "Member has no section designation",
                "field": "section",
            })
            unknown_sections.append(raw_section)
        else:
            # Try exact lookup, then normalized lookup
            ref = (
                _lookup_section(section_ref, raw_section) or
                _lookup_section(section_ref, normalized)
            )
            if ref:
                m["unit_weight_kg_m"] = ref.get("unit_weight_kg_m") or ref.get("kg_per_m")
                m["section"] = normalized  # standardize casing
            else:
                unknown_sections.append(raw_section)
                suggestion = _fuzzy_section(section_ref, normalized)
                entry = {
                    "type": "UNRECOGNIZED_SECTION",
                    "severity": "WARNING",
                    "message": f"Section '{raw_section}' not in reference table",
                    "field": "section",
                }
                if suggestion:
                    entry["suggestion"] = suggestion
                    fuzzy_matches[raw_section] = suggestion
                issues.append(entry)

        resolved_members.append(m)

    # ── Calculate weight from member dimensions ─────────────────────────
    calc_parts = []
    for m in resolved_members:
        uw = m.get("unit_weight_kg_m")
        length = (
            m.get("total_length_m") or
            m.get("length_m") or
            (float(m.get("length_mm", 0)) / 1000)
        )
        qty = float(m.get("pieces") or m.get("qty") or 1)
        if uw and length:
            calc_parts.append(float(uw) * float(length) * qty)

    calculated_weight_kg = sum(calc_parts) if calc_parts else None

    # ── Get total weight from BOM rows ──────────────────────────────────
    bom_weight_kg = None
    bom_confidence = 0.0
    if extracted_bom_items:
        weights, confs = [], []
        for item in extracted_bom_items:
            w = item.get("total_weight_kg") or item.get("weight_kg")
            if w and float(w) > 0:
                weights.append(float(w))
            confs.append(float(item.get("confidence", 0.8)))
        if weights:
            bom_weight_kg = sum(weights)
            bom_confidence = sum(confs) / len(confs)

    # ── Reconcile BOM vs calculated ─────────────────────────────────────
    divergence_pct = None
    if bom_weight_kg and calculated_weight_kg:
        denom = max(bom_weight_kg, calculated_weight_kg)
        if denom > 0:
            divergence_pct = abs(bom_weight_kg - calculated_weight_kg) / denom * 100

    # Choose the trusted weight source
    if bom_weight_kg and bom_confidence >= 0.75:
        if divergence_pct is None or divergence_pct <= 5.0:
            weight_source = "BOM"
        elif divergence_pct <= 15.0:
            weight_source = "CALCULATED"
            issues.append({
                "type": "WEIGHT_DIVERGENCE",
                "severity": "WARNING",
                "message": (
                    f"BOM total {bom_weight_kg:.1f} kg vs calculated "
                    f"{calculated_weight_kg:.1f} kg — {divergence_pct:.1f}% apart. "
                    f"Using calculated weight. Verify BOM table extraction."
                ),
                "field": "total_weight_kg",
            })
        else:
            weight_source = "MIXED"
            issues.append({
                "type": "WEIGHT_DIVERGENCE_HIGH",
                "severity": "ERROR",
                "message": (
                    f"BOM total {bom_weight_kg:.1f} kg vs calculated "
                    f"{calculated_weight_kg:.1f} kg — {divergence_pct:.1f}% apart. "
                    f"Manual review required before proceeding."
                ),
                "field": "total_weight_kg",
            })
    elif calculated_weight_kg:
        weight_source = "CALCULATED"
    elif bom_weight_kg:
        weight_source = "BOM"
    else:
        weight_source = "UNAVAILABLE"
        issues.append({
            "type": "NO_WEIGHT",
            "severity": "ERROR",
            "message": "Could not determine steel weight from BOM or dimensions.",
            "field": "total_weight_kg",
        })

    # ── Overall status ──────────────────────────────────────────────────
    if any(i["severity"] == "ERROR" for i in issues):
        status = "FAIL"
    elif any(i["severity"] == "WARNING" for i in issues):
        status = "WARNING"
    else:
        status = "PASS"

    return {
        "status": status,
        "issues": issues,
        "resolved_members": resolved_members,
        "bom_weight_kg": bom_weight_kg,
        "calculated_weight_kg": calculated_weight_kg,
        "weight_divergence_pct": divergence_pct,
        "weight_source": weight_source,
        "unknown_sections": unknown_sections,
        "fuzzy_matches": fuzzy_matches,
    }


def _lookup_section(section_ref, designation: str):
    """Try every plausible method name the section_ref module might expose."""
    for method in ("lookup", "get", "get_section", "find", "find_section",
                   "get_section_unit_weight"):
        fn = getattr(section_ref, method, None)
        if fn:
            try:
                result = fn(designation)
                if result is not None:
                    if isinstance(result, dict):
                        return result
                    # Function returned a scalar (unit weight)
                    return {"unit_weight_kg_m": result, "kg_per_m": result}
            except Exception:
                pass
    # Last resort: check module-level SECTION_WEIGHTS dict
    sw = getattr(section_ref, "SECTION_WEIGHTS", None)
    if isinstance(sw, dict):
        val = sw.get(designation) or sw.get(designation.upper())
        if val is not None:
            return {"unit_weight_kg_m": val, "kg_per_m": val}
    return None


def _fuzzy_section(section_ref, designation: str) -> str | None:
    """Return the closest matching section designation from the reference."""
    for method in ("find_by_prefix", "suggest", "closest", "fuzzy_match"):
        fn = getattr(section_ref, method, None)
        if fn:
            try:
                result = fn(designation[:6])
                if result:
                    return result[0] if isinstance(result, list) else result
            except Exception:
                pass
    # Fallback: prefix scan on SECTION_WEIGHTS dict
    sw = getattr(section_ref, "SECTION_WEIGHTS", None)
    if isinstance(sw, dict):
        prefix = designation[:6].upper()
        for key in sw:
            if key.upper().startswith(prefix):
                return key
    return None


# ---------------------------------------------------------------------------
# Step 3–5: Compute everything
# ---------------------------------------------------------------------------
def compute_costing(extraction: dict, markup_pct: float = RATIOS["defaultMarkupPct"]) -> dict:
    """
    Given extraction dict (members, plates), compute steel weight, derived
    quantities, all cost line items, overhead, and selling price.
    Returns a flat dict consumed by both the review API and the Excel generator.
    """
    members: List[Dict[str, Any]] = extraction.get("members", [])
    plates:  List[Dict[str, Any]] = extraction.get("plates", [])

    # --- Steel weight ---
    member_rows = []
    total_steel_kg = 0.0
    for m in members:
        section = m.get("section", "")
        length_m = float(m.get("total_length_m") or 0)
        pieces = int(m.get("pieces") or 0)
        role = m.get("role", "")
        kg_per_m, is_estimated = get_kg_per_m(section)
        weight_kg = kg_per_m * length_m
        total_steel_kg += weight_kg
        member_rows.append({
            "section":      section,
            "role":         role,
            "length_m":     round(length_m, 3),
            "kg_per_m":     kg_per_m,
            "pieces":       pieces,
            "weight_kg":    round(weight_kg, 2),
            "is_estimated": is_estimated,
        })

    plate_weight_kg = 0.0
    for p in plates:
        thk = float(p.get("thickness_mm") or 0)
        area = float(p.get("total_area_m2") or 0)
        plate_weight_kg += thk * area * PLATE_DENSITY

    total_steel_kg += plate_weight_kg

    # --- Derived quantities ---
    surface_area_sqm  = round(total_steel_kg * RATIOS["surfaceAreaPerKg"])
    bolts             = math.ceil(total_steel_kg / 1000 * RATIOS["boltsPer1000Kg"])
    paint_litres      = math.ceil(surface_area_sqm * RATIOS["paintLitresPerSqm"])
    mpi_visits        = max(1, math.ceil(total_steel_kg / 1000 * RATIOS["mpiVisitsPer1000Kg"]))
    welding_mh        = math.ceil(total_steel_kg * RATIOS["weldingMHPerKg"])
    fabrication_mh    = math.ceil(total_steel_kg * RATIOS["fabricationMHPerKg"])

    # --- Direct costs ---
    steel_mat_cost    = total_steel_kg * RATIOS["rateSteelPerKg"]
    bolt_cost         = bolts          * RATIOS["rateBoltPerNo"]
    paint_mat_cost    = paint_litres   * RATIOS["ratePaintPerLitre"]
    weld_cost         = welding_mh     * RATIOS["rateWeldingPerMH"]
    fab_cost          = fabrication_mh * RATIOS["rateFabricationPerMH"]
    blast_cost        = surface_area_sqm * RATIOS["rateBlastingPerSqm"]
    paint_app_cost    = surface_area_sqm * RATIOS["ratePaintingPerSqm"]
    mpi_cost          = mpi_visits     * RATIOS["rateMPIPerVisit"]
    qaqc_cost         = RATIOS["rateQAQC"]
    packing_cost      = RATIOS["ratePacking"]

    subtotal_no_consum = (
        steel_mat_cost + bolt_cost + paint_mat_cost +
        weld_cost + fab_cost + blast_cost + paint_app_cost +
        mpi_cost + qaqc_cost + packing_cost
    )

    # --- Overhead (S54) ---
    oh_rate   = 230000 / 30 / 30 / 8
    blast_mh  = (1 / 13.3) * surface_area_sqm * 3
    paint_mh  = (1 / 6.65) * surface_area_sqm * 3
    overhead  = oh_rate * (welding_mh + fabrication_mh + blast_mh + paint_mh)

    # --- Selling price (resolves circular reference) ---
    selling_price = (subtotal_no_consum + overhead) * (1 + markup_pct)
    consumables   = selling_price / 20
    grand_total   = subtotal_no_consum + consumables + overhead
    net_profit    = selling_price - grand_total
    profit_pct    = (net_profit / selling_price) if selling_price else 0.0

    return {
        # Takeoff
        "member_rows":       member_rows,
        "plates":            plates,
        "plate_weight_kg":   round(plate_weight_kg, 2),
        "total_steel_kg":    round(total_steel_kg, 2),
        # Derived quantities
        "surface_area_sqm":  int(surface_area_sqm),
        "bolts":             bolts,
        "paint_litres":      paint_litres,
        "mpi_visits":        mpi_visits,
        "welding_mh":        welding_mh,
        "fabrication_mh":    fabrication_mh,
        # Cost line items
        "steel_mat_cost":    round(steel_mat_cost, 2),
        "bolt_cost":         round(bolt_cost, 2),
        "paint_mat_cost":    round(paint_mat_cost, 2),
        "weld_cost":         round(weld_cost, 2),
        "fab_cost":          round(fab_cost, 2),
        "blast_cost":        round(blast_cost, 2),
        "paint_app_cost":    round(paint_app_cost, 2),
        "mpi_cost":          round(mpi_cost, 2),
        "qaqc_cost":         round(qaqc_cost, 2),
        "packing_cost":      round(packing_cost, 2),
        "subtotal_no_consum": round(subtotal_no_consum, 2),
        "overhead":          round(overhead, 2),
        # Totals
        "consumables":       round(consumables, 2),
        "grand_total":       round(grand_total, 2),
        "selling_price":     round(selling_price, 2),
        "net_profit":        round(net_profit, 2),
        "profit_pct":        round(profit_pct * 100, 2),
        "markup_pct":        round(markup_pct * 100, 2),
    }


# ---------------------------------------------------------------------------
# Step 5: Generate Excel workbook from template
# ---------------------------------------------------------------------------

def _resolve_template_path() -> Path:
    """Resolve the Job Costing Sheet template to an absolute path."""
    configured = Path(settings.drawing_costing_template_path)
    if configured.is_absolute() and configured.exists():
        return configured
    # Try multiple base directories in order:
    #   parents[2] = backend/   (production: /tmp/<hash>/)
    #   parents[3] = project root (local dev: CostEstimatorAgent/)
    #   /home/site/wwwroot      (Azure wwwroot fallback)
    candidates = [
        Path(__file__).resolve().parents[2] / configured,
        Path(__file__).resolve().parents[3] / configured,
        Path("/home/site/wwwroot") / configured,
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]  # will raise FileNotFoundError with a clear path


def generate_excel(costing: dict, project: dict, customer: dict) -> BytesIO:
    """
    Stamp computed values into the Sample Job Costing Sheet.xlsx template.
    All existing formatting, merged cells, borders, and pre-built formulas
    are preserved. Only the variable data cells listed below are written.

    Critical invariants (verified against the template):
      - All formulas (J33, I40, I41, K-column, S54, D56, D59, etc.) are preserved from template
      - Only data values are written (quantities, dates, names, remarks)
      - D58 is HARDCODED to selling_price (the only number override in the footer)
    """
    template_path = _resolve_template_path()
    if not template_path.exists():
        raise FileNotFoundError(
            f"Job Costing Sheet template not found at: {template_path}\n"
            "Set drawing_costing_template_path in your .env or config."
        )

    wb = openpyxl.load_workbook(str(template_path))
    ws = wb.active  # template has exactly one sheet

    # Rename sheet to "{jobNo}- Structure Frame"
    job_no = str(customer.get("jobNo") or "XXXX")
    ws.title = f"{job_no}- Structure Frame"[:31]  # Excel max 31 chars

    T      = costing["total_steel_kg"]
    SA     = costing["surface_area_sqm"]
    PL     = costing["paint_litres"]
    MPI    = costing["mpi_visits"]
    WMH    = costing["welding_mh"]
    FMH    = costing["fabrication_mh"]
    HR_KG  = costing.get("handrail_kg")   # LLM-extracted, may be None
    GR_KG  = costing.get("grating_kg")    # LLM-extracted, may be None
    # Bolts qty feeds selling_price via _compute_costing but has no dedicated row in template

    # ----------------------------------------------------------------
    # Header block — only the fields that vary per job
    # ----------------------------------------------------------------
    ws["A3"] = f"REF NO: CNJ/{customer.get('refNo', '')}/01/2025"
    ws["C4"] = customer.get("customerName", "")
    ws["G4"] = date.today()
    ws["O4"] = customer.get("enquiryNo", "")
    ws["G5"] = customer.get("attention", "")
    ws["O5"] = customer.get("jobNo", "")
    ws["G6"] = customer.get("contact", "")

    # ----------------------------------------------------------------
    # Qty / Manhour cells — mapped to actual template rows (screenshot verified)
    # ----------------------------------------------------------------

    # ── Section 5: Material Cost ──────────────────────────────────────
    # Row 23 — 5.1 Structural Steel Material
    ws["G23"] = T

    # Row 24 — 5.2 Handrails (LLM-extracted; blank row left if not found)
    if HR_KG:
        ws["G24"] = HR_KG

    # Row 25 — 5.3 Grating (LLM-extracted; blank row left if not found)
    if GR_KG:
        ws["G25"] = GR_KG

    # Row 26 — 5.4 Paint Material
    ws["G26"] = PL

    # ── Section 7: Labour & Fabrication Cost ─────────────────────────
    # Row 30 — 7.1 Structural Welding (steel + handrails)
    welding_qty = T + (HR_KG or 0)
    ws["G30"] = welding_qty
    ws["I30"] = "=INT((G30/1000)*40)"
    ws["M30"] = "2 Welder"

    # Row 31 — 7.2 Structural Fabrication (steel + handrails)
    ws["G31"] = welding_qty
    ws["I31"] = "=INT((G31/1000)*80)"
    ws["M31"] = "2 Fabricator 2 Helper"

    # Row 33 — 7.4 Machining (remarks only)
    ws["M33"] = "1  Machinist"

    # ── Section 8: Consumables ────────────────────────────────────────
    # Row 34 — Consumables
    ws["G34"] = 1

    # ── Section 10: Testing & Quality Control ────────────────────────
    # Row 38 — 10.1 100% MPI/DPT
    ws["G38"] = MPI

    # ── Section 11: Surface Preparation & Coating ────────────────────
    # Row 40 — 11.1 Galvanizing Work (handrail kg — galvanizing is applied to handrails)
    if HR_KG:
        ws["G40"] = HR_KG
        ws["M40"] = "1 Galvanizer"

    # Row 41 — 11.2 Blasting
    ws["G41"] = SA
    ws["M41"] = "1 Blaster 1 Helper"

    # Row 42 — 11.3 Painting
    ws["G42"] = SA
    ws["M42"] = "1 Painter 1 Helper"

    # ── Section 13 & 14: QA/QC and Packing ───────────────────────────
    # Row 44 — 13 QA/QC Documentation & Certification
    ws["G44"] = 1

    # Row 45 — 14 Packing and loading
    ws["G45"] = 1

    # ----------------------------------------------------------------
    # Footer
    # ----------------------------------------------------------------

    # Row 58 — CRITICAL: D58 hardcoded selling price (NUMBER, not formula)
    ws["D58"] = costing["selling_price"]

    # Row 59 — Net Profit (formula preserved from template if exists)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
