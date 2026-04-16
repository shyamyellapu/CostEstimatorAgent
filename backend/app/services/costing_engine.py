"""
Costing Engine — Main Orchestrator.
Accepts confirmed extracted line items + rates, runs all cost modules in sequence.
Returns full breakdown with formulas, audit trail, and totals.
NEVER calls AI — fully deterministic.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import logging

from app.services.weight_calculator import calculate_weight
from app.services.material_cost import calculate_material_cost
from app.services.fabrication_cost import (
    calculate_fabrication_cost, calculate_manhours,
    FabCalcMode, ManhourMode
)
from app.services.welding_cost import calculate_welding_cost
from app.services.consumables_cost import calculate_consumables_cost, ConsumableMode
from app.services.cutting_cost import calculate_cutting_cost, CuttingMode
from app.services.surface_treatment import (
    calculate_surface_treatment,
    estimate_surface_area_plate_m2,
    estimate_surface_area_pipe_m2
)
from app.services.overhead_margin import calculate_overhead_and_margin

logger = logging.getLogger(__name__)


@dataclass
class LineItemCostBreakdown:
    item_tag: str
    description: str
    section_type: str
    quantity: float
    # Weight
    weight_kg: float
    weight_formula: str
    # Material
    material_cost: float
    material_formula: str
    # Fabrication
    manhours: float
    fabrication_cost: float
    fabrication_formula: str
    # Welding
    weld_length_m: float
    welding_manhours: float
    welding_cost: float
    welding_formula: str
    # Consumables
    consumables_cost: float
    consumables_formula: str
    # Cutting
    cutting_cost: float
    cutting_formula: str
    # Surface Treatment
    surface_area_m2: float
    surface_treatment_cost: float
    surface_formula: str
    # Totals (before overhead)
    total_direct_cost: float
    # Intermediate values for audit
    intermediate_values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostingResult:
    job_id: str
    line_items: List[LineItemCostBreakdown]
    # Aggregated totals
    total_weight_kg: float
    total_material_cost: float
    total_manhours: float
    total_fabrication_cost: float
    total_welding_manhours: float
    total_welding_cost: float
    total_consumables_cost: float
    total_cutting_cost: float
    total_surface_area_m2: float
    total_surface_treatment_cost: float
    total_direct_cost: float
    # Overhead + profit
    overhead_percentage: float
    overhead_cost: float
    profit_margin_percentage: float
    profit_amount: float
    selling_price: float
    # Audit
    audit_trail: List[Dict[str, Any]]
    rates_used: Dict[str, Any]


DEFAULT_RATES = {
    "material_rate_per_kg": 3.5,          # AED/kg
    "fabrication_rate_per_kg": 6.0,       # AED/kg (weight-based mode)
    "fabrication_hourly_rate": 45.0,      # AED/hr (manhour mode)
    "manhour_factor_hr_per_kg": 0.15,     # hr/kg (weight factor mode)
    "welding_time_per_m_hr": 0.8,         # hr/m weld
    "welding_hourly_rate": 45.0,          # AED/hr
    "consumable_factor_kg_per_m": 0.12,   # kg consumables per m of weld
    "consumable_unit_rate": 15.0,         # AED/kg consumable
    "cutting_rate_per_cut": 25.0,         # AED/cut
    "surface_treatment_rate_per_m2": 55.0, # AED/m²
    "overhead_percentage": 15.0,          # %
    "profit_margin_percentage": 12.0,     # %
    "steel_density_kg_m3": 7850.0,
    "weld_length_per_joint_mm": 150.0,    # default weld length per joint
}


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Convert value to float safely, handling strings and None."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def run_costing_engine(
    job_id: str,
    line_items: List[Dict[str, Any]],
    rates: Optional[Dict[str, float]] = None,
) -> CostingResult:
    """
    Main costing engine entry point.
    line_items: list of confirmed extracted dimension items.
    rates: rate configuration (from DB, falls back to DEFAULT_RATES).
    Returns full CostingResult with all breakdowns and audit trail.
    """
    r = {**DEFAULT_RATES, **(rates or {})}
    audit_trail = []
    item_breakdowns: List[LineItemCostBreakdown] = []

    for item in line_items:
        # Multi-key fallback for resilient data mapping
        tag = (
            item.get("item_tag") or item.get("tag") or item.get("item") or 
            f"ITEM-{len(item_breakdowns)+1}"
        )
        desc = item.get("description") or item.get("desc") or "Unknown Structural Member"
        section_type = item.get("section_type") or item.get("type") or "plate"
        
        # Helper for resilient float extraction
        def get_val(*keys, default=None):
            for k in keys:
                if item.get(k) is not None and item.get(k) != "":
                    return _safe_float(item.get(k), default)
            return default

        qty = get_val("quantity", "qty", "Q", "count", default=1.0)
        l_mm = get_val("length_mm", "length", "L", "len")
        w_mm = get_val("width_mm", "width", "W", "wid", "breadth")
        t_mm = get_val("thickness_mm", "thickness", "T", "thk", "thick")
        od_mm = get_val("od_mm", "od", "diameter", "D", "outer_diameter")
        
        logger.info(f"Processing {tag}: qty={qty}, l={l_mm}, w={w_mm}, t={t_mm}, section={section_type}")

        try:
            # ── 1. Weight ────────────────────────────────────────────────
            w_result = calculate_weight(
                section_type=section_type,
                quantity=qty,
                length_mm=l_mm,
                width_mm=w_mm,
                thickness_mm=t_mm,
                od_mm=od_mm,
                density_kg_m3=r["steel_density_kg_m3"]
            )

            # ── 2. Material Cost ─────────────────────────────────────────
            mat_result = calculate_material_cost(
                weight_kg=w_result.weight_kg,
                rate_per_kg=r["material_rate_per_kg"],
                material_grade=item.get("material_grade", "mild_steel")
            )

            # ── 3. Manhours + Fabrication Cost ──────────────────────────
            mh_result = calculate_manhours(
                mode=ManhourMode.WEIGHT_FACTOR,
                weight_kg=w_result.weight_kg,
                factor_hr_per_kg=r["manhour_factor_hr_per_kg"]
            )
            fab_result = calculate_fabrication_cost(
                mode=FabCalcMode.MANHOUR_BASED,
                manhours=mh_result.manhours,
                hourly_rate=r["fabrication_hourly_rate"],
                weight_kg=w_result.weight_kg
            )

            # ── 4. Welding ───────────────────────────────────────────────
            num_joints = int(_safe_float(item.get("weld_joints"), 0.0))
            weld_len_per_joint = _safe_float(
                item.get("weld_length_per_joint_mm"), r["weld_length_per_joint_mm"]
            )
            if num_joints > 0:
                weld_result = calculate_welding_cost(
                    num_joints=num_joints,
                    length_per_joint_mm=weld_len_per_joint,
                    time_per_m_hr=r["welding_time_per_m_hr"],
                    hourly_rate=r["welding_hourly_rate"]
                )
            else:
                from dataclasses import make_dataclass
                weld_result = type("W", (), {
                    "weld_length_m": 0.0, "welding_manhours": 0.0,
                    "welding_cost": 0.0,
                    "formula": "No weld joints specified"
                })()

            # ── 5. Consumables ───────────────────────────────────────────
            cons_result = calculate_consumables_cost(
                mode=ConsumableMode.WELD_LENGTH,
                weld_length_m=getattr(weld_result, "weld_length_m", 0.0),
                consumption_factor_kg_per_m=r["consumable_factor_kg_per_m"],
                unit_rate=r["consumable_unit_rate"]
            )

            # ── 6. Cutting ───────────────────────────────────────────────
            cut_result = calculate_cutting_cost(
                mode=CuttingMode.PER_CUT,
                num_cuts=int(qty),
                rate_per_cut=r["cutting_rate_per_cut"]
            )

            # ── 7. Surface Treatment ─────────────────────────────────────
            surface_area_m2 = _safe_float(item.get("surface_area_m2"), 0.0)
            if surface_area_m2 == 0.0:
                # Estimate from dimensions
                if section_type in ("pipe", "tube"):
                    surface_area_m2 = estimate_surface_area_pipe_m2(
                        od_mm=od_mm or 0,
                        length_mm=l_mm or 0
                    ) * qty
                else:
                    if l_mm and w_mm and t_mm:
                        surface_area_m2 = estimate_surface_area_plate_m2(l_mm, w_mm, t_mm) * qty

            surf_result = calculate_surface_treatment(
                surface_area_m2=surface_area_m2,
                rate_per_m2=r["surface_treatment_rate_per_m2"]
            )

            # ── 8. Total Direct Cost ─────────────────────────────────────
            total_direct = (
                mat_result.material_cost
                + fab_result.fabrication_cost
                + getattr(weld_result, "welding_cost", 0.0)
                + cons_result.consumables_cost
                + cut_result.cutting_cost
                + surf_result.surface_treatment_cost
            )

            breakdown = LineItemCostBreakdown(
                item_tag=tag,
                description=desc,
                section_type=section_type,
                quantity=qty,
                weight_kg=w_result.weight_kg,
                weight_formula=w_result.formula,
                material_cost=mat_result.material_cost,
                material_formula=mat_result.formula,
                manhours=mh_result.manhours,
                fabrication_cost=fab_result.fabrication_cost,
                fabrication_formula=fab_result.formula,
                weld_length_m=getattr(weld_result, "weld_length_m", 0.0),
                welding_manhours=getattr(weld_result, "welding_manhours", 0.0),
                welding_cost=getattr(weld_result, "welding_cost", 0.0),
                welding_formula=getattr(weld_result, "formula", "n/a"),
                consumables_cost=cons_result.consumables_cost,
                consumables_formula=cons_result.formula,
                cutting_cost=cut_result.cutting_cost,
                cutting_formula=cut_result.formula,
                surface_area_m2=surface_area_m2,
                surface_treatment_cost=surf_result.surface_treatment_cost,
                surface_formula=surf_result.formula,
                total_direct_cost=round(total_direct, 2),
                intermediate_values={
                    "weight": asdict(w_result) if hasattr(w_result, '__dataclass_fields__') else {},
                    "material": asdict(mat_result) if hasattr(mat_result, '__dataclass_fields__') else {},
                    "manhours": asdict(mh_result) if hasattr(mh_result, '__dataclass_fields__') else {},
                    "fabrication": asdict(fab_result) if hasattr(fab_result, '__dataclass_fields__') else {},
                }
            )
            item_breakdowns.append(breakdown)
            audit_trail.append({
                "item_tag": tag, "status": "calculated",
                "total_direct_cost": round(total_direct, 2)
            })

        except Exception as e:
            logger.error(f"Costing error for item {tag}: {e}")
            audit_trail.append({"item_tag": tag, "status": "error", "error": str(e)})

    # ── Aggregate Totals ─────────────────────────────────────────────────────
    total_weight = sum(b.weight_kg for b in item_breakdowns)
    total_material = sum(b.material_cost for b in item_breakdowns)
    total_mh = sum(b.manhours for b in item_breakdowns)
    total_fab = sum(b.fabrication_cost for b in item_breakdowns)
    total_weld_mh = sum(b.welding_manhours for b in item_breakdowns)
    total_weld_cost = sum(b.welding_cost for b in item_breakdowns)
    total_cons = sum(b.consumables_cost for b in item_breakdowns)
    total_cut = sum(b.cutting_cost for b in item_breakdowns)
    total_surf_area = sum(b.surface_area_m2 for b in item_breakdowns)
    total_surf_cost = sum(b.surface_treatment_cost for b in item_breakdowns)
    total_direct = sum(b.total_direct_cost for b in item_breakdowns)

    # ── Overhead + Margin ────────────────────────────────────────────────────
    oh_result = calculate_overhead_and_margin(
        total_direct_cost=total_direct,
        overhead_percentage=r["overhead_percentage"],
        profit_margin_percentage=r["profit_margin_percentage"]
    )

    audit_trail.append({
        "step": "overhead_and_margin",
        "overhead_formula": oh_result.formula_overhead,
        "selling_formula": oh_result.formula_selling,
    })

    return CostingResult(
        job_id=job_id,
        line_items=item_breakdowns,
        total_weight_kg=round(total_weight, 4),
        total_material_cost=round(total_material, 2),
        total_manhours=round(total_mh, 4),
        total_fabrication_cost=round(total_fab, 2),
        total_welding_manhours=round(total_weld_mh, 4),
        total_welding_cost=round(total_weld_cost, 2),
        total_consumables_cost=round(total_cons, 2),
        total_cutting_cost=round(total_cut, 2),
        total_surface_area_m2=round(total_surf_area, 4),
        total_surface_treatment_cost=round(total_surf_cost, 2),
        total_direct_cost=round(total_direct, 2),
        overhead_percentage=r["overhead_percentage"],
        overhead_cost=oh_result.overhead_cost,
        profit_margin_percentage=r["profit_margin_percentage"],
        profit_amount=oh_result.profit_amount,
        selling_price=oh_result.selling_price,
        audit_trail=audit_trail,
        rates_used=r,
    )
