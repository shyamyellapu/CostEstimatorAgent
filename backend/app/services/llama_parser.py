"""
LlamaParse document parser — uses the official llama-cloud Python SDK.

Flow:
  1. client.files.create()          → upload file, get file_id
  2. client.parsing.parse()         → submit agentic job, poll, return result
  3. result.markdown_full           → clean markdown ready for LLM

Parsed markdown is saved to:
  <LOCAL_STORAGE_PATH>/llama_parsed/<job_id>/<filename>.md
"""
import io
import logging
from pathlib import Path

import aiofiles

from app.config import settings

logger = logging.getLogger(__name__)


async def parse_to_markdown(file_bytes: bytes, filename: str) -> str:
    """
    Parse a document via LlamaParse (agentic tier) and return clean markdown.

    Raises ValueError  — API key not configured
    Raises RuntimeError — parsing failed on LlamaCloud side
    """
    api_key = settings.llama_parse_api_key
    if not api_key:
        raise ValueError(
            "LLAMA_PARSE_API_KEY is not configured. "
            "Add it to your .env file to enable LlamaParse."
        )

    import asyncio
    # SDK calls are synchronous — run in thread pool to avoid blocking the event loop
    result_markdown = await asyncio.get_event_loop().run_in_executor(
        None, _parse_sync, file_bytes, filename, api_key
    )
    return result_markdown


def _parse_sync(file_bytes: bytes, filename: str, api_key: str) -> str:
    """Synchronous LlamaCloud SDK call (runs in a thread pool)."""
    from llama_cloud import LlamaCloud

    client = LlamaCloud(api_key=api_key)
    mime = _guess_mime(filename)

    logger.info("LlamaParse: uploading '%s' (%d bytes)", filename, len(file_bytes))

    # Upload file — SDK accepts (filename, bytes, mime_type) tuple
    file_obj = client.files.create(
        file=(filename, io.BytesIO(file_bytes), mime),
        purpose="parse",
    )
    logger.info("LlamaParse: file_id=%s for '%s'", file_obj.id, filename)

    # Submit parse job (agentic tier), poll until done, return result
    result = client.parsing.parse(
        file_id=file_obj.id,
        tier="agentic",
        version="latest",
        expand=["markdown_full", "text_full"],
    )

    markdown = result.markdown_full or result.text_full or ""
    logger.info(
        "LlamaParse: done — %d chars extracted from '%s'", len(markdown), filename
    )
    return markdown


async def save_parsed_markdown(markdown: str, filename: str, job_id: str) -> Path:
    """Save LlamaParse markdown to disk for inspection."""
    stem    = Path(filename).stem
    out_dir = Path(settings.local_storage_path) / "llama_parsed" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stem}.md"
    async with aiofiles.open(out_path, "w", encoding="utf-8") as f:
        await f.write(markdown)
    logger.info("LlamaParse result saved → %s", out_path)
    return out_path


def is_useful_markdown(markdown: str, min_chars: int = 200) -> bool:
    """Return False when the output is clearly binary garbage."""
    if not markdown or len(markdown.strip()) < min_chars:
        return False
    binary_markers = [
        "FlateDecode", "DCTDecode", "CCITTFaxDecode",
        "JBIG2Decode", "JPXDecode", "stream\n", "endstream",
        "obj\n", "endobj",
    ]
    return sum(1 for m in binary_markers if m in markdown) <= 2


def pdf_to_page_images(file_bytes: bytes, max_pages: int = 8, dpi: int = 120) -> list:
    """Render PDF pages to PNG bytes for vision API fallback."""
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=dpi)
            pages.append(pix.tobytes("png"))
    finally:
        doc.close()
    return pages


def _guess_mime(filename: str) -> str:
    ext = Path(filename).suffix.lstrip(".").lower()
    return {
        "pdf":  "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc":  "application/msword",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls":  "application/vnd.ms-excel",
        "png":  "image/png",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "gif":  "image/gif",
        "webp": "image/webp",
        "txt":  "text/plain",
    }.get(ext, "application/octet-stream")
