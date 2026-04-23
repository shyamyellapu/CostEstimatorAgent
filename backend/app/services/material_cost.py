"""
Material Cost Calculator — deterministic.
Formula: Material Cost = Weight (kg) × Rate per kg

IMPROVED: Enhanced precision using Decimal arithmetic and comprehensive validation.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.services.precision_utils import (
    to_decimal, round_cost, round_weight, validate_weight,
    validate_positive, to_float, format_formula_value
)


@dataclass
class MaterialCostResult:
    weight_kg: float
    rate_per_kg: float
    material_cost: float
    formula: str
    intermediate_values: dict


def calculate_material_cost(
    weight_kg: float,
    rate_per_kg: float,
    material_grade: str = "mild_steel",
) -> MaterialCostResult:
    """
    Calculate material cost.
    Formula: Material Cost = Weight × Rate/kg
    
    Improved with Decimal precision and enhanced validation.
    """
    # Validate inputs
    validate_weight(weight_kg, allow_zero=True)
    validate_positive(rate_per_kg, "Rate per kg", allow_zero=False)
    
    # Convert to Decimal for precise calculation
    W = to_decimal(weight_kg)
    R = to_decimal(rate_per_kg)
    
    # Calculate cost
    cost = W * R
    
    # Round to standard precision
    cost_rounded = round_cost(cost)
    weight_rounded = round_weight(W)
    
    return MaterialCostResult(
        weight_kg=to_float(weight_rounded),
        rate_per_kg=to_float(R),
        material_cost=to_float(cost_rounded),
        formula=f"Material Cost = Weight({format_formula_value(W, 4)} kg) × Rate({format_formula_value(R, 2)}/kg) = {format_formula_value(cost, 2)}",
        intermediate_values={
            "weight_kg": to_float(weight_rounded),
            "rate_per_kg": to_float(R),
            "material_grade": material_grade,
        }
    )
