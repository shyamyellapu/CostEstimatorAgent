"""
RFQ Document Extraction Engine

Multi-stage extraction pipeline:
  Stage 1 — Deterministic parsers (structured Excel BOMs, known layouts)
  Stage 2 — Heuristic parsers (PDF table detection, regex patterns)
  Stage 3 — AI extraction (LLM reads text/image, returns structured JSON)

Output schema per attachment:
  {
    "line_items": [...],
    "metadata":   { client, project, reference, deadline, ... },
    "raw_text":   "..."
  }
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit normalisation map
# ---------------------------------------------------------------------------
UNIT_NORMALISE: dict[str, str] = {
    "nos": "nos", "no": "nos", "nr": "nos", "pcs": "nos", "pc": "nos",
    "pieces": "nos", "units": "nos", "unit": "nos", "each": "nos",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "t": "t", "ton": "t", "tons": "t", "mt": "t", "tonne": "t",
    "m": "m", "metre": "m", "meter": "m", "metres": "m", "meters": "m",
    "mm": "mm", "millimetre": "mm", "millimeter": "mm",
    "m2": "m2", "sqm": "m2", "sq.m": "m2",
    "m3": "m3", "cbm": "m3",
    "l": "l", "ltr": "l", "litre": "l",
    "set": "set", "sets": "set",
    "lot": "lot", "lots": "lot", "ls": "lot",
}

MATERIAL_NORMALISE: dict[str, str] = {
    "cs": "Carbon Steel",
    "ms": "Mild Steel",
    "ss": "Stainless Steel",
    "ss304": "Stainless Steel 304",
    "ss316": "Stainless Steel 316",
    "ss316l": "Stainless Steel 316L",
    "alloy steel": "Alloy Steel",
    "p91": "Alloy Steel P91",
    "p22": "Alloy Steel P22",
    "p11": "Alloy Steel P11",
    "inconel": "Inconel",
    "hastelloy": "Hastelloy",
    "duplex": "Duplex Stainless Steel",
    "sdss": "Super Duplex Stainless Steel",
    "gi": "Galvanized Steel",
    "hdg": "Hot-Dip Galvanized Steel",
}


def normalise_unit(raw: str) -> str:
    if not raw:
        return ""
    return UNIT_NORMALISE.get(raw.strip().lower(), raw.strip().lower())


def normalise_material(raw: str) -> str:
    if not raw:
        return ""
    lower = raw.strip().lower()
    return MATERIAL_NORMALISE.get(lower, raw.strip())


# ---------------------------------------------------------------------------
# Excel BOM parser (deterministic)
# ---------------------------------------------------------------------------

def _coerce_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


BOM_COLUMN_SYNONYMS: dict[str, list[str]] = {
    "line_number":    ["item", "sl no", "s.no", "sr", "line", "item no", "item#", "#"],
    "tag_number":     ["tag", "tag no", "tag number", "equipment tag", "tag-no"],
    "description":    ["description", "item description", "desc", "scope", "specification"],
    "material":       ["material", "mat", "moc", "material of construction", "grade"],
    "quantity":       ["qty", "quantity", "nos", "count", "req", "required"],
    "unit":           ["unit", "uom", "units"],
    "weight_each_kg": ["unit weight", "weight ea", "weight each", "kg each", "wt each"],
    "total_weight_kg":["total weight", "total wt", "gross weight"],
    "drawing_reference": ["dwg no", "drawing no", "drg no", "drawing ref"],
    "remarks":        ["remarks", "notes", "comment", "note"],
}


def _map_columns(header_row: List[Any]) -> dict[str, int]:
    """Map BOM_COLUMN_SYNONYMS keys to column indices in an Excel header row."""
    col_map: dict[str, int] = {}
    normalised_headers = [str(h or "").strip().lower() for h in header_row]
    for field, synonyms in BOM_COLUMN_SYNONYMS.items():
        for idx, hdr in enumerate(normalised_headers):
            if any(syn in hdr or hdr in syn for syn in synonyms):
                col_map[field] = idx
                break
    return col_map


def parse_excel_bom(filepath: str) -> Dict[str, Any]:
    """Extract line items from an Excel BOM/BOQ file."""
    try:
        import openpyxl
    except ImportError:
        return {"line_items": [], "error": "openpyxl not installed"}

    line_items: List[dict] = []
    metadata: dict = {}

    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    except Exception as exc:
        return {"line_items": [], "error": str(exc)}

    for ws in wb.worksheets:
        all_rows = list(ws.iter_rows(values_only=True))
        if not all_rows:
            continue

        # Find header row (first row where >3 cells are non-empty)
        header_idx = 0
        for i, row in enumerate(all_rows[:20]):
            filled = sum(1 for c in row if c is not None)
            if filled >= 3:
                header_idx = i
                break

        col_map = _map_columns(all_rows[header_idx])
        if not col_map:
            continue

        for row in all_rows[header_idx + 1:]:
            if all(c is None for c in row):
                continue
            item: dict[str, Any] = {}
            for field, idx in col_map.items():
                if idx < len(row):
                    val = row[idx]
                    item[field] = str(val).strip() if val is not None else None

            # Skip empty rows
            if not item.get("description") and not item.get("material"):
                continue

            qty = _coerce_float(item.get("quantity"))
            line_items.append({
                "line_number":      item.get("line_number"),
                "tag_number":       item.get("tag_number"),
                "description":      item.get("description"),
                "material":         normalise_material(item.get("material") or ""),
                "quantity":         qty,
                "unit":             normalise_unit(item.get("unit") or ""),
                "weight_each_kg":   _coerce_float(item.get("weight_each_kg")),
                "total_weight_kg":  _coerce_float(item.get("total_weight_kg")),
                "drawing_reference": item.get("drawing_reference"),
                "remarks":          item.get("remarks"),
                "confidence_score": 0.88,
                "raw_extracted":    item,
            })

    wb.close()
    return {"line_items": line_items, "metadata": metadata}


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def _extract_pdf_full_text(filepath: str) -> Tuple[str, bool]:
    """
    Returns (text, is_scanned).
    is_scanned=True means the PDF has very little selectable text (needs OCR).
    """
    text = ""
    try:
        import fitz
        doc = fitz.open(filepath)
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text("text"))
        text = "\n".join(pages_text)
        doc.close()
    except Exception:
        pass

    if not text.strip():
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        except Exception:
            pass

    char_density = len(text.strip()) / max(1, text.count("\n") + 1)
    is_scanned = len(text.strip()) < 100 or char_density < 5
    return text, is_scanned


def _ocr_pdf(filepath: str) -> str:
    """OCR a scanned PDF using pytesseract (if available)."""
    try:
        import fitz
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore
        import io

        doc = fitz.open(filepath)
        full_text = []
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            full_text.append(pytesseract.image_to_string(img))
        doc.close()
        return "\n".join(full_text)
    except ImportError:
        logger.info("pytesseract/Pillow not available — OCR skipped")
        return ""
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# AI-based extraction
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are an expert engineering document data extractor.

Extract ALL line items from the following RFQ / BOM document and return structured JSON.

For each line item extract:
- line_number (string, e.g. "1", "A", "1.1")
- tag_number (equipment tag, e.g. "TK-101")
- description (full item description)
- material (material of construction, e.g. "Carbon Steel A106 Gr.B")
- material_grade (grade only, e.g. "A106 Gr.B")
- quantity (numeric)
- unit (e.g. "nos", "kg", "m", "set")
- weight_each_kg (if mentioned)
- total_weight_kg (if mentioned)
- dimensions (object with keys: length_mm, width_mm, height_mm, diameter_mm, thickness_mm, nps_inch — only what's present)
- pressure_class (e.g. "ANSI 150", "PN16", "Class 600")
- surface_treatment (e.g. "Hot-dip galvanised", "Shot blast SA2.5 + epoxy")
- drawing_reference (drawing number)
- remarks

Also extract document metadata:
- client_name
- project_name
- project_reference
- rfq_number
- enquiry_date (ISO format)
- deadline (ISO format)
- scope_summary (1-2 sentence summary of what is being requested)

Return ONLY valid JSON with this structure:
{
  "line_items": [...],
  "metadata": {
    "client_name": null,
    "project_name": null,
    "project_reference": null,
    "rfq_number": null,
    "enquiry_date": null,
    "deadline": null,
    "scope_summary": null
  }
}

If a field is not present in the document, use null.
Normalise all units to standard forms (nos, kg, m, mm, m2, m3, set, lot).

Document text:
---
{text}
---"""


