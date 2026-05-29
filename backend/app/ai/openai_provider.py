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

DOCUMENT_TEXT_CHAR_LIMIT = 50000


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
            logger.warning(f"Strict JSON parse failed ({e}), attempting repair...")

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
            logger.error(f"JSON repair also failed: {repair_err}")
            raise json.JSONDecodeError(f"Could not parse or repair JSON: {repair_err}", content, 0)

    async def extract_from_document(
        self,
        file_bytes: bytes,
        file_type: str,
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract structured engineering data from document text."""
        text = file_bytes.decode("utf-8", errors="replace")
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        truncated_text = text[:DOCUMENT_TEXT_CHAR_LIMIT]
        prompt = DOCUMENT_EXTRACTION_PROMPT.format(
            filename=filename,
            text=truncated_text,
            context=context_note
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=6000,
            response_format={"type": "json_object"},
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

        response = await self.client.chat.completions.create(
            model=self.model_vision,
            messages=[
                {"role": "system", "content": DRAWING_READER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0,
            max_completion_tokens=8192,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        data = self._parse_json_response(content)

        # Flatten nested structures into 'dimensions'
        dimensions = []
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
        return ExtractedDataResponse(**data)

    async def parse_boq(
        self,
        text: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        prompt = BOQ_PARSE_PROMPT.format(text=text[:12000], context=context_note)

        response = await self.client.chat.completions.create(
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
            response = await self.client.chat.completions.create(
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
            response = await self.client.chat.completions.create(
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
            response = await self.client.chat.completions.create(
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
            return CoverLetterDraft(**data)
        except Exception as e:
            logger.error(f"OpenAI cover letter draft error: {e}")
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_msg}] + messages,
                max_completion_tokens=2048,
            )
            return ChatResponse(
                content=response.choices[0].message.content,
                model_used=self.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else {}
            )
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise

    async def complete(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.1) -> str:
        """Direct completion using raw OpenAI client with proper token param for newer models."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
