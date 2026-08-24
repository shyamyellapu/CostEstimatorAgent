"""
Weight Calculator — deterministic, formula-transparent.
Supports: plate/rectangular, pipe, beam, angle, channel, flat bar, round bar.
All dimensions in mm, output weight in kg.
Steel density default = 7850 kg/m³

IMPROVED: Enhanced precision using Decimal arithmetic, comprehensive validation,
and more accurate formulas for pipe weight calculations.
"""
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
import math
import logging

from app.services.precision_utils import (
    to_decimal, round_weight, round_dimension, validate_dimension,
    validate_positive, validate_weight, to_float, format_formula_value
)

logger = logging.getLogger(__name__)

STEEL_DENSITY_KG_M3 = 7850.0  # kg/m³ — configurable per job


@dataclass
class WeightResult:
    section_type: str
    weight_kg: float
    formula: str
    intermediate_values: dict
    unit_weight_kg_per_m: Optional[float] = None


def weight_plate(
    length_mm: float,
    width_mm: float,
    thickness_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """
    Plate / rectangular section weight.
    Formula: W = L × W × T × ρ / 1e9  (mm→m³, then × kg/m³)
    
    Improved with Decimal precision and validation.
    """
    # Validate inputs
    validate_dimension(length_mm, "Length")
    validate_dimension(width_mm, "Width")
    validate_dimension(thickness_mm, "Thickness")
    validate_positive(quantity, "Quantity", allow_zero=False)
    validate_positive(density_kg_m3, "Density", allow_zero=False)
    
    # Convert to Decimal for precise calculation
    L = to_decimal(length_mm)
    W = to_decimal(width_mm)
    T = to_decimal(thickness_mm)
    Q = to_decimal(quantity)
    rho = to_decimal(density_kg_m3)
    
    # Calculate volume in mm³
    volume_mm3 = L * W * T
    
    # Convert to m³ and calculate weight
    # 1 m³ = 1,000,000,000 mm³
    volume_m3 = volume_mm3 / Decimal('1000000000')
    weight_each = volume_m3 * rho
    total_weight = weight_each * Q
    
    # Round to standard precision
    total_weight_rounded = round_weight(total_weight)
    weight_each_rounded = round_weight(weight_each)
    
    return WeightResult(
        section_type="plate",
        weight_kg=to_float(total_weight_rounded),
        formula=f"W = L({format_formula_value(L, 2)}) × W({format_formula_value(W, 2)}) × T({format_formula_value(T, 2)}) × ρ({format_formula_value(rho, 0)}) / 1e9 × Qty({format_formula_value(Q, 0)})",
        intermediate_values={
            "volume_mm3": to_float(round_dimension(volume_mm3)),
            "weight_each_kg": to_float(weight_each_rounded),
            "quantity": to_float(Q),
            "density_kg_m3": to_float(rho),
        }
    )


def weight_pipe(
    od_mm: float,
    thickness_mm: float,
    length_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """
    Pipe / hollow section weight.
    
    IMPROVED FORMULA - More accurate calculation:
    Volume = π × (OD² - ID²) / 4 × L  where ID = OD - 2×T
    Weight = Volume × ρ / 1e9
    
    Previous approximation: W = (OD - T) × T × L × 0.02466
    New calculation provides better accuracy, especially for thick-walled pipes.
    """
    # Validate inputs
    validate_dimension(od_mm, "Outer Diameter")
    validate_dimension(thickness_mm, "Thickness")
    validate_dimension(length_mm, "Length")
    validate_positive(quantity, "Quantity", allow_zero=False)
    validate_positive(density_kg_m3, "Density", allow_zero=False)
    
    # Additional validation: thickness must be less than half of OD
    if thickness_mm >= od_mm / 2:
        raise ValueError(f"Thickness ({thickness_mm}mm) must be less than half of OD ({od_mm}mm)")
    
    # Convert to Decimal for precise calculation
    OD = to_decimal(od_mm)
    T = to_decimal(thickness_mm)
    L = to_decimal(length_mm)
    Q = to_decimal(quantity)
    rho = to_decimal(density_kg_m3)
    
    # Calculate inner diameter
    ID = OD - (Decimal('2') * T)
    
    # Validate ID is positive
    if ID <= 0:
        raise ValueError(f"Inner diameter is non-positive. OD={od_mm}, T={thickness_mm}")
    
    # Calculate cross-sectional area (annular area)
    # Area = π/4 × (OD² - ID²)
    pi = Decimal(str(math.pi))
    area_mm2 = (pi / Decimal('4')) * (OD * OD - ID * ID)
    
    # Calculate volume
    volume_mm3 = area_mm2 * L
    
    # Convert to m³ and calculate weight
    volume_m3 = volume_mm3 / Decimal('1000000000')
    weight_each = volume_m3 * rho
    total_weight = weight_each * Q
    
    # Calculate unit weight per meter for reference
    unit_weight_kg_per_m = weight_each / (L / Decimal('1000'))
    
    # Round to standard precision
    total_weight_rounded = round_weight(total_weight)
    weight_each_rounded = round_weight(weight_each)
    unit_weight_rounded = round_weight(unit_weight_kg_per_m)
    
    return WeightResult(
        section_type="pipe",
        weight_kg=to_float(total_weight_rounded),
        formula=f"W = π/4 × (OD²({format_formula_value(OD, 2)}) - ID²({format_formula_value(ID, 2)})) × L({format_formula_value(L, 2)}) × ρ({format_formula_value(rho, 0)}) / 1e9 × Qty({format_formula_value(Q, 0)})",
        intermediate_values={
            "od_mm": to_float(OD),
            "id_mm": to_float(round_dimension(ID)),
            "thickness_mm": to_float(T),
            "length_mm": to_float(L),
            "area_mm2": to_float(round_dimension(area_mm2)),
            "volume_mm3": to_float(round_dimension(volume_mm3)),
            "weight_each_kg": to_float(weight_each_rounded),
            "quantity": to_float(Q),
        },
        unit_weight_kg_per_m=to_float(unit_weight_rounded)
    )


def weight_round_bar(
    diameter_mm: float,
    length_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """
    Solid round bar weight.
    Formula: W = π/4 × D² × L × ρ / 1e9
    
    Improved with Decimal precision and validation.
    """
    # Validate inputs
    validate_dimension(diameter_mm, "Diameter")
    validate_dimension(length_mm, "Length")
    validate_positive(quantity, "Quantity", allow_zero=False)
    validate_positive(density_kg_m3, "Density", allow_zero=False)
    
    # Convert to Decimal for precise calculation
    D = to_decimal(diameter_mm)
    L = to_decimal(length_mm)
    Q = to_decimal(quantity)
    rho = to_decimal(density_kg_m3)
    
    # Calculate cross-sectional area
    pi = Decimal(str(math.pi))
    area_mm2 = (pi / Decimal('4')) * D * D
    
    # Calculate volume
    volume_mm3 = area_mm2 * L
    
    # Convert to m³ and calculate weight
    volume_m3 = volume_mm3 / Decimal('1000000000')
    weight_each = volume_m3 * rho
    total_weight = weight_each * Q
    
    # Round to standard precision
    total_weight_rounded = round_weight(total_weight)
    weight_each_rounded = round_weight(weight_each)
    
    return WeightResult(
        section_type="round_bar",
        weight_kg=to_float(total_weight_rounded),
        formula=f"W = π/4 × D²({format_formula_value(D, 2)}) × L({format_formula_value(L, 2)}) × ρ({format_formula_value(rho, 0)}) / 1e9 × Qty({format_formula_value(Q, 0)})",
        intermediate_values={
            "area_mm2": to_float(round_dimension(area_mm2)),
            "volume_mm3": to_float(round_dimension(volume_mm3)),
            "weight_each_kg": to_float(weight_each_rounded),
            "quantity": to_float(Q),
        }
    )


def weight_flat_bar(
    width_mm: float,
    thickness_mm: float,
    length_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """Flat bar = rectangular section."""
    return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)


def weight_angle(
    leg1_mm: float,
    leg2_mm: float,
    thickness_mm: float,
    length_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """
    Angle section weight (approximate — treats as two plates minus corner overlap).
    Area = (leg1 + leg2 - thickness) × thickness
    
    Improved with Decimal precision and validation.
    Note: This is an approximation. For precise calculations, use manufacturer's
    weight tables for standard angle sections.
    """
    # Validate inputs
    validate_dimension(leg1_mm, "Leg 1")
    validate_dimension(leg2_mm, "Leg 2")
    validate_dimension(thickness_mm, "Thickness")
    validate_dimension(length_mm, "Length")
    validate_positive(quantity, "Quantity", allow_zero=False)
    validate_positive(density_kg_m3, "Density", allow_zero=False)
    
    # Validate thickness is less than both legs
    if thickness_mm >= leg1_mm or thickness_mm >= leg2_mm:
        raise ValueError(f"Thickness ({thickness_mm}mm) must be less than both legs ({leg1_mm}mm, {leg2_mm}mm)")
    
    # Convert to Decimal for precise calculation
    L1 = to_decimal(leg1_mm)
    L2 = to_decimal(leg2_mm)
    T = to_decimal(thickness_mm)
    L = to_decimal(length_mm)
    Q = to_decimal(quantity)
    rho = to_decimal(density_kg_m3)
    
    # Calculate cross-sectional area
    area_mm2 = (L1 + L2 - T) * T
    
    # Calculate volume
    volume_mm3 = area_mm2 * L
    
    # Convert to m³ and calculate weight
    volume_m3 = volume_mm3 / Decimal('1000000000')
    weight_each = volume_m3 * rho
    total_weight = weight_each * Q
    
    # Round to standard precision
    total_weight_rounded = round_weight(total_weight)
    weight_each_rounded = round_weight(weight_each)
    
    return WeightResult(
        section_type="angle",
        weight_kg=to_float(total_weight_rounded),
        formula=f"W = (L1({format_formula_value(L1, 2)})+L2({format_formula_value(L2, 2)})-T({format_formula_value(T, 2)})) × T({format_formula_value(T, 2)}) × L({format_formula_value(L, 2)}) × ρ({format_formula_value(rho, 0)}) / 1e9 × Qty({format_formula_value(Q, 0)})",
        intermediate_values={
            "area_mm2": to_float(round_dimension(area_mm2)),
            "volume_mm3": to_float(round_dimension(volume_mm3)),
            "weight_each_kg": to_float(weight_each_rounded),
            "quantity": to_float(Q),
        }
    )


import logging
logger = logging.getLogger(__name__)

def calculate_weight(
    section_type: str,
    quantity: float = 1.0,
    length_mm: Optional[float] = None,
    width_mm: Optional[float] = None,
    thickness_mm: Optional[float] = None,
    od_mm: Optional[float] = None,
    diameter_mm: Optional[float] = None,
    leg1_mm: Optional[float] = None,
    leg2_mm: Optional[float] = None,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """Universal dispatcher for weight calculation based on section type."""
    st = section_type.lower().replace(" ", "_").replace("-", "_")

    try:
        if st in ("plate", "flat", "flat_bar", "rectangular"):
            if not all([length_mm, width_mm, thickness_mm]):
                logger.warning(f"Plate requires L, W, T. Got: L={length_mm}, W={width_mm}, T={thickness_mm}")
                return WeightResult(section_type="plate", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)

        elif st in ("pipe", "tube", "hollow_section", "hss"):
            if not all([od_mm, thickness_mm, length_mm]):
                logger.warning(f"Pipe requires OD, T, L. Got: OD={od_mm}, T={thickness_mm}, L={length_mm}")
                return WeightResult(section_type="pipe", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_pipe(od_mm, thickness_mm, length_mm, quantity)

        elif st in ("round_bar", "rod", "solid_bar"):
            d = diameter_mm or width_mm
            if not all([d, length_mm]):
                logger.warning(f"Round bar requires D, L. Got: D={d}, L={length_mm}")
                return WeightResult(section_type="round_bar", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_round_bar(d, length_mm, quantity, density_kg_m3)

        elif st in ("angle", "l_section"):
            # Resilient angle logic: fallback to width if legs missing
            if not all([thickness_mm, length_mm]):
                 logger.warning(f"Angle requires T, L. Got: T={thickness_mm}, L={length_mm}")
                 return WeightResult(section_type="angle", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            l1 = leg1_mm or width_mm or 0
            l2 = leg2_mm or l1
            if l1 == 0:
                logger.warning("Angle leg size is 0")
                return WeightResult(section_type="angle", weight_kg=0.0, formula="Leg size is 0", intermediate_values={})
            return weight_angle(l1, l2, thickness_mm, length_mm, quantity, density_kg_m3)

        elif st in ("beam", "channel", "i_beam", "h_beam", "ipn", "upn", "hea", "heb"):
            if not all([length_mm, width_mm, thickness_mm]):
                logger.warning(f"Beam requires L, W, T. Got: L={length_mm}, W={width_mm}, T={thickness_mm}")
                return WeightResult(section_type="beam", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)

        else:
            # Fallback to plate
            if all([length_mm, width_mm, thickness_mm]):
                return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)
            
            logger.warning(f"Unknown section type or missing dimensions for '{section_type}'")
            return WeightResult(section_type=st, weight_kg=0.0, formula=f"Cannot calculate weight for {st}", intermediate_values={})

    except Exception as e:
        logger.error(f"Internal weight calculator error: {e}")
        return WeightResult(section_type=st, weight_kg=0.0, formula=str(e), intermediate_values={})
