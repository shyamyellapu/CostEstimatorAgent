"""
Enhanced Costing Calculation Utilities
======================================

Improved costing helpers that use:
1. C&J master rate configuration
2. Weight-based labour formulas
3. Empirical surface area calculation
4. Steel section validation

Based on: JobCosting_Accuracy_Report recommendations
"""
from typing import Dict, Optional
from decimal import Decimal
import logging

from app.services.steel_section_reference import (
    validate_weight, calculate_weight_from_section, get_section_unit_weight
)
from app.services.surface_treatment import estimate_surface_area_from_weight
from app.services.fabrication_cost import calculate_manhours, ManhourMode
from app.services.master_rates import get_rate_by_key

logger = logging.getLogger(__name__)


def calculate_labour_costs_from_weight(
    steel_weight_kg: float,
    rates: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """Calculate all labour costs from steel weight using C&J formulas.
    
    Formulas from CNJ/142676:
    - Welding: 0.35 hr/kg
    - Fabrication: 0.28 hr/kg
    - Fitting: 0.18 hr/kg
    - Grinding: 0.07 hr/kg
    
    Args:
        steel_weight_kg: Total structural steel weight
        rates: Optional rate overrides (defaults to master rates)
        
    Returns:
        Dict with manhours and costs for each labour category
    """
    try:
        # Get rates
        if rates is None:
            welding_factor = get_rate_by_key("welding_manhours_per_kg")
            fab_factor = get_rate_by_key("fabrication_manhours_per_kg")
            fitting_factor = get_rate_by_key("fitting_manhours_per_kg")
            grinding_factor = get_rate_by_key("grinding_manhours_per_kg")
            hourly_rate = get_rate_by_key("labour_hourly_rate_aed")
        else:
            welding_factor = rates.get("welding_manhours_per_kg", 0.35)
            fab_factor = rates.get("fabrication_manhours_per_kg", 0.28)
            fitting_factor = rates.get("fitting_manhours_per_kg", 0.18)
            grinding_factor = rates.get("grinding_manhours_per_kg", 0.07)
            hourly_rate = rates.get("labour_hourly_rate_aed", 35.0)
        
        # Calculate manhours
        welding_hrs = steel_weight_kg * welding_factor
        fab_hrs = steel_weight_kg * fab_factor
        fitting_hrs = steel_weight_kg * fitting_factor
        grinding_hrs = steel_weight_kg * grinding_factor
        total_hrs = welding_hrs + fab_hrs + fitting_hrs + grinding_hrs
        
        # Calculate costs
        welding_cost = welding_hrs * hourly_rate
        fab_cost = fab_hrs * hourly_rate
        fitting_cost = fitting_hrs * hourly_rate
        grinding_cost = grinding_hrs * hourly_rate
        total_cost = welding_cost + fab_cost + fitting_cost + grinding_cost
        
        return {
            "welding_manhours": round(welding_hrs, 2),
            "welding_cost_aed": round(welding_cost, 2),
            "fabrication_manhours": round(fab_hrs, 2),
            "fabrication_cost_aed": round(fab_cost, 2),
            "fitting_manhours": round(fitting_hrs, 2),
            "fitting_cost_aed": round(fitting_cost, 2),
            "grinding_manhours": round(grinding_hrs, 2),
            "grinding_cost_aed": round(grinding_cost, 2),
            "total_manhours": round(total_hrs, 2),
            "total_labour_cost_aed": round(total_cost, 2),
            "formulas": {
                "welding": f"{welding_hrs:.2f} = {steel_weight_kg:.2f} kg × {welding_factor} hr/kg",
                "fabrication": f"{fab_hrs:.2f} = {steel_weight_kg:.2f} kg × {fab_factor} hr/kg",
                "fitting": f"{fitting_hrs:.2f} = {steel_weight_kg:.2f} kg × {fitting_factor} hr/kg",
                "grinding": f"{grinding_hrs:.2f} = {steel_weight_kg:.2f} kg × {grinding_factor} hr/kg"
            }
        }
    except KeyError as e:
        logger.error(f"Missing rate configuration: {e}")
        raise ValueError(f"Required rate not found: {e}. Run seed_master_rates.py first.")


def calculate_surface_treatment_from_weight(
    steel_weight_kg: float,
    rates: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """Calculate surface treatment costs from steel weight.
    
    Uses empirical factor: 0.0256 m²/kg (from CNJ/142676)
    
    Args:
        steel_weight_kg: Total structural steel weight
        rates: Optional rate overrides
        
    Returns:
        Dict with surface area and treatment costs
    """
    try:
        # Get rates
        if rates is None:
            area_factor = get_rate_by_key("surface_area_factor_m2_per_kg")
            blasting_rate = get_rate_by_key("blasting_sa25_aed_per_m2")
            painting_rate = get_rate_by_key("painting_aed_per_m2")
        else:
            area_factor = rates.get("surface_area_factor_m2_per_kg", 0.0256)
            blasting_rate = rates.get("blasting_sa25_aed_per_m2", 12.0)
            painting_rate = rates.get("painting_aed_per_m2", 18.0)
        
        # Calculate surface area
        surface_area_m2 = estimate_surface_area_from_weight(steel_weight_kg, area_factor)
        
        # Calculate costs
        blasting_cost = surface_area_m2 * blasting_rate
        painting_cost = surface_area_m2 * painting_rate
        total_cost = blasting_cost + painting_cost
        
        return {
            "surface_area_m2": round(surface_area_m2, 2),
            "blasting_cost_aed": round(blasting_cost, 2),
            "painting_cost_aed": round(painting_cost, 2),
            "total_surface_treatment_cost_aed": round(total_cost, 2),
            "formulas": {
                "area": f"{surface_area_m2:.2f} m² = {steel_weight_kg:.2f} kg × {area_factor} m²/kg",
                "blasting": f"{blasting_cost:.2f} = {surface_area_m2:.2f} m² × {blasting_rate:.2f} AED/m²",
                "painting": f"{painting_cost:.2f} = {surface_area_m2:.2f} m² × {painting_rate:.2f} AED/m²"
            }
        }
    except KeyError as e:
        logger.error(f"Missing rate configuration: {e}")
        raise ValueError(f"Required rate not found: {e}. Run seed_master_rates.py first.")


def calculate_consumables_from_weight(
    steel_weight_kg: float,
    material_rate_per_kg: float,
    rates: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """Calculate consumables cost as percentage of steel material cost.
    
    Formula from CNJ/142676: 3.5% of (steel_weight × material_rate)
    
    Args:
        steel_weight_kg: Total structural steel weight
        material_rate_per_kg: Steel material rate in AED/kg
        rates: Optional rate overrides
        
    Returns:
        Dict with consumables cost
    """
    try:
        # Get rate
        if rates is None:
            consumables_pct = get_rate_by_key("consumables_percentage_of_steel")
        else:
            consumables_pct = rates.get("consumables_percentage_of_steel", 3.5)
        
        # Calculate
        material_cost = steel_weight_kg * material_rate_per_kg
        consumables_cost = material_cost * (consumables_pct / 100.0)
        
        return {
            "consumables_cost_aed": round(consumables_cost, 2),
            "formula": (
                f"{consumables_cost:.2f} = "
                f"({steel_weight_kg:.2f} kg × {material_rate_per_kg:.2f} AED/kg) × "
                f"{consumables_pct}%"
            )
        }
    except KeyError as e:
        logger.error(f"Missing rate configuration: {e}")
        raise ValueError(f"Required rate not found: {e}. Run seed_master_rates.py first.")


def validate_and_correct_weights(
    structural_elements: list,
    auto_correct: bool = False
) -> tuple[list, list]:
    """Validate weights against section tables and optionally correct them.
    
    Args:
        structural_elements: List of extracted structural elements
        auto_correct: If True, replace invalid weights with calculated values
        
    Returns:
        Tuple of (corrected_elements, validation_warnings)
    """
    warnings = []
    corrected_elements = []
    
    for elem in structural_elements:
        section = elem.get("section_designation", "") or elem.get("section", "")
        length_mm = elem.get("length_mm", 0) or elem.get("l_mm", 0)
        quantity = elem.get("quantity", 1) or elem.get("qty", 1)
        current_weight = elem.get("total_weight_kg", 0) or elem.get("weight_kg", 0)
        
        if not section or not length_mm:
            corrected_elements.append(elem)
            continue
        
        # Validate weight
        is_valid, warning, expected_weight = validate_weight(
            current_weight, section, length_mm, quantity, tolerance_percent=20.0
        )
        
        if not is_valid and warning:
            tag = elem.get("support_tag", "") or elem.get("tag", "Unknown")
            warnings.append(f"Tag {tag}: {warning}")
            
            if auto_correct and expected_weight is not None:
                elem_copy = elem.copy()
                elem_copy["total_weight_kg"] = round(expected_weight, 2)
                elem_copy["weight_corrected"] = True
                elem_copy["original_weight_kg"] = current_weight
                corrected_elements.append(elem_copy)
                warnings.append(f"  → Auto-corrected to {expected_weight:.2f} kg")
            else:
                corrected_elements.append(elem)
        else:
            corrected_elements.append(elem)
    
    return corrected_elements, warnings


def calculate_paint_material_from_area(
    surface_area_m2: float,
    rates: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """Calculate paint material requirement from surface area.
    
    Args:
        surface_area_m2: Total paintable surface area
        rates: Optional rate overrides
        
    Returns:
        Dict with paint litres and cost
    """
    try:
        # Get rates
        if rates is None:
            coverage_factor = get_rate_by_key("paint_coverage_factor_m2_per_litre")
            paint_rate = get_rate_by_key("paint_2pack_epoxy_aed_per_litre")
        else:
            coverage_factor = rates.get("paint_coverage_factor_m2_per_litre", 6.67)
            paint_rate = rates.get("paint_2pack_epoxy_aed_per_litre", 85.0)
        
        # Calculate
        paint_litres = surface_area_m2 / coverage_factor
        paint_cost = paint_litres * paint_rate
        
        return {
            "paint_litres": round(paint_litres, 2),
            "paint_cost_aed": round(paint_cost, 2),
            "formula": (
                f"{paint_litres:.2f} litres = {surface_area_m2:.2f} m² / {coverage_factor:.2f} m²/litre; "
                f"Cost = {paint_litres:.2f} × {paint_rate:.2f} AED/litre"
            )
        }
    except KeyError as e:
        logger.error(f"Missing rate configuration: {e}")
        raise ValueError(f"Required rate not found: {e}. Run seed_master_rates.py first.")
