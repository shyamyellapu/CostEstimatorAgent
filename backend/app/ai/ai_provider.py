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
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ExtractionFlag(BaseModel):
    field: str = "general"
    reason: str
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
