"""
Groq AI Provider — uses groq SDK + instructor for structured outputs.
Model selection:
  - Large/complex tasks: llama-3.3-70b-versatile (supports vision via base64)
  - Fast/simple tasks:   llama-3.1-8b-instant
"""
import base64
import logging
from typing import Any, Dict, List, Optional

import instructor
from groq import AsyncGroq
from pydantic import BaseModel

from app.ai.ai_provider import (
    AIProvider, ExtractedDataResponse, DimensionItem, ExtractionFlag,
    MemberClassification, CoverLetterDraft, CoverLetterSection, ChatResponse
)
from app.ai.prompts import (
    DOCUMENT_EXTRACTION_PROMPT, IMAGE_EXTRACTION_PROMPT,
    BOQ_PARSE_PROMPT, MEMBER_CLASSIFY_PROMPT,
    QUOTATION_PARSE_PROMPT, COVER_LETTER_DRAFT_PROMPT,
    SYSTEM_PROMPT_ENGINEER
)
from app.config import settings

logger = logging.getLogger(__name__)

DOCUMENT_TEXT_CHAR_LIMIT = 50000


class GroqProvider(AIProvider):

    def __init__(self):
        raw_client = AsyncGroq(api_key=settings.groq_api_key)
        self.client = instructor.from_groq(raw_client, mode=instructor.Mode.JSON)
        self.raw_client = raw_client
        self.model_large = settings.groq_model_large
        self.model_fast = settings.groq_model_fast
        self.model_vision = settings.groq_vision_model

    @property
    def provider_name(self) -> str:
        return "groq"

    async def extract_from_document(
        self,
        file_bytes: bytes,
        file_type: str,
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract structured engineering data from document text."""
        # For PDFs/documents, text is pre-extracted before calling AI
        # file_bytes here is UTF-8 text bytes
        text = file_bytes.decode("utf-8", errors="replace")
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        truncated_text = text[:DOCUMENT_TEXT_CHAR_LIMIT]
        prompt = DOCUMENT_EXTRACTION_PROMPT.format(
            filename=filename,
            text=truncated_text,
            context=context_note
        )
        response = await self.client.chat.completions.create(
            model=self.model_large,
            response_model=ExtractedDataResponse,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=6000,
        )
        response.raw_text = text
        return response

    async def extract_from_image(
        self,
        image_bytes: bytes | List[bytes],
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract engineering data from drawing/screenshot image using vision."""
        image_list = image_bytes if isinstance(image_bytes, list) else [image_bytes]
        ext = filename.rsplit(".", 1)[-1].lower()
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
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
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64_image}"}
                }
            )

        # Vision call via raw client (instructor vision not always stable)
        raw_response = await self.raw_client.chat.completions.create(
            model=self.model_vision,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            temperature=0.1,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        import json
        data = json.loads(raw_response.choices[0].message.content)

        # Robust repair for flag format (some models return strings instead of objects)
        # Flatten nested structures into 'dimensions' for backward compatibility with costing engine
        dimensions = []
        if "structural_elements" in data and isinstance(data["structural_elements"], list):
            for el in data["structural_elements"]:
                dimensions.append({
                    "item_tag": el.get("support_tag") or el.get("item_tag"),
                    "description": el.get("item_description") or el.get("description"),
                    "section_type": el.get("section_type"),
                    "material_grade": el.get("material_grade"),
                    "length_mm": el.get("length_mm"),
                    "width_mm": el.get("width_mm"),
                    "thickness_mm": el.get("thickness_mm"),
                    "quantity": el.get("quantity", 1),
                    "weld_joints": el.get("weld_length_mm"), # approximation
                    "surface_area_m2": el.get("surface_area_m2"),
                    "notes": el.get("notes"),
                    "confidence": 0.9
                })
        
        if "bolts_and_plates" in data and isinstance(data["bolts_and_plates"], list):
            for bp in data["bolts_and_plates"]:
                dimensions.append({
                    "item_tag": "BOLT/PLATE",
                    "description": bp.get("item_description"),
                    "section_type": "plate" if "plate" in bp.get("item_description", "").lower() else "bolt",
                    "material_grade": bp.get("grade"),
                    "length_mm": bp.get("length_mm"),
                    "quantity": bp.get("quantity", 0),
                    "notes": bp.get("notes"),
                    "confidence": 0.9
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
            model=self.model_large,
            response_model=ExtractedDataResponse,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4096,
        )
        return response

    async def classify_member(self, description: str) -> MemberClassification:
        prompt = MEMBER_CLASSIFY_PROMPT.format(description=description)
        try:
            response = await self.client.chat.completions.create(
                model=self.model_fast,
                response_model=MemberClassification,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=512,
            )
            return response
        except Exception as e:
            logger.error(f"Groq classify error: {e}")
            return MemberClassification(
                section_type="unknown", material_grade="unknown",
                confidence=0.0, reasoning=str(e)
            )

    async def parse_quotation(self, text: str) -> Dict[str, Any]:
        prompt = QUOTATION_PARSE_PROMPT.format(text=text[:12000])
        try:
            raw = await self.raw_client.chat.completions.create(
                model=self.model_large,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            import json
            return json.loads(raw.choices[0].message.content)
        except Exception as e:
            logger.error(f"Groq quotation parse error: {e}")
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
                model=self.model_large,
                response_model=CoverLetterDraft,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_ENGINEER},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=6000,
            )
            return response
        except Exception as e:
            logger.error(f"Groq cover letter draft error: {e}")
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
            raw = await self.raw_client.chat.completions.create(
                model=self.model_large,
                messages=[{"role": "system", "content": system_msg}] + messages,
                temperature=0.3,
                max_tokens=2048,
            )
            return ChatResponse(
                content=raw.choices[0].message.content,
                model_used=self.model_large,
                usage=dict(raw.usage) if raw.usage else {}
            )
        except Exception as e:
            logger.error(f"Groq chat error: {e}")
            return ChatResponse(content=f"Error: {str(e)}", model_used=self.model_large)
