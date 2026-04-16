"""
Material Cost Calculator — deterministic.
Formula: Material Cost = Weight (kg) × Rate per kg
"""
from dataclasses import dataclass


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
    """
    if weight_kg < 0:
        raise ValueError(f"Weight must be non-negative, got {weight_kg}")
    if rate_per_kg < 0:
        raise ValueError(f"Rate must be non-negative, got {rate_per_kg}")

    cost = weight_kg * rate_per_kg

    return MaterialCostResult(
        weight_kg=round(weight_kg, 4),
        rate_per_kg=rate_per_kg,
        material_cost=round(cost, 2),
        formula=f"Material Cost = Weight({weight_kg:.4f} kg) × Rate({rate_per_kg}/kg) = {cost:.2f}",
        intermediate_values={
            "weight_kg": weight_kg,
            "rate_per_kg": rate_per_kg,
            "material_grade": material_grade,
        }
    )
