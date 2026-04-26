"""
Surface Treatment Cost Calculator — deterministic.
Formula: Cost = Surface Area (m²) × Rate per m²
Surface area must be provided or estimated from item dimensions.

IMPROVED: Enhanced precision using Decimal arithmetic and comprehensive validation.
"""
from dataclasses import dataclass
from decimal import Decimal
import math

from app.services.precision_utils import (
    to_decimal, round_cost, round_area, round_dimension,
    validate_positive, to_float, format_formula_value
)


@dataclass
class SurfaceTreatmentResult:
    surface_area_m2: float
    rate_per_m2: float
    treatment_type: str
    surface_treatment_cost: float
    formula: str
    intermediate_values: dict


def estimate_surface_area_plate_m2(
    length_mm: float,
    width_mm: float,
    thickness_mm: float,
    include_edges: bool = True
) -> float:
    """Estimate surface area of a plate including both faces and edges.
    
    Improved with Decimal precision.
    """
    # Convert to Decimal
    L = to_decimal(length_mm)
    W = to_decimal(width_mm)
    T = to_decimal(thickness_mm)
    
    # Calculate face area (both sides)
    face_area = Decimal('2') * (L * W)
    
    # Calculate edge area if requested
    if include_edges:
        edge_area = Decimal('2') * (L * T) + Decimal('2') * (W * T)
    else:
        edge_area = Decimal('0')
    
    # Total area in mm²
    total_area_mm2 = face_area + edge_area
    
    # Convert to m²
    area_m2 = total_area_mm2 / Decimal('1000000')
    
    return to_float(round_area(area_m2))


def estimate_surface_area_pipe_m2(
    od_mm: float,
    length_mm: float
) -> float:
    """Estimate outer surface area of a pipe.
    
    Improved with Decimal precision.
    """
    # Convert to Decimal
    OD = to_decimal(od_mm)
    L = to_decimal(length_mm)
    pi = Decimal(str(math.pi))
    
    # Calculate outer surface area
    area_mm2 = pi * OD * L
    
    # Convert to m²
    area_m2 = area_mm2 / Decimal('1000000')
    
    return to_float(round_area(area_m2))


def estimate_surface_area_from_weight(
    steel_weight_kg: float,
    factor_m2_per_kg: float = 0.0256
) -> float:
    """Estimate paintable surface area from steel weight using empirical factor.
    
    Default factor 0.0256 m²/kg derived from CNJ/142676 reference job.
    This accounts for typical structural steel cross-sections with partial exposure.
    
    Args:
        steel_weight_kg: Total structural steel weight
        factor_m2_per_kg: Conversion factor (default 0.0256 from reference job)
        
    Returns:
        Surface area in m²
    """
    W = to_decimal(steel_weight_kg)
    F = to_decimal(factor_m2_per_kg)
    
    area_m2 = W * F
    return to_float(round_area(area_m2))


def calculate_surface_treatment(
    surface_area_m2: float,
    rate_per_m2: float,
    treatment_type: str = "blast_and_prime",
) -> SurfaceTreatmentResult:
    """
    Surface treatment cost.
    Formula: Cost = Area (m²) × Rate/m²
    
    Improved with Decimal precision and validation.
    """
    # Validate inputs
    validate_positive(surface_area_m2, "Surface area", allow_zero=True)
    validate_positive(rate_per_m2, "Rate per m²", allow_zero=False)
    
    # Convert to Decimal
    A = to_decimal(surface_area_m2)
    R = to_decimal(rate_per_m2)
    
    # Calculate cost
    cost = A * R
    
    # Round to standard precision
    area_rounded = round_area(A)
    cost_rounded = round_cost(cost)
    
    return SurfaceTreatmentResult(
        surface_area_m2=to_float(area_rounded),
        rate_per_m2=to_float(R),
        treatment_type=treatment_type,
        surface_treatment_cost=to_float(cost_rounded),
        formula=f"Surface Treatment({treatment_type}) = Area({format_formula_value(area_rounded, 4)}m²) × Rate({format_formula_value(R, 2)}/m²) = {format_formula_value(cost_rounded, 2)}",
        intermediate_values={
            "surface_area_m2": to_float(area_rounded),
            "rate_per_m2": to_float(R),
            "treatment_type": treatment_type,
        }
    )