async def _ai_extract(text: str, filename: str) -> Dict[str, Any]:
    """Use AI to extract structured line items from document text."""
    from app.ai.ai_provider import get_provider
    import json_repair

    provider = get_provider()
    truncated_text = text[:12000]  # keep within token budget

    prompt = EXTRACTION_PROMPT.replace("{text}", truncated_text)

    try:
        response = await provider.complete(prompt, max_tokens=4000, temperature=0.1)
        raw = json_repair.repair_json(response)
        data = json.loads(raw)
        line_items = data.get("line_items", [])
        metadata = data.get("metadata", {})

        # Normalise fields
        for item in line_items:
            if item.get("unit"):
                item["unit"] = normalise_unit(item["unit"])
            if item.get("material"):
                item["material"] = normalise_material(item["material"])
            item.setdefault("confidence_score", 0.75)
            item["raw_extracted"] = dict(item)

        return {"line_items": line_items, "metadata": metadata}
    except Exception as exc:
        logger.error("AI extraction failed for %s: %s", filename, exc)
        return {"line_items": [], "metadata": {}, "error": str(exc)}


# ---------------------------------------------------------------------------
# Word / DOCX extraction
# ---------------------------------------------------------------------------

def _extract_docx_text(filepath: str) -> str:
    try:
        from docx import Document
        doc = Document(filepath)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                if row_text:
                    parts.append(row_text)
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Email body extraction
# ---------------------------------------------------------------------------

