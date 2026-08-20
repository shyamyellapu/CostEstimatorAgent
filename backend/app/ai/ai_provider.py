"""
Abstract AI Provider base class.
All AI providers must implement this interface.
The AI layer is ONLY responsible for:
  - Extracting structured data from documents/images
  - Classifying member types and scope
  - Summarizing findings
  - Drafting cover letter content
It must NEVER be used for costing calculations.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"})


class ExtractionFlag(BaseModel):
    field: str = "general"
    reason: str = "No reason provided"
    confidence: float = 0.5


class DimensionItem(BaseModel):
    item_tag: Optional[str] = None
    description: Optional[str] = None
    material_grade: Optional[str] = None
    section_type: Optional[str] = None   # plate / pipe / beam / channel / angle / etc.
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    od_mm: Optional[float] = None         # pipe OD
    quantity: Optional[float] = 1.0
    weld_joints: Optional[int] = None
    weld_length_per_joint_mm: Optional[float] = None
    surface_area_m2: Optional[float] = None
    notes: Optional[str] = None
    confidence: float = 0.0
    flags: List[ExtractionFlag] = []


# ─── Shared Response Models ──────────────────────────────────────────────────

class DrawingMetadata(BaseModel):
    project_name: Optional[str] = ""
    unit_area: Optional[str] = ""
    drawing_number: Optional[str] = ""
    revision: Optional[str] = ""
    client: Optional[str] = ""
    consultant: Optional[str] = ""
    contractor: Optional[str] = ""
    work_order_number: Optional[str] = ""
    scale: Optional[str] = ""
    date_issued: Optional[str] = ""
    total_sheets_in_drawing: Optional[int] = None
    sheets_provided: Optional[int] = None
    sheets_processed: Optional[int] = None
    material_standard: Optional[str] = ""
    referenced_drawings: List[str] = []
    general_notes: List[str] = []


class StructuralElement(BaseModel):
    support_tag: Optional[str] = ""
    item_description: Optional[str] = ""
    section_type: Optional[str] = ""
    section_designation: Optional[str] = ""
    material_grade: Optional[str] = ""
    length_mm: Optional[float] = 0
    width_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    quantity: Optional[float] = 1
    unit_weight_kg_per_m: Optional[float] = 0
    total_weight_kg: Optional[float] = 0
    weld_type: Optional[str] = ""
    weld_size_mm: Optional[float] = None
    weld_length_mm: Optional[float] = None
    surface_area_m2: Optional[float] = 0
    notes: Optional[str] = ""


class BoltPlateItem(BaseModel):
    item_description: Optional[str] = ""
    size_designation: Optional[str] = ""
    grade: Optional[str] = ""
    length_mm: Optional[float] = None
    quantity: Optional[float] = 0
    notes: Optional[str] = ""


class SurfaceTreatmentData(BaseModel):
    blasting_standard: Optional[str] = ""
    paint_system: Optional[str] = ""
    galvanizing_required: bool = False
    galvanized_members: List[str] = []
    total_surface_area_m2: Optional[float] = 0


class WeightSummary(BaseModel):
    total_structural_steel_kg: float = 0
    total_plates_kg: float = 0
    grand_total_steel_kg: float = 0


class CostEstimationInputs(BaseModel):
    structural_steel_rate_usd_per_kg: float = 4.0
    fabrication_welding_manhours: float = 0
    fabrication_fitting_manhours: float = 0
    blasting_area_sqm: float = 0
    painting_area_sqm: float = 0
    bolt_sets_count: int = 0
    paint_litres_estimated: float = 0


class CostingSheetInputs(BaseModel):
    """Aggregate inputs from AI extraction — feed directly into the costing engine."""
    structural_steel_total_kg: float = 0.0
    bolt_quantity_nos: int = 0
    paint_litres: float = 0.0
    welding_hours: float = 0.0
    fabrication_hours: float = 0.0
    galvanizing_weight_kg: float = 0.0
    blasting_area_m2: float = 0.0
    painting_area_m2: float = 0.0


class AmbiguityItem(BaseModel):
    location: str
    issue: str
    assumption_made: str


class ExtractedDataResponse(BaseModel):
    drawing_metadata: Optional[DrawingMetadata] = None
    structural_elements: List[StructuralElement] = []
    bolts_and_plates: List[BoltPlateItem] = []
    surface_treatment: Optional[SurfaceTreatmentData] = None
    weight_summary: Optional[WeightSummary] = None
    cost_estimation_inputs: Optional[CostEstimationInputs] = None
    costing_sheet_inputs: Optional[CostingSheetInputs] = None
    ambiguities: List[AmbiguityItem] = []
    
    # Backward compatibility fields (Flattened versions of above)
    dimensions: List[DimensionItem] = []
    summary: str = ""
    overall_confidence: float = 1.0
    raw_text: Optional[str] = None
    flags: List[ExtractionFlag] = []
    member_types: List[str] = []
    material_references: List[str] = []
    annotations: List[str] = []
    fabrication_notes: List[str] = []


class MemberClassification(BaseModel):
    section_type: str
    material_grade: str
    confidence: float
    reasoning: str


class CoverLetterSection(BaseModel):
    section_id: str
    title: str
    content: str


class CoverLetterDraft(BaseModel):
    date: str
    to_name: str
    to_company: str
    subject: str
    reference: str
    sections: List[CoverLetterSection]
    closing: str
    signatory_name: str
    signatory_title: str


class ChatResponse(BaseModel):
    content: str
    model_used: str
    usage: Dict[str, Any] = {}
    response_id: Optional[str] = None


# ─── Abstract Base ────────────────────────────────────────────────────────────

class AIProvider(ABC):
    """Base class for all AI providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def extract_from_document(
        self,
        file_bytes: bytes,
        file_type: str,
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract engineering data from PDF/DOCX/Excel documents."""
        pass

    @abstractmethod
    async def extract_from_image(
        self,
        image_bytes: bytes | List[bytes],
        filename: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Extract engineering data from drawings/screenshots/images."""
        pass

    @abstractmethod
    async def parse_boq(
        self,
        text: str,
        additional_context: Optional[str] = None
    ) -> ExtractedDataResponse:
        """Parse a BOQ text/table into structured extraction."""
        pass

    @abstractmethod
    async def classify_member(
        self,
        description: str
    ) -> MemberClassification:
        """Classify a structural member type from its description."""
        pass

    @abstractmethod
    async def parse_quotation(
        self,
        text: str
    ) -> Dict[str, Any]:
        """Extract structured quotation fields from quotation document text."""
        pass

    @abstractmethod
    async def draft_cover_letter(
        self,
        quotation_data: Dict[str, Any],
        template_clauses: str,
        company_info: Dict[str, str]
    ) -> CoverLetterDraft:
        """Draft a professional cover letter based on quotation data and template clauses."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None
    ) -> ChatResponse:
        """Handle conversational chat with job context."""
        pass

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.1,
    ) -> str:
        """
        Simple prompt → text completion.
        Wraps chat() so callers don't need to build a messages list.
        Returns the plain text string from the response.
        """
        response = await self.chat([{"role": "user", "content": prompt}])
        return response.content

    async def chat_with_attachments(
        self,
        prompt: str,
        images: Optional[List[Dict[str, Any]]] = None,
        pdfs: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        previous_response_id: Optional[str] = None,
    ) -> "ChatResponse":
        """
        Raw LLM inference test: a free-form prompt plus optional attached files,
        sent to the model with no costing schema or system prompt in the way.

        `images` is a list of {"bytes": bytes, "mime": str} dicts.
        `pdfs` is a list of {"bytes": bytes, "filename": str} dicts — raw PDF bytes,
        no text extraction or page-to-image conversion.
        `documents` is a list of {"bytes": bytes, "filename": str, "mime": str} dicts
        for non-PDF office/text documents (docx, pptx, xlsx, csv, txt, ...).
        `previous_response_id` chains a follow-up onto a prior native provider
        response (only meaningful where the provider supports it, e.g. OpenAI's
        Responses API) — providers that don't support it just ignore it.

        Providers with a native multimodal chat path should override this; the
        default here just ignores any attachments and answers the prompt alone.
        """
        if images or pdfs or documents:
            logger.warning(
                "%s.chat_with_attachments: no multimodal override — %d image(s), %d pdf(s), "
                "%d document(s) ignored",
                self.provider_name, len(images or []), len(pdfs or []), len(documents or [])
            )
        text = await self.complete(prompt)
        return ChatResponse(content=text, model_used=self.provider_name, usage={})

    async def extract_from_multiple_files(
        self,
        files: List[Dict[str, Any]],
        additional_context: Optional[str] = None,
    ) -> "ExtractedDataResponse":
        """
        Send all uploaded files (PDFs, images, docs) to the LLM in a single call.
        Default: processes each file individually then merges results.
        Override in providers that natively support multi-file batching.
        """
        merged = ExtractedDataResponse()
        for f in files:
            fn = f.get("filename", "")
            fb = f.get("bytes", b"")
            ft = f.get("file_type", "")
            suffix = ("." + fn.rsplit(".", 1)[-1].lower()) if "." in fn else ""
            is_img = suffix in _IMAGE_EXTENSIONS
            try:
                if is_img:
                    result = await self.extract_from_image(fb, fn, additional_context)
                else:
                    result = await self.extract_from_document(fb, ft, fn, additional_context)
                merged.structural_elements.extend(result.structural_elements)
                merged.dimensions.extend(result.dimensions)
                merged.bolts_and_plates.extend(result.bolts_and_plates)
                merged.annotations.extend(result.annotations or [])
                merged.fabrication_notes.extend(result.fabrication_notes or [])
                merged.flags.extend(result.flags)
                merged.ambiguities.extend(result.ambiguities)
                if not merged.drawing_metadata and result.drawing_metadata:
                    merged.drawing_metadata = result.drawing_metadata
                if result.overall_confidence > 0:
                    merged.overall_confidence = max(merged.overall_confidence, result.overall_confidence)
                if result.summary:
                    merged.summary = ((merged.summary + " | ") if merged.summary else "") + result.summary
            except Exception as exc:
                logger.warning("extract_from_multiple_files fallback: %s failed: %s", fn, exc)
        return merged


# ---------------------------------------------------------------------------
# Convenience factory — import via:  from app.ai.ai_provider import get_provider
# ---------------------------------------------------------------------------

def get_provider() -> "AIProvider":
    """Return the configured AI provider (same as app.ai.get_ai_provider)."""
    from app.ai import get_ai_provider  # local import avoids circular dependency
    return get_ai_provider()
