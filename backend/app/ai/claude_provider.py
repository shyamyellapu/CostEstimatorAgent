"""
Claude AI Provider — Anthropic Claude implementation.
Implements the same AIProvider interface as GroqProvider.
Swap in by setting AI_PROVIDER=claude in .env
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

DOCUMENT_TEXT_CHAR_LIMIT = 50000


class ClaudeProvider(AIProvider):

    def __init__(self):
        # Import only when actually used
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.model = settings.claude_model
        except ImportError:
            raise ImportError("anthropic package required for ClaudeProvider. Install with: pip install anthropic")

    def _model_rejects_temperature(self) -> bool:
        """Return True for model families that reject temperature."""
        model_name = (self.model or "").lower()
        return model_name.startswith("claude-opus-4-7")

    async def _messages_create(
        self,
        *,
        max_tokens: int,
        system: str,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ):
        """Create Claude message with compatibility handling for deprecated params."""
        payload: Dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if temperature is not None and not self._model_rejects_temperature():
            payload["temperature"] = temperature

        try:
            return await self.client.messages.create(**payload)
        except Exception as e:
            # Safety retry for models that now reject temperature.
            if "temperature" in str(e).lower() and "deprecated" in str(e).lower() and "temperature" in payload:
                payload.pop("temperature", None)
                return await self.client.messages.create(**payload)
            raise

    @property
    def provider_name(self) -> str:
        return "claude"
    
    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON from Claude response, handling markdown code blocks and syntax errors."""
        import re
        from json_repair import repair_json

        logger.debug("claude_parse_json_response content_len=%d", len(content))
        
        if not content or not content.strip():
            raise ValueError("Empty response from Claude")
        
        # Extract JSON from markdown code block if present ANYWHERE in the response
        if "```json" in content or "```" in content:
            json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                logger.debug("claude_json_found_in_json_block")
                content = json_match.group(1)
            else:
                json_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    logger.debug("claude_json_found_in_generic_block")
                    content = json_match.group(1)
        
        # If still not a JSON object, extract from surrounding text
        if not content.strip().startswith("{"):
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                logger.debug("claude_json_extracted_from_text")
                content = json_match.group(1)
        
        # First attempt: strict parse
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("claude_json_strict_parse_failed error=%s attempting_repair=True", e)
        
        # Second attempt: repair and parse (handles trailing commas, missing commas, truncation, etc.)
        try:
            repaired = repair_json(content, return_objects=True)
            if isinstance(repaired, dict):
                logger.debug("claude_json_repaired_ok")
                return repaired
            repaired_str = repair_json(content)
            result = json.loads(repaired_str)
            if isinstance(result, dict):
                return result
            raise ValueError(f"Repaired JSON is not a dict: {type(result)}")
        except Exception as repair_err:
            logger.error(
                "claude_json_repair_failed error=%s content_preview=%s",
                repair_err, content[:500], exc_info=True,
            )
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
            "claude_extract_document_start filename=%s text_len=%d model=%s",
            filename, len(truncated_text), self.model,
        )
        _t0 = _time.perf_counter()
        try:
            response = await self._messages_create(
                max_tokens=6000,
                temperature=0.1,
                system=SYSTEM_PROMPT_ENGINEER,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            elapsed_ms = (_time.perf_counter() - _t0) * 1000
            usage = getattr(response, "usage", None)
            logger.info(
                "claude_extract_document_ok filename=%s model=%s elapsed_ms=%.0f "
                "input_tokens=%s output_tokens=%s",
                filename, self.model, elapsed_ms,
                getattr(usage, "input_tokens", "?"),
                getattr(usage, "output_tokens", "?"),
            )
            content = response.content[0].text
            data = self._parse_json_response(content)
            data["raw_text"] = text
            return ExtractedDataResponse(**data)
        except Exception as e:
            elapsed_ms = (_time.perf_counter() - _t0) * 1000
            logger.error(
                "claude_extract_document_failed filename=%s model=%s elapsed_ms=%.0f "
                "exc_type=%s exc=%s",
                filename, self.model, elapsed_ms, type(e).__name__, e, exc_info=True,
            )
            raise

    async def extract_from_image(
        self,
        image_bytes: bytes | List[bytes],
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract engineering data from drawing/screenshot image using vision."""
        image_list = image_bytes if isinstance(image_bytes, list) else [image_bytes]
        
        # Determine mime type from filename extension
        # If PDF, the bytes are actually PNG from pdf_to_images conversion
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            # PDF files are converted to PNG images by pdf_to_images()
            mime = "image/png"
        else:
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}
            mime = mime_map.get(ext, "image/png")
        
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""

        user_content = [
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
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": b64_image
                }
            })

        try:
            import time as _time
            logger.debug(
                "claude_extract_image_start filename=%s images=%d model=%s",
                filename, len(image_list), self.model,
            )
            _t0 = _time.perf_counter()
            
            response = await self._messages_create(
                max_tokens=8192,
                temperature=0.0,
                system=DRAWING_READER_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_content}
                ]
            )
            elapsed_ms = (_time.perf_counter() - _t0) * 1000
            usage = getattr(response, "usage", None)
            logger.info(
                "claude_extract_image_ok filename=%s model=%s images=%d elapsed_ms=%.0f "
                "input_tokens=%s output_tokens=%s",
                filename, self.model, len(image_list), elapsed_ms,
                getattr(usage, "input_tokens", "?"),
                getattr(usage, "output_tokens", "?"),
            )
            
            if not response.content or len(response.content) == 0:
                raise ValueError("Empty content in Claude response")
            
            if len(response.content) > 1:
                logger.warning("claude_multiple_content_blocks filename=%s blocks=%d", filename, len(response.content))
            
            content = response.content[0].text
            logger.debug("claude_image_response_len filename=%s content_len=%d", filename, len(content))
            data = self._parse_json_response(content)

            # Robust repair for flag format and flatten nested structures
            dimensions = []
            if "structural_elements" in data and isinstance(data["structural_elements"], list):
                for el in data["structural_elements"]:
                    dimensions.append({
                        "item_tag":             el.get("support_tag") or el.get("tag") or el.get("item_tag"),
                        "description":          el.get("item_description") or el.get("description"),
                        "section_type":         el.get("section_type"),
                        "section_designation":  el.get("section_designation"),
                        "material_grade":       el.get("material_grade"),
                        "length_mm":            el.get("length_mm") or el.get("l_mm"),
                        "width_mm":             el.get("width_mm") or el.get("w_mm"),
                        "thickness_mm":         el.get("thickness_mm") or el.get("t_mm"),
                        "od_mm":                el.get("od_mm"),
                        "quantity":             el.get("quantity") or el.get("qty") or 1,
                        # Pre-computed weights from Claude — most accurate, use these first
                        "unit_weight_kg_per_m": el.get("unit_weight_kg_per_m"),
                        "total_weight_kg":      el.get("total_weight_kg") or el.get("weight_kg"),
                        # Weld details
                        "weld_length_per_joint_mm": el.get("weld_length_per_joint_mm"),
                        "weld_size_mm":         el.get("weld_size_mm"),
                        "weld_type":            el.get("weld_type"),
                        # Surface area
                        "surface_area_m2":      el.get("surface_area_m2"),
                        "is_existing":          el.get("is_existing", False),
                        "notes":                el.get("notes"),
                        "confidence":           0.9,
                    })
            
            if "bolts_and_plates" in data and isinstance(data["bolts_and_plates"], list):
                for bp in data["bolts_and_plates"]:
                    desc = bp.get("item_description") or bp.get("description") or ""
                    dimensions.append({
                        "item_tag":             "BOLT",
                        "description":          desc,
                        "section_type":         "plate" if "plate" in desc.lower() else "bolt",
                        "material_grade":       bp.get("grade"),
                        "length_mm":            bp.get("length_mm"),
                        "quantity":             bp.get("quantity") or bp.get("qty") or 0,
                        "notes":                bp.get("notes"),
                        "confidence":           0.9,
                    })
            
            data["dimensions"] = dimensions
            return ExtractedDataResponse(**data)
        except Exception as e:
            logger.error(
                "claude_extract_image_failed filename=%s exc_type=%s exc=%s",
                filename, type(e).__name__, e, exc_info=True,
            )
            raise

    async def parse_boq(
        self,
        text: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        prompt = BOQ_PARSE_PROMPT.format(text=text[:12000], context=context_note)
        
        try:
            response = await self._messages_create(
                max_tokens=4096,
                temperature=0.1,
                system=SYSTEM_PROMPT_ENGINEER,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            data = self._parse_json_response(content)
            return ExtractedDataResponse(**data)
        except Exception as e:
            logger.error(f"Claude BOQ parse error: {e}")
            raise

    async def classify_member(self, description: str) -> MemberClassification:
        prompt = MEMBER_CLASSIFY_PROMPT.format(description=description)
        
        try:
            response = await self._messages_create(
                max_tokens=512,
                temperature=0.0,
                system=SYSTEM_PROMPT_ENGINEER,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            data = self._parse_json_response(content)
            return MemberClassification(**data)
        except Exception as e:
            logger.error(f"Claude classify error: {e}")
            return MemberClassification(
                section_type="unknown", material_grade="unknown",
                confidence=0.0, reasoning=str(e)
            )

    async def parse_quotation(self, text: str) -> Dict[str, Any]:
        prompt = QUOTATION_PARSE_PROMPT.format(text=text[:12000])
        
        try:
            response = await self._messages_create(
                max_tokens=4096,
                temperature=0.1,
                system=SYSTEM_PROMPT_ENGINEER,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"Claude quotation parse error: {e}")
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
            response = await self._messages_create(
                max_tokens=6000,
                temperature=0.2,
                system=SYSTEM_PROMPT_ENGINEER,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            data = self._parse_json_response(content)
            data = self._normalize_cover_letter_draft_data(data, quotation_data, company_info)
            return CoverLetterDraft(**data)
        except Exception as e:
            logger.error(f"Claude cover letter draft error: {e}")
            raise

    async def chat(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None
    ) -> ChatResponse:
        system_msg = SYSTEM_PROMPT_ENGINEER
        if context:
            system_msg += f"\n\nCurrent job context:\n{context}"
        
        try:
            response = await self._messages_create(
                max_tokens=2048,
                system=system_msg,
                messages=messages
            )
            
            content = response.content[0].text
            usage_dict = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
            
            return ChatResponse(
                content=content,
                model_used=self.model,
                usage=usage_dict
            )
        except Exception as e:
            logger.error(f"Claude chat error: {e}")
            raise

    async def complete(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.1) -> str:
        """Direct completion using Anthropic client."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