EMAIL_METADATA_PATTERNS = {
    "rfq_number":        [r"(?:rfq|enquiry|inquiry|ref|reference)[# :.-]*([A-Z0-9]*\d[A-Z0-9/-]*)", r"(?:our ref)[# :.-]*([A-Z0-9]*\d[A-Z0-9/-]*)"],
    # Pattern requires at least one digit to avoid capturing plain words like 'PR', 'for'
    "project_reference": [r"(?:project ref|project no|job no|po no)[# :.-]*([A-Z0-9/-]+)"],
    "deadline":          [r"(?:due|deadline|required by|respond by|closing date)[: .-]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"],
}


def extract_email_metadata(body: str) -> dict:
    metadata: dict = {}
    for field, patterns in EMAIL_METADATA_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                metadata[field] = m.group(1).strip()
                break
    return metadata


# ---------------------------------------------------------------------------
# Master extraction dispatcher
# ---------------------------------------------------------------------------

async def extract_from_attachment(
    filepath: str,
    filename: str,
    file_category: str,
    document_type: str,
) -> Dict[str, Any]:
    """
    Dispatch to the right extractor based on file_category / document_type.
    Returns { line_items, metadata, raw_text, source_stage }.
    """
    raw_text = ""
    result: Dict[str, Any] = {"line_items": [], "metadata": {}, "raw_text": "", "source_stage": "rules"}

    if file_category == "excel":
        parsed = parse_excel_bom(filepath)
        result["line_items"] = parsed.get("line_items", [])
        result["metadata"] = parsed.get("metadata", {})
        result["source_stage"] = "deterministic"
        return result

    elif file_category == "pdf":
        raw_text, is_scanned = _extract_pdf_full_text(filepath)
        if is_scanned:
            raw_text = _ocr_pdf(filepath)
            result["source_stage"] = "ocr+ai"
        else:
            result["source_stage"] = "ai"
        result["raw_text"] = raw_text

    elif file_category == "word":
        raw_text = _extract_docx_text(filepath)
        result["source_stage"] = "ai"
        result["raw_text"] = raw_text

    else:
        return result

    if raw_text.strip():
        ai_result = await _ai_extract(raw_text, filename)
        result["line_items"] = ai_result.get("line_items", [])
        result["metadata"] = ai_result.get("metadata", {})

    return result


async def extract_from_email_body(subject: str, body: str) -> Dict[str, Any]:
    """Extract RFQ metadata from email body text."""
    metadata = extract_email_metadata(body)
    if subject:
        metadata.setdefault("scope_summary", subject)
    return {"metadata": metadata, "line_items": []}
