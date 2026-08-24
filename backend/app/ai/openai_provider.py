"""
OpenAI AI Provider — uses openai SDK for structured outputs.
Set AI_PROVIDER=openai in .env to use as primary provider.
"""
import base64
import json
import logging
from typing import Any, Dict, List, Optional

from app.ai.ai_provider import (
    AIProvider, ExtractedDataResponse, DimensionItem, ExtractionFlag,
    MemberClassification, CoverLetterDraft, CoverLetterSection, ChatResponse
)
from app.ai.prompts import (
    DOCUMENT_EXTRACTION_PROMPT, IMAGE_EXTRACTION_PROMPT, DRAWING_READER_SYSTEM_PROMPT,
    BOQ_PARSE_PROMPT, MEMBER_CLASSIFY_PROMPT,
    QUOTATION_PARSE_PROMPT, COVER_LETTER_DRAFT_PROMPT,
    SYSTEM_PROMPT_ENGINEER
)
from app.config import settings

logger = logging.getLogger(__name__)

DOCUMENT_TEXT_CHAR_LIMIT = 300000   # ~75k tokens — safe for GPT-4o 128k context window


def _flatten_extraction(data: dict) -> dict:
    """Flatten structural_elements + bolts_and_plates into the dimensions list."""
    dimensions: list = []
    if "structural_elements" in data and isinstance(data["structural_elements"], list):
        for el in data["structural_elements"]:
            dimensions.append({
                "item_tag":                 el.get("support_tag") or el.get("tag") or el.get("item_tag"),
                "description":              el.get("item_description") or el.get("description"),
                "section_type":             el.get("section_type"),
                "section_designation":      el.get("section_designation"),
                "material_grade":           el.get("material_grade"),
                "length_mm":                el.get("length_mm") or el.get("l_mm"),
                "width_mm":                 el.get("width_mm") or el.get("w_mm"),
                "thickness_mm":             el.get("thickness_mm") or el.get("t_mm"),
                "od_mm":                    el.get("od_mm"),
                "quantity":                 el.get("quantity") or el.get("qty") or 1,
                "unit_weight_kg_per_m":     el.get("unit_weight_kg_per_m"),
                "total_weight_kg":          el.get("total_weight_kg") or el.get("weight_kg"),
                "weld_length_per_joint_mm": el.get("weld_length_per_joint_mm"),
                "weld_size_mm":             el.get("weld_size_mm"),
                "weld_type":                el.get("weld_type"),
                "surface_area_m2":          el.get("surface_area_m2"),
                "is_existing":              el.get("is_existing", False),
                "notes":                    el.get("notes"),
                "confidence":               0.9,
            })
    if "bolts_and_plates" in data and isinstance(data["bolts_and_plates"], list):
        for bp in data["bolts_and_plates"]:
            desc = bp.get("item_description") or bp.get("description") or ""
            dimensions.append({
                "item_tag":     "BOLT",
                "description":  desc,
                "section_type": "plate" if "plate" in desc.lower() else "bolt",
                "material_grade": bp.get("grade"),
                "length_mm":    bp.get("length_mm"),
                "quantity":     bp.get("quantity") or bp.get("qty") or 0,
                "notes":        bp.get("notes"),
                "confidence":   0.9,
            })
    data["dimensions"] = dimensions
    return data


