"""
Drawing Extraction Completeness Validation
==========================================

Validation utilities for ensuring drawing extraction completeness
based on the Drawing Reader Accuracy Report requirements.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class CompletenessReport:
    """Completeness validation report."""
    is_complete: bool
    score_percent: float
    sheets_in_title_block: int
    sheets_processed: int
    tags_extracted: int
    section_types_found: List[str]
    total_weight_kg: float
    warnings: List[str]
    recommendations: List[str]
    status: str  # "COMPLETE", "INCOMPLETE", "PARTIAL"


def extract_sheet_count_from_text(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract sheet count from title block text.
    
    Looks for patterns like:
        "Sheet 01 of 03"
        "Sheet 1 of 3"
        "Sh. 2/5"
        "Page 1 of 2"
        
    Returns:
        Tuple of (current_sheet, total_sheets) or (None, None)
    """
    # Try various patterns
    patterns = [
        r'Sheet\s+(\d+)\s+of\s+(\d+)',
        r'Sh\.?\s+(\d+)\s*/\s*(\d+)',
        r'Page\s+(\d+)\s+of\s+(\d+)',
        r'Drawing\s+(\d+)\s+of\s+(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            return current, total
    
    return None, None


def count_pdf_pages_from_metadata(text: str) -> Optional[int]:
    """Extract PDF page count from metadata marker.
    
    Looks for: "=== PDF METADATA: Total Pages = X ==="
    """
    match = re.search(r'PDF METADATA: Total Pages = (\d+)', text)
    if match:
        return int(match.group(1))
    return None


def detect_section_types(extracted_data: Dict) -> List[str]:
    """Detect which section types were found in extraction.
    
    Args:
        extracted_data: The extraction JSON response
        
    Returns:
        List of section type codes found (UC, UB, PFC, L, etc.)
    """
    section_types = set()
    
    # Check structural_elements
    if "structural_elements" in extracted_data:
        for element in extracted_data["structural_elements"]:
            section = element.get("section", "") or element.get("section_designation", "")
            
            # Extract section type prefix
            match = re.match(r'^([A-Z]+)', section.upper())
            if match:
                section_type = match.group(1)
                section_types.add(section_type)
    
    return sorted(list(section_types))


def validate_weight_reasonableness(
    total_weight_kg: float,
    tags_count: int,
    min_weight_per_tag: float = 5.0
) -> Tuple[bool, Optional[str]]:
    """Check if total weight is reasonable for the number of tags.
    
    Args:
        total_weight_kg: Total extracted weight
        tags_count: Number of structural tags
        min_weight_per_tag: Minimum expected weight per tag
        
    Returns:
        Tuple of (is_reasonable, warning_message)
    """
    if total_weight_kg == 0:
        return False, "Total weight is zero - likely missing data"
    
    if tags_count == 0:
        return False, "No tags extracted"
    
    avg_weight = total_weight_kg / tags_count
    if avg_weight < min_weight_per_tag:
        return False, (
            f"Average weight per tag ({avg_weight:.1f} kg) is unusually low. "
            f"Expected at least {min_weight_per_tag} kg/tag. "
            "Possible causes: missing sheets, incomplete extraction, or lightweight members."
        )
    
    return True, None


def validate_completeness(
    extracted_json: Dict,
    raw_text: str
) -> CompletenessReport:
    """Validate completeness of drawing extraction.
    
    Implements checks from Drawing Reader Accuracy Report:
    - Multi-sheet processing verification
    - Section type coverage
    - Weight reasonableness
    - Tag count validation
    
    Args:
        extracted_json: The AI extraction response
        raw_text: The original document text
        
    Returns:
        CompletenessReport with validation results
    """
    warnings = []
    recommendations = []
    
    # Extract metadata from JSON
    drawing_metadata = extracted_json.get("drawing_metadata", {})
    structural_elements = extracted_json.get("structural_elements", [])
    weight_summary = extracted_json.get("weight_summary", {})
    completeness_check = extracted_json.get("completeness_check", {})
    
    # 1. Check sheet processing
    title_block_sheets = drawing_metadata.get("total_sheets", 0) or completeness_check.get("sheets_in_title_block", 0)
    processed_sheets = completeness_check.get("sheets_processed", 0)
    pdf_page_count = count_pdf_pages_from_metadata(raw_text)
    
    # Try to extract from raw text if not in JSON
    if title_block_sheets == 0:
        _, detected_total = extract_sheet_count_from_text(raw_text)
        if detected_total:
            title_block_sheets = detected_total
            warnings.append(f"Sheet count detected from text: {detected_total} sheets")
    
    # Validate sheet processing
    sheets_match = True
    if title_block_sheets > 0:
        if processed_sheets == 0:
            processed_sheets = pdf_page_count or 1
        
        if processed_sheets < title_block_sheets:
            sheets_match = False
            warnings.append(
                f"CRITICAL: Only {processed_sheets} sheets processed, "
                f"but title block indicates {title_block_sheets} sheets. "
                "Missing data from incomplete sheet processing."
            )
            recommendations.append(
                "Re-run extraction with all sheets. "
                "Check that PDF contains all pages and AI prompt processes each page."
            )
    
    # 2. Check tags extracted
    tags_count = len(structural_elements)
    if tags_count == 0:
        warnings.append("CRITICAL: No structural tags extracted")
        recommendations.append("Verify drawing contains structural elements and text is readable")
    elif tags_count < (title_block_sheets * 2):  # Expect at least 2 tags per sheet
        warnings.append(
            f"Low tag count: {tags_count} tags from {title_block_sheets} sheets. "
            f"Expected at least {title_block_sheets * 2} tags."
        )
        recommendations.append("Review extraction - may be missing elements from some sheets")
    
    # 3. Check section types
    section_types_found = detect_section_types(extracted_json)
    if not section_types_found:
        warnings.append("No section types detected")
    elif len(section_types_found) == 1 and section_types_found[0] == "UC":
        warnings.append(
            "Only UC sections found. Check for missing PFC, UB, L angles, plates."
        )
        recommendations.append("Verify AI prompt recognizes all section types (UC, UB, PFC, L, RHS, SHS, CHS, PL)")
    
    # 4. Check weight
    total_weight = weight_summary.get("total_kg", 0) or weight_summary.get("grand_total_steel_kg", 0)
    weight_reasonable, weight_warning = validate_weight_reasonableness(total_weight, tags_count)
    if not weight_reasonable:
        warnings.append(f"Weight issue: {weight_warning}")
        recommendations.append("Validate weights against section tables")
    
    # 5. Check for bolts/fasteners if cap plates present
    bolts = extracted_json.get("bolts_and_plates", [])
    has_cap_plates = any("cap" in elem.get("description", "").lower() 
                         for elem in structural_elements)
    if has_cap_plates and not bolts:
        warnings.append("Cap plates found but no bolts extracted")
        recommendations.append("Check detail drawings for bolt specifications")
    
    # 6. Check surface treatment data
    surface_treatment = extracted_json.get("surface_treatment", {})
    if not surface_treatment or not surface_treatment.get("blasting_standard"):
        warnings.append("Surface treatment specifications missing or incomplete")
        recommendations.append("Extract blasting and painting requirements from notes")
    
    # Calculate score
    max_score = 100
    deductions = 0
    
    if not sheets_match:
        deductions += 40  # Major deduction for incomplete sheet processing
    if tags_count == 0:
        deductions += 30
    elif tags_count < (title_block_sheets * 2):
        deductions += 15
    if not weight_reasonable:
        deductions += 10
    if len(section_types_found) <= 1:
        deductions += 10
    if has_cap_plates and not bolts:
        deductions += 5
    if not surface_treatment or not surface_treatment.get("blasting_standard"):
        deductions += 5
    
    score = max(0, max_score - deductions)
    
    # Determine status
    if score >= 90:
        status = "COMPLETE"
    elif score >= 70:
        status = "PARTIAL"
    else:
        status = "INCOMPLETE"
    
    is_complete = (sheets_match and tags_count > 0 and weight_reasonable)
    
    return CompletenessReport(
        is_complete=is_complete,
        score_percent=score,
        sheets_in_title_block=title_block_sheets,
        sheets_processed=processed_sheets,
        tags_extracted=tags_count,
        section_types_found=section_types_found,
        total_weight_kg=total_weight,
        warnings=warnings,
        recommendations=recommendations,
        status=status
    )


def format_completeness_report(report: CompletenessReport) -> str:
    """Format completeness report as human-readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("DRAWING EXTRACTION COMPLETENESS REPORT")
    lines.append("=" * 60)
    lines.append(f"Status: {report.status}")
    lines.append(f"Completeness Score: {report.score_percent:.0f}%")
    lines.append("")
    lines.append(f"Sheets in Title Block: {report.sheets_in_title_block}")
    lines.append(f"Sheets Processed: {report.sheets_processed}")
    lines.append(f"Tags Extracted: {report.tags_extracted}")
    lines.append(f"Section Types Found: {', '.join(report.section_types_found) if report.section_types_found else 'None'}")
    lines.append(f"Total Weight: {report.total_weight_kg:.2f} kg")
    lines.append("")
    
    if report.warnings:
        lines.append("WARNINGS:")
        for i, warning in enumerate(report.warnings, 1):
            lines.append(f"  {i}. {warning}")
        lines.append("")
    
    if report.recommendations:
        lines.append("RECOMMENDATIONS:")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")
    
    lines.append("=" * 60)
    return "\n".join(lines)
