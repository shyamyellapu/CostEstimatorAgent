"""
Attachment Classification Engine

Two-stage pipeline:
  1. Deterministic rules (extension, MIME type, filename patterns) — fast, no AI
  2. AI-assisted classification for ambiguous documents — uses first-page text

Outputs:
  - file_category  : pdf | excel | word | dwg | zip | image | other
  - document_type  : bom | datasheet | pid | ga_drawing | isometric | specification
                     | rfq | cover_letter | drawing | other
  - revision_number: extracted from filename / content
  - document_number: extracted from filename / content
  - confidence     : 0.0 – 1.0
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category maps
# ---------------------------------------------------------------------------
EXTENSION_CATEGORY: dict[str, str] = {
    "pdf": "pdf",
    "xlsx": "excel", "xls": "excel", "csv": "excel",
    "doc": "word", "docx": "word",
    "dwg": "dwg", "dxf": "dwg",
    "zip": "zip", "rar": "zip", "7z": "zip", "tar": "zip", "gz": "zip",
    "jpg": "image", "jpeg": "image", "png": "image",
    "tif": "image", "tiff": "image", "bmp": "image",
}

MIME_CATEGORY: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.ms-excel": "excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    "text/csv": "excel",
    "application/msword": "word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
    "image/jpeg": "image", "image/png": "image",
    "image/tiff": "image", "image/bmp": "image",
    "application/zip": "zip",
    "application/x-rar-compressed": "zip",
}

# ---------------------------------------------------------------------------
# Document type patterns (checked against normalised filename)
# ---------------------------------------------------------------------------
DOC_TYPE_PATTERNS: list[Tuple[str, list[str]]] = [
    # (document_type, list_of_regex_patterns_on_lower_filename)
    ("bom",           [r"\bbom\b", r"bill[_ -]of[_ -]material", r"parts[_ -]list", r"\bboq\b"]),
    ("pid",           [r"\bpid\b", r"p&id", r"piping[_ -]instrument", r"process[_ -]flow"]),
    ("ga_drawing",    [r"\bga\b", r"general[_ -]arr", r"g\.a\.", r"layout"]),
    ("isometric",     [r"iso", r"isometric", r"isometri"]),
    ("datasheet",     [r"datasheet", r"data[_ -]sheet", r"\bds\b", r"spec[_ -]sheet"]),
    ("specification", [r"specif", r"\bspec\b", r"material[_ -]spec", r"project[_ -]spec", r"scope[_ -]of[_ -]work"]),
    ("rfq",           [r"\brfq\b", r"request[_ -]for[_ -]quot", r"enquiry", r"inquiry", r"rfp", r"tender"]),
    ("cover_letter",  [r"cover[_ -]letter", r"transmittal"]),
    ("drawing",       [r"drawing", r"drg", r"\bdwg\b", r"sketch"]),
]

# ---------------------------------------------------------------------------
# Revision extraction
# ---------------------------------------------------------------------------
REVISION_PATTERNS = [
    r"[_ \-]rev[\._\- ]?([a-z0-9]+)",
    r"[_ \-]r([0-9]{1,2})[_ \-\.]",
    r"revision[_ ]([a-z0-9]+)",
    r"[_ \-]v([0-9]+(?:\.[0-9]+)?)[_ \-\.]",
]

DOCUMENT_NUMBER_PATTERNS = [
    r"([A-Z]{2,}-[A-Z0-9]+-[A-Z0-9]+-\d{3,})",     # e.g. CJ-MEC-GA-001
    r"([A-Z]{2,}\d{3,}-[A-Z]{2,}\d{2,})",
    r"doc[\s_-]?no[\s_:.-]*([A-Z0-9/-]+)",
]


def _classify_by_rules(filename: str, mime_type: str) -> Tuple[str, str, float]:
    """Return (file_category, document_type, confidence) using deterministic rules only."""
    ext = Path(filename).suffix.lstrip(".").lower()
    file_category = (
        EXTENSION_CATEGORY.get(ext)
        or MIME_CATEGORY.get(mime_type, "")
        or "other"
    )

    fname_lower = filename.lower()

    doc_type = "other"
    doc_confidence = 0.6

    for dtype, patterns in DOC_TYPE_PATTERNS:
        for pat in patterns:
            if re.search(pat, fname_lower):
                doc_type = dtype
                doc_confidence = 0.85
                break
        if doc_type != "other":
            break

    # DWG files are almost always drawings
    if file_category == "dwg":
        if doc_type == "other":
            doc_type = "drawing"
        doc_confidence = max(doc_confidence, 0.90)

    return file_category, doc_type, doc_confidence


def extract_revision_number(filename: str, text_snippet: str = "") -> Optional[str]:
    """Extract revision identifier from filename or document text."""
    combined = (filename + " " + text_snippet[:500]).lower()
    for pat in REVISION_PATTERNS:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


def extract_document_number(filename: str, text_snippet: str = "") -> Optional[str]:
    """Extract document/drawing number from filename or document text."""
    combined = filename + " " + text_snippet[:1000]
    for pat in DOCUMENT_NUMBER_PATTERNS:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


# ---------------------------------------------------------------------------
# PDF text extraction (first page only, for AI classification)
# ---------------------------------------------------------------------------

def _extract_pdf_first_page_text(filepath: str) -> str:
    """Extract text from the first page of a PDF (fast, for classification)."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(filepath)
        if len(doc) == 0:
            return ""
        page = doc[0]
        return page.get_text("text")[:3000]
    except Exception:
        pass
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        if not reader.pages:
            return ""
        return reader.pages[0].extract_text() or ""
    except Exception:
        return ""


