"""
RFQ Validation Engine

Rule-based engineering validation + confidence scoring.

Checks performed:
  1. Confidence threshold — flag low-confidence extractions
  2. Unit consistency — detect mixed or unknown units
  3. Quantity sanity — zero qty, implausibly large values
  4. Weight consistency — computed vs extracted weight
  5. Material validation — against MaterialMaster / known standards
  6. Duplicate detection — same tag, same description across items
  7. Missing scope — no line items, no description
  8. Revision change detection — when comparing two RFQ revisions
  9. Dimension sanity — negative / zero dimensions
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known unit and material standard sets
# ---------------------------------------------------------------------------

KNOWN_UNITS = {
    "nos", "kg", "t", "m", "mm", "m2", "m3", "l", "set", "lot",
    "pcs", "each", "unit", "length",
}

KNOWN_MATERIAL_KEYWORDS = [
    "steel", "stainless", "carbon", "alloy", "inconel", "hastelloy",
    "duplex", "copper", "aluminium", "aluminum", "cast iron", "wrought iron",
    "hdpe", "pvc", "frp", "grp", "titanium",
]

PRESSURE_CLASS_PATTERN = re.compile(
    r"(ansi|asme|class|pn|api|jis)[_ ]?([0-9]+[a-z]*)", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Validation result builder
# ---------------------------------------------------------------------------

def _issue(
    validation_type: str,
    severity: str,
    message: str,
    field_name: Optional[str] = None,
    extracted_value: Optional[str] = None,
    suggested_value: Optional[str] = None,
    confidence: Optional[float] = None,
    line_item_index: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "validation_type": validation_type,
        "severity": severity,
        "message": message,
        "field_name": field_name,
        "extracted_value": extracted_value,
        "suggested_value": suggested_value,
        "confidence": confidence,
        "line_item_index": line_item_index,
    }


# ---------------------------------------------------------------------------
# Individual rule validators
# ---------------------------------------------------------------------------

def _validate_confidence(item: dict, idx: int) -> List[dict]:
    issues = []
    score = item.get("confidence_score")
    if score is not None and score < 0.5:
        issues.append(_issue(
            "confidence", "error",
            f"Line {idx + 1}: Very low extraction confidence ({score:.0%}). Manual review required.",
            confidence=score, line_item_index=idx,
        ))
    elif score is not None and score < 0.75:
        issues.append(_issue(
            "confidence", "warning",
            f"Line {idx + 1}: Low extraction confidence ({score:.0%}). Please verify.",
            confidence=score, line_item_index=idx,
        ))
    return issues


def _validate_quantity(item: dict, idx: int) -> List[dict]:
    issues = []
    qty = item.get("quantity")
    if qty is None:
        issues.append(_issue(
            "quantity", "warning",
            f"Line {idx + 1} ({item.get('description', 'N/A')}): Quantity not extracted.",
            field_name="quantity", line_item_index=idx,
        ))
    elif qty <= 0:
        issues.append(_issue(
            "quantity", "error",
            f"Line {idx + 1}: Quantity is zero or negative ({qty}).",
            field_name="quantity", extracted_value=str(qty), line_item_index=idx,
        ))
    elif qty > 100_000:
        issues.append(_issue(
            "quantity", "warning",
            f"Line {idx + 1}: Unusually large quantity ({qty:,.0f}). Please verify.",
            field_name="quantity", extracted_value=str(qty), line_item_index=idx,
        ))
    return issues


def _validate_unit(item: dict, idx: int) -> List[dict]:
    issues = []
    unit = (item.get("unit") or "").lower().strip()
    if not unit:
        issues.append(_issue(
            "unit", "info",
            f"Line {idx + 1}: Unit of measure not specified.",
            field_name="unit", line_item_index=idx,
        ))
    elif unit not in KNOWN_UNITS:
        issues.append(_issue(
            "unit", "warning",
            f"Line {idx + 1}: Unrecognised unit '{unit}'.",
            field_name="unit", extracted_value=unit, line_item_index=idx,
        ))
    return issues


def _validate_material(item: dict, idx: int) -> List[dict]:
    issues = []
    mat = (item.get("material") or "").lower().strip()
    if not mat:
        issues.append(_issue(
            "material", "warning",
            f"Line {idx + 1}: Material of construction not specified.",
            field_name="material", line_item_index=idx,
        ))
    elif not any(kw in mat for kw in KNOWN_MATERIAL_KEYWORDS):
        issues.append(_issue(
            "material", "info",
            f"Line {idx + 1}: Material '{item.get('material')}' not recognised in standard list.",
            field_name="material", extracted_value=item.get("material"), line_item_index=idx,
        ))
    return issues


def _validate_description(item: dict, idx: int) -> List[dict]:
    issues = []
    desc = (item.get("description") or "").strip()
    if not desc:
        issues.append(_issue(
            "scope", "error",
            f"Line {idx + 1}: No description provided for line item.",
            field_name="description", line_item_index=idx,
        ))
    elif len(desc) < 5:
        issues.append(_issue(
            "scope", "warning",
            f"Line {idx + 1}: Very short description '{desc}'. May be incomplete.",
            field_name="description", extracted_value=desc, line_item_index=idx,
        ))
    return issues


def _validate_weight_consistency(item: dict, idx: int) -> List[dict]:
    issues = []
    qty = item.get("quantity")
    wt_each = item.get("weight_each_kg")
    wt_total = item.get("total_weight_kg")

    if qty and wt_each and wt_total:
        computed = qty * wt_each
        if wt_total > 0 and abs(computed - wt_total) / wt_total > 0.05:
            issues.append(_issue(
                "quantity", "warning",
                f"Line {idx + 1}: Weight mismatch. "
                f"qty={qty} × {wt_each} kg = {computed:.1f} kg, but total_weight={wt_total} kg.",
                field_name="total_weight_kg",
                extracted_value=str(wt_total),
                suggested_value=f"{computed:.2f}",
                line_item_index=idx,
            ))
    return issues


def _validate_dimensions(item: dict, idx: int) -> List[dict]:
    issues = []
    dims = item.get("dimensions") or {}
    for dim_key, dim_val in dims.items():
        try:
            fval = float(dim_val)
            if fval < 0:
                issues.append(_issue(
                    "dimension", "error",
                    f"Line {idx + 1}: Negative dimension '{dim_key}' = {fval}.",
                    field_name=f"dimensions.{dim_key}",
                    extracted_value=str(fval),
                    line_item_index=idx,
                ))
        except (TypeError, ValueError):
            pass
    return issues


def _detect_duplicates(items: List[dict]) -> List[dict]:
    """Detect duplicate tag numbers or identical descriptions."""
    issues = []
    seen_tags: dict[str, int] = {}
    seen_descs: dict[str, int] = {}

    for idx, item in enumerate(items):
        tag = (item.get("tag_number") or "").strip()
        desc = (item.get("description") or "").strip().lower()

        if tag:
            if tag in seen_tags:
                issues.append(_issue(
                    "duplicate", "warning",
                    f"Line {idx + 1}: Duplicate tag number '{tag}' also at line {seen_tags[tag] + 1}.",
                    field_name="tag_number", extracted_value=tag, line_item_index=idx,
                ))
            else:
                seen_tags[tag] = idx

        if desc and len(desc) > 10:
            if desc in seen_descs:
                issues.append(_issue(
                    "duplicate", "info",
                    f"Line {idx + 1}: Possibly duplicate description (same as line {seen_descs[desc] + 1}).",
                    field_name="description", extracted_value=desc[:80], line_item_index=idx,
                ))
            else:
                seen_descs[desc] = idx

    return issues


def _validate_scope_completeness(
    line_items: List[dict], metadata: dict
) -> List[dict]:
    issues = []
    if not line_items:
        issues.append(_issue(
            "scope", "error",
            "No line items were extracted from this RFQ. Check document format or re-upload.",
        ))
    if not metadata.get("client_name"):
        issues.append(_issue(
            "scope", "info", "Client name not extracted from document.",
            field_name="client_name",
        ))
    if not metadata.get("scope_summary") and not line_items:
        issues.append(_issue(
            "scope", "warning", "No scope summary available. Add manually.",
            field_name="scope_summary",
        ))
    return issues


# ---------------------------------------------------------------------------
# Revision comparison
# ---------------------------------------------------------------------------

def compare_revisions(
    old_items: List[dict],
    new_items: List[dict],
) -> List[Dict[str, Any]]:
    """
    Compare two lists of line items (old vs new revision).
    Returns list of change dicts with type: added / removed / modified.
    """
    changes: List[dict] = []

    def key(item: dict) -> str:
        return (item.get("tag_number") or item.get("line_number") or item.get("description") or "").strip().lower()

    old_map = {key(i): i for i in old_items}
    new_map = {key(i): i for i in new_items}

    for k, new_item in new_map.items():
        if k not in old_map:
            changes.append({"type": "added", "item": new_item})
        else:
            old_item = old_map[k]
            field_changes: List[dict] = []
            for field in ("quantity", "material", "unit", "weight_each_kg", "total_weight_kg", "description"):
                ov = old_item.get(field)
                nv = new_item.get(field)
                if str(ov) != str(nv) and not (ov is None and nv is None):
                    field_changes.append({"field": field, "old": ov, "new": nv})
            if field_changes:
                changes.append({"type": "modified", "key": k, "item": new_item, "changes": field_changes})

    for k, old_item in old_map.items():
        if k not in new_map:
            changes.append({"type": "removed", "item": old_item})

    return changes


# ---------------------------------------------------------------------------
# Master validation entry-point
# ---------------------------------------------------------------------------

def validate_rfq_extraction(
    line_items: List[dict],
    metadata: dict,
) -> Tuple[List[dict], Dict[str, Any]]:
    """
    Run all validation rules against extracted line items and metadata.

    Returns:
      - issues: List of issue dicts (ready to persist as ValidationResult records)
      - summary: { total, errors, warnings, info, confidence_avg }
    """
    issues: List[dict] = []

    # Per-item validation
    for idx, item in enumerate(line_items):
        issues.extend(_validate_confidence(item, idx))
        issues.extend(_validate_quantity(item, idx))
        issues.extend(_validate_unit(item, idx))
        issues.extend(_validate_material(item, idx))
        issues.extend(_validate_description(item, idx))
        issues.extend(_validate_weight_consistency(item, idx))
        issues.extend(_validate_dimensions(item, idx))

    # Cross-item validation
    issues.extend(_detect_duplicates(line_items))

    # Scope / document-level
    issues.extend(_validate_scope_completeness(line_items, metadata))

    errors   = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")
    info     = sum(1 for i in issues if i["severity"] == "info")

    scores = [i.get("confidence_score") for i in line_items if i.get("confidence_score") is not None]
    conf_avg = sum(scores) / len(scores) if scores else None

    summary = {
        "total": len(issues),
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "confidence_avg": conf_avg,
        "is_valid": errors == 0,
    }

    return issues, summary