class OpenAIProvider(AIProvider):

    def __init__(self):
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = settings.openai_model
            self.model_fast = settings.openai_model_fast
            self.model_vision = settings.openai_model_vision
        except ImportError:
            raise ImportError(
                "openai package required for OpenAIProvider. Install with: pip install openai"
            )

    @property
    def provider_name(self) -> str:
        return "openai"

    async def _chat_completions_create(self, **kwargs):
        """Create chat completion with compatibility retries for model-specific params."""
        payload = dict(kwargs)

        for _ in range(4):
            try:
                return await self.client.chat.completions.create(**payload)
            except Exception as e:
                msg = str(e).lower()

                # Newer OpenAI models: max_tokens → max_completion_tokens
                if (
                    "unsupported parameter" in msg
                    and "max_tokens" in msg
                    and "max_completion_tokens" in msg
                    and "max_tokens" in payload
                ):
                    payload["max_completion_tokens"] = payload.pop("max_tokens")
                    continue

                # Gemini / OpenRouter: max_completion_tokens → max_tokens
                if (
                    ("max_completion_tokens" in msg or "unknown field" in msg or "extra inputs" in msg)
                    and "max_completion_tokens" in payload
                ):
                    payload["max_tokens"] = payload.pop("max_completion_tokens")
                    continue

                # Some models only allow default temperature=1 and reject custom values.
                if (
                    "temperature" in msg
                    and ("unsupported value" in msg or "only the default" in msg)
                    and "temperature" in payload
                ):
                    payload.pop("temperature", None)
                    continue

                raise

        raise RuntimeError("OpenAI compatibility retry loop exhausted")

    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON from OpenAI response, handling markdown code blocks and syntax errors."""
        import re
        from json_repair import repair_json

        if not content or not content.strip():
            raise ValueError("Empty response from OpenAI")

        # Extract JSON from markdown code block if present
        if "```json" in content or "```" in content:
            json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            else:
                json_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)

        # If still not a JSON object, extract from surrounding text
        if not content.strip().startswith("{"):
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("openai_json_parse_strict_fail filename=<redacted> error=%s attempting_repair=True", e)

        try:
            repaired = repair_json(content, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
            repaired_str = repair_json(content)
            result = json.loads(repaired_str)
            if isinstance(result, dict):
                return result
            raise ValueError(f"Repaired JSON is not a dict: {type(result)}")
        except Exception as repair_err:
            logger.error("openai_json_repair_failed error=%s", repair_err, exc_info=True)
            raise json.JSONDecodeError(f"Could not parse or repair JSON: {repair_err}", content, 0)

    def _normalize_cover_letter_draft_data(
        self,
        data: Dict[str, Any],
        quotation_data: Dict[str, Any],
        company_info: Dict[str, str],
    ) -> Dict[str, Any]:
        """Backfill required draft fields when the model omits them."""
        normalized: Dict[str, Any] = dict(data or {})

        to_name = normalized.get("to_name") or quotation_data.get("client") or quotation_data.get("client_name") or ""
        to_company = normalized.get("to_company") or quotation_data.get("to_company") or to_name

        normalized.setdefault("date", quotation_data.get("date") or quotation_data.get("quotation_date") or "")
        normalized.setdefault("to_name", to_name)
        normalized.setdefault("to_company", to_company)
        normalized.setdefault("subject", "Submission of Techno-Commercial Offer")
        normalized.setdefault("reference", quotation_data.get("reference_number") or quotation_data.get("reference") or "")

        sections = normalized.get("sections")
        if not isinstance(sections, list) or not sections:
            normalized["sections"] = [
                {
                    "section_id": "summary",
                    "title": "Offer Summary",
                    "content": "Please find attached our techno-commercial offer for your review.",
                }
            ]

        normalized.setdefault("closing", "Thank you for your consideration.")
        normalized.setdefault("signatory_name", company_info.get("signatory_name") or settings.signatory_name)
        normalized.setdefault("signatory_title", company_info.get("signatory_title") or settings.signatory_title)

        return normalized

    async def extract_from_document(
        self,
        file_bytes: bytes,
        file_type: str,
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract structured engineering data from document text."""
        import time as _time
        text = file_bytes.decode("utf-8", errors="replace")
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        truncated_text = text[:DOCUMENT_TEXT_CHAR_LIMIT]
        prompt = DOCUMENT_EXTRACTION_PROMPT.format(
            filename=filename,
            text=truncated_text,
            context=context_note
        )
        logger.debug(
            "openai_extract_document_start filename=%s text_len=%d model=%s",
            filename, len(truncated_text), self.model,
        )
        _t0 = _time.perf_counter()
        response = await self._chat_completions_create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=16000,
            response_format={"type": "json_object"},
        )
        elapsed_ms = (_time.perf_counter() - _t0) * 1000
        usage = response.usage
        logger.info(
            "openai_extract_document_ok filename=%s model=%s elapsed_ms=%.0f "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            filename, self.model, elapsed_ms,
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
            getattr(usage, "total_tokens", "?"),
        )
        content = response.choices[0].message.content
        data = self._parse_json_response(content)
        data["raw_text"] = text
        return ExtractedDataResponse(**data)

    async def extract_from_image(
        self,
        image_bytes: bytes | List[bytes],
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract engineering data from drawing/screenshot image using vision."""
        image_list = image_bytes if isinstance(image_bytes, list) else [image_bytes]

        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            mime = "image/png"
        else:
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                        "gif": "image/gif", "webp": "image/webp"}
            mime = mime_map.get(ext, "image/png")

        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""

        user_content: List[Any] = [
            {
                "type": "text",
                "text": IMAGE_EXTRACTION_PROMPT.format(
                    filename=filename,
                    context=context_note
                )
            }
        ]

        for img_bytes in image_list:
            b64_image = base64.standard_b64encode(img_bytes).decode("utf-8")
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64_image}"}
            })

        import time as _time
        logger.debug(
            "openai_extract_image_start filename=%s images=%d model=%s",
            filename, len(image_list), self.model_vision,
        )
        _t0 = _time.perf_counter()
        response = await self._chat_completions_create(
            model=self.model_vision,
            messages=[
                {"role": "system", "content": DRAWING_READER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0,
            max_completion_tokens=8192,
            response_format={"type": "json_object"},
        )
        elapsed_ms = (_time.perf_counter() - _t0) * 1000
        usage = response.usage
        logger.info(
            "openai_extract_image_ok filename=%s model=%s images=%d elapsed_ms=%.0f "
            "prompt_tokens=%s completion_tokens=%s",
            filename, self.model_vision, len(image_list), elapsed_ms,
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
        )
        content = response.choices[0].message.content
        data = self._parse_json_response(content)
        data = _flatten_extraction(data)
        return ExtractedDataResponse(**data)

    async def extract_from_multiple_files(
        self,
        files: List[Dict[str, Any]],
        additional_context: Optional[str] = None,
    ) -> ExtractedDataResponse:
        """Render all PDFs to page images and send all files to OpenAI in a single vision call."""
        import fitz
        _IMG_MIMES = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp",
        }
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        filenames = ", ".join(f.get("filename", "") for f in files)
        prompt = IMAGE_EXTRACTION_PROMPT.format(filename=filenames, context=context_note)
        user_content: List[Any] = [{"type": "text", "text": prompt}]

        for f in files:
            fn = f.get("filename", "")
            fb = f.get("bytes", b"")
            ft = f.get("file_type", "")
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
            is_pdf = fn.lower().endswith(".pdf") or "pdf" in ft.lower()
            is_img = ext in _IMG_MIMES

            if is_pdf:
                doc = fitz.open(stream=fb, filetype="pdf")
                try:
                    for page in doc:
                        pix = page.get_pixmap(dpi=150)
                        b64 = base64.standard_b64encode(pix.tobytes("png")).decode("utf-8")
                        user_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        })
                finally:
                    doc.close()
            elif is_img:
                mime = _IMG_MIMES.get(ext, "image/png")
                b64 = base64.standard_b64encode(fb).decode("utf-8")
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
            else:
                text = fb.decode("utf-8", errors="replace")[:DOCUMENT_TEXT_CHAR_LIMIT]
                user_content.append({"type": "text", "text": f"=== File: {fn} ===\n{text}"})

        response = await self._chat_completions_create(
            model=self.model_vision,
            messages=[
                {"role": "system", "content": DRAWING_READER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.0,
            max_completion_tokens=8192,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = self._parse_json_response(content)
        data = _flatten_extraction(data)
        return ExtractedDataResponse(**data)

    async def parse_boq(
        self,
        text: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        prompt = BOQ_PARSE_PROMPT.format(text=text[:12000], context=context_note)

        response = await self._chat_completions_create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=4096,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        data = self._parse_json_response(content)
        return ExtractedDataResponse(**data)

    async def classify_member(self, description: str) -> MemberClassification:
        prompt = MEMBER_CLASSIFY_PROMPT.format(description=description)
        try:
            response = await self._chat_completions_create(
                model=self.model_fast,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_completion_tokens=512,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = self._parse_json_response(content)
            return MemberClassification(**data)
        except Exception as e:
            logger.error(f"OpenAI classify error: {e}")
            return MemberClassification(
                section_type="unknown", material_grade="unknown",
                confidence=0.0, reasoning=str(e)
            )

    async def parse_quotation(self, text: str) -> Dict[str, Any]:
        prompt = QUOTATION_PARSE_PROMPT.format(text=text[:12000])
        try:
            response = await self._chat_completions_create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_completion_tokens=4096,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"OpenAI quotation parse error: {e}")
            return {"error": str(e)}

    async def draft_cover_letter(
        self,
        quotation_data: Dict[str, Any],
        template_clauses: str,
        company_info: Dict[str, str]
    ) -> CoverLetterDraft:
        prompt = COVER_LETTER_DRAFT_PROMPT.format(
            quotation_data=str(quotation_data),
            template_clauses=template_clauses[:8000],
            company_info=str(company_info)
        )
        try:
            response = await self._chat_completions_create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_completion_tokens=6000,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = self._parse_json_response(content)
            data = self._normalize_cover_letter_draft_data(data, quotation_data, company_info)
            return CoverLetterDraft(**data)
        except Exception as e:
            logger.error(f"OpenAI cover letter draft error: {e}")
            raise

    async def chat(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None
    ) -> ChatResponse:
        import asyncio

        system_msg = SYSTEM_PROMPT_ENGINEER
        if context:
            system_msg += f"\n\nCurrent job context:\n{context}"
        full_messages = [{"role": "system", "content": system_msg}] + messages

        async def _call(model: str):
            response = await self._chat_completions_create(
                model=model,
                messages=full_messages,
                max_completion_tokens=2048,
            )
            return ChatResponse(
                content=response.choices[0].message.content,
                model_used=model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else {}
            )

        # Transient overload/unavailable errors (e.g. 503 UNAVAILABLE) are retried
        # with backoff, then as a last resort against the fast model.
        max_attempts = 3
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return await _call(self.model)
            except Exception as e:
                last_exc = e
                transient = any(t in str(e) for t in ("503", "UNAVAILABLE", "overloaded"))
                logger.error(f"OpenAI chat error (attempt {attempt + 1}/{max_attempts}): {e}")
                if not transient or attempt == max_attempts - 1:
                    break
                await asyncio.sleep(2 ** attempt)

        if self.model_fast and self.model_fast != self.model:
            try:
                logger.warning("Falling back to fast model %s after repeated overload errors", self.model_fast)
                return await _call(self.model_fast)
            except Exception as e:
                logger.error(f"OpenAI chat fallback error: {e}")
                last_exc = e

        raise last_exc

    async def complete(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.1) -> str:
        """Direct completion using raw OpenAI client with proper token param for newer models."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def chat_with_attachments(
        self,
        prompt: str,
        images: Optional[List[Dict[str, Any]]] = None,
        pdfs: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        previous_response_id: Optional[str] = None,
    ) -> ChatResponse:
        """Raw LLM inference test — plain prompt, no costing schema/system prompt.
        Files are sent as-is — no text extraction, no page rasterizing.

        Chat Completions has no native PDF/document input, so real OpenAI uses the
        Responses API per OpenAI's file-inputs guide: PDFs and other documents
        (docx, pptx, xlsx, csv, txt, ...) are uploaded via the Files API
        (`purpose="user_data"`) and referenced by file_id as `input_file` blocks;
        images go in inline as base64 `input_image` blocks. `previous_response_id`
        chains a follow-up onto a prior response natively, without resending
        earlier files/messages. Gemini/OpenRouter subclass this provider but proxy
        to endpoints that don't implement the Files/Responses APIs, so they fall
        back to the old inline Chat Completions path below (images/PDFs only).
        """
        if self.provider_name != "openai":
            return await self._chat_completions_with_attachments(prompt, images, pdfs)

        input_content: List[Any] = [{"type": "input_text", "text": prompt}]
        model = self.model

        for pdf in (pdfs or []):
            filename = pdf.get("filename", "document.pdf")
            uploaded = await self.client.files.create(
                file=(filename, pdf["bytes"], "application/pdf"),
                purpose="user_data",
            )
            input_content.append({"type": "input_file", "file_id": uploaded.id, "detail": "auto"})
            model = self.model_vision

        for doc in (documents or []):
            filename = doc.get("filename", "document")
            uploaded = await self.client.files.create(
                file=(filename, doc["bytes"], doc.get("mime") or "application/octet-stream"),
                purpose="user_data",
            )
            input_content.append({"type": "input_file", "file_id": uploaded.id})

        for img in (images or []):
            b64_image = base64.standard_b64encode(img["bytes"]).decode("utf-8")
            input_content.append({
                "type": "input_image",
                "image_url": f"data:{img['mime']};base64,{b64_image}",
                "detail": "auto",
            })
            model = self.model_vision

        request_kwargs: Dict[str, Any] = {
            "model": model,
            "input": [{"role": "user", "content": input_content}],
        }
        if previous_response_id:
            request_kwargs["previous_response_id"] = previous_response_id

        response = await self.client.responses.create(**request_kwargs)
        usage = getattr(response, "usage", None)
        return ChatResponse(
            content=response.output_text,
            model_used=model,
            usage={
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
            } if usage else {},
            response_id=response.id,
        )

    async def _chat_completions_with_attachments(
        self,
        prompt: str,
        images: Optional[List[Dict[str, Any]]] = None,
        pdfs: Optional[List[Dict[str, Any]]] = None,
    ) -> ChatResponse:
        """Fallback for OpenAI-compatible endpoints (Gemini, OpenRouter) that don't
        implement the Files/Responses APIs — inline attachments via Chat Completions.
        Non-PDF documents and multi-turn `previous_response_id` chaining aren't
        supported on this path."""
        user_content: List[Any] = [{"type": "text", "text": prompt}]
        model = self.model

        for pdf in (pdfs or []):
            b64_pdf = base64.standard_b64encode(pdf["bytes"]).decode("utf-8")
            user_content.append({
                "type": "file",
                "file": {
                    "filename": pdf.get("filename", "document.pdf"),
                    "file_data": f"data:application/pdf;base64,{b64_pdf}",
                }
            })
            model = self.model_vision

        for img in (images or []):
            b64_image = base64.standard_b64encode(img["bytes"]).decode("utf-8")
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{img['mime']};base64,{b64_image}"}
            })
            model = self.model_vision

        response = await self._chat_completions_create(
            model=model,
            messages=[{"role": "user", "content": user_content}],
            max_completion_tokens=2048,
        )
        usage = response.usage
        return ChatResponse(
            content=response.choices[0].message.content or "",
            model_used=model,
            usage={
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            } if usage else {}
        )