def _extract_excel_header_text(filepath: str) -> str:
    """Read first few rows/cells of an Excel to help classification."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        rows_text = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= 10:
                break
            rows_text.append(" ".join(str(c) for c in row if c is not None))
        wb.close()
        return "\n".join(rows_text)[:2000]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# AI-assisted classification
# ---------------------------------------------------------------------------

async def _ai_classify_document(
    filename: str, text_snippet: str, file_category: str
) -> Tuple[str, float]:
    """
    Use AI to classify document type when rule-based method is inconclusive.
    Returns (document_type, confidence).
    """
    from app.ai.ai_provider import get_provider
    from app.config import settings

    prompt = f"""You are an engineering document classifier.

File name: {filename}
File category: {file_category}

Document content preview (first 2000 chars):
---
{text_snippet[:2000]}
---

Classify this document into exactly ONE of these types:
- bom (Bill of Materials / Bill of Quantities / Parts List)
- datasheet (Equipment or material data sheet)
- pid (P&ID / Process Flow Diagram)
- ga_drawing (General Arrangement drawing / Layout)
- isometric (Piping isometric drawing)
- specification (Project spec / Scope of Work / Technical Specification)
- rfq (Request for Quotation / Enquiry / Tender)
- cover_letter (Cover letter / Transmittal)
- drawing (Other engineering drawing)
- other

Respond with ONLY a JSON object: {{"document_type": "<type>", "confidence": 0.0-1.0, "reason": "<brief reason>"}}"""

    try:
        provider = get_provider()
        response = await provider.complete(prompt, max_tokens=200, temperature=0.1)
        import json, json_repair
        data = json.loads(json_repair.repair_json(response))
        doc_type = data.get("document_type", "other")
        confidence = float(data.get("confidence", 0.7))
        valid_types = {t for t, _ in DOC_TYPE_PATTERNS} | {"other"}
        if doc_type not in valid_types:
            doc_type = "other"
        return doc_type, confidence
    except Exception as exc:
        logger.warning("AI classification failed: %s", exc)
        return "other", 0.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ClassificationResult:
    __slots__ = (
        "file_category", "document_type", "revision_number",
        "document_number", "confidence", "metadata",
    )

    def __init__(
        self,
        file_category: str,
        document_type: str,
        confidence: float,
        revision_number: Optional[str] = None,
        document_number: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        self.file_category = file_category
        self.document_type = document_type
        self.confidence = confidence
        self.revision_number = revision_number
        self.document_number = document_number
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "file_category": self.file_category,
            "document_type": self.document_type,
            "confidence": self.confidence,
            "revision_number": self.revision_number,
            "document_number": self.document_number,
            "metadata": self.metadata,
        }


async def classify_attachment(
    filepath: str,
    filename: str,
    mime_type: str = "",
    use_ai: bool = True,
) -> ClassificationResult:
    """
    Classify an attachment file.
    1. Deterministic rules first.
    2. Extract text snippet from first page / header.
    3. If confidence < 0.75 and use_ai=True, fall back to AI classification.
    """
    file_category, doc_type, confidence = _classify_by_rules(filename, mime_type)

    # Extract text snippet for revision / doc number extraction
    text_snippet = ""
    if file_category == "pdf":
        text_snippet = _extract_pdf_first_page_text(filepath)
    elif file_category == "excel":
        text_snippet = _extract_excel_header_text(filepath)

    # Try AI classification if needed
    if confidence < 0.75 and use_ai and text_snippet:
        ai_type, ai_conf = await _ai_classify_document(filename, text_snippet, file_category)
        if ai_conf > confidence:
            doc_type = ai_type
            confidence = ai_conf

    revision = extract_revision_number(filename, text_snippet)
    doc_number = extract_document_number(filename, text_snippet)

    return ClassificationResult(
        file_category=file_category,
        document_type=doc_type,
        confidence=confidence,
        revision_number=revision,
        document_number=doc_number,
        metadata={"text_snippet_len": len(text_snippet)},
    )
