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

    @property
    def provider_name(self) -> str:
        return "claude"
    
    def _parse_json_response(self, content: str) -> dict:
        """Parse JSON from Claude response, handling markdown code blocks and syntax errors."""
        import re
        from json_repair import repair_json

        # Log response for debugging
        logger.info(f"Claude response length: {len(content)}")
        logger.info(f"Claude response (first 1000 chars): {content[:1000]}")
        
        if not content or not content.strip():
            raise ValueError("Empty response from Claude")
        
        # Extract JSON from markdown code block if present ANYWHERE in the response
        if "```json" in content or "```" in content:
            json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                logger.info("Found ```json block in response")
                content = json_match.group(1)
            else:
                json_match = re.search(r'```\s*\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    logger.info("Found generic ``` block in response")
                    content = json_match.group(1)
        
        # If still not a JSON object, extract from surrounding text
        if not content.strip().startswith("{"):
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                logger.info("Extracted JSON object from text")
                content = json_match.group(1)
        
        # First attempt: strict parse
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Strict JSON parse failed ({e}), attempting repair...")
        
        # Second attempt: repair and parse (handles trailing commas, missing commas, truncation, etc.)
        try:
            repaired = repair_json(content, return_objects=True)
            if isinstance(repaired, dict):
                logger.info("JSON repaired successfully")
                return repaired
            # repair_json returned a non-dict (e.g. list or string) — try loading repaired string
            repaired_str = repair_json(content)
            result = json.loads(repaired_str)
            if isinstance(result, dict):
                logger.info("JSON repaired and parsed successfully")
                return result
            raise ValueError(f"Repaired JSON is not a dict: {type(result)}")
        except Exception as repair_err:
            logger.error(f"JSON repair also failed: {repair_err}")
            logger.error(f"Content that failed to parse (first 2000 chars): {content[:2000]}")
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
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=6000,
                temperature=0.1,
                system=SYSTEM_PROMPT_ENGINEER,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            data = self._parse_json_response(content)
            data["raw_text"] = text
            return ExtractedDataResponse(**data)
        except Exception as e:
            logger.error(f"Claude document extraction error: {e}")
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
            logger.info(f"Calling Claude with model: {self.model}")
            logger.info(f"Image count: {len(image_list)}, MIME type: {mime}")
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=8192,  # Increased for complex drawings
                temperature=0.0,   # Zero temp for deterministic JSON
                system=DRAWING_READER_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_content}
                ]
            )
            
            # Log response structure for debugging
            logger.info(f"Claude response type: {type(response)}")
            logger.info(f"Response model: {response.model if hasattr(response, 'model') else 'N/A'}")
            logger.info(f"Response content type: {type(response.content)}")
            logger.info(f"Response content length: {len(response.content) if response.content else 0}")
            
            if not response.content or len(response.content) == 0:
                raise ValueError("Empty content in Claude response")
            
            # Handle multiple content blocks if present
            if len(response.content) > 1:
                logger.warning(f"Multiple content blocks: {len(response.content)}")
                for i, block in enumerate(response.content):
                    logger.info(f"Block {i}: type={type(block)}, {block}")
            
            content = response.content[0].text
            logger.info(f"Extracted text length: {len(content)}")
            logger.info(f"First 1000 chars: {content[:1000]}")
            logger.info(f"Last 500 chars: {content[-500:]}")
            
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
            import traceback
            logger.error(f"Claude image extraction error: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise

    async def parse_boq(
        self,
        text: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        context_note = f"\nAdditional context: {additional_context}" if additional_context else ""
        prompt = BOQ_PARSE_PROMPT.format(text=text[:12000], context=context_note)
        
        try:
            response = await self.client.messages.create(
                model=self.model,
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
            response = await self.client.messages.create(
                model=self.model,
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
            response = await self.client.messages.create(
                model=self.model,
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
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=6000,
                temperature=0.2,
                system=SYSTEM_PROMPT_ENGINEER,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            content = response.content[0].text
            data = self._parse_json_response(content)
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
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0.3,
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
            return ChatResponse(content=f"Error: {str(e)}", model_used=self.model)
