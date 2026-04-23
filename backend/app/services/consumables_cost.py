"""
Consumables Cost Calculator — deterministic.
Two supported modes:
  Mode A: weld-length-based  → Consumables = Weld Length × Consumption Factor × Rate
  Mode B: percentage-based   → Consumables = % of Fabrication Cost

IMPROVED: Enhanced precision using Decimal arithmetic and comprehensive validation.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from decimal import Decimal

from app.services.precision_utils import (
    to_decimal, round_cost, calculate_percentage,
    validate_positive, to_float, format_formula_value
)


class ConsumableMode(str, Enum):
    WELD_LENGTH = "weld_length"
    PERCENTAGE = "percentage"


@dataclass
class ConsumablesCostResult:
    mode: str
    consumables_quantity: Optional[float]
    consumption_factor: Optional[float]
    unit_rate: Optional[float]
    fabrication_cost: Optional[float]
    percentage: Optional[float]
    consumables_cost: float
    formula: str
    intermediate_values: dict


def calculate_consumables_cost(
    mode: ConsumableMode,
    # Weld-length mode params
    weld_length_m: Optional[float] = None,
    consumption_factor_kg_per_m: Optional[float] = None,
    unit_rate: Optional[float] = None,
    # Percentage mode params
    fabrication_cost: Optional[float] = None,
    percentage: Optional[float] = None,
) -> ConsumablesCostResult:
    """
    Consumables cost.
    WELD_LENGTH: Qty(kg) = WeldLen(m) × Factor(kg/m); Cost = Qty × Rate/kg
    PERCENTAGE:  Cost = FabCost × (% / 100)
    
    Improved with Decimal precision and validation.
    """
    if mode == ConsumableMode.WELD_LENGTH:
        if weld_length_m is None or consumption_factor_kg_per_m is None or unit_rate is None:
            raise ValueError("WELD_LENGTH mode requires weld_length_m, consumption_factor_kg_per_m, unit_rate")
        
        # Validate inputs
        validate_positive(weld_length_m, "Weld length", allow_zero=True)
        validate_positive(consumption_factor_kg_per_m, "Consumption factor", allow_zero=False)
        validate_positive(unit_rate, "Unit rate", allow_zero=False)
        
        # Convert to Decimal
        L = to_decimal(weld_length_m)
        F = to_decimal(consumption_factor_kg_per_m)
        R = to_decimal(unit_rate)
        
        # Calculate quantity and cost
        qty = L * F
        cost = qty * R
        
        # Round to standard precision
        cost_rounded = round_cost(cost)
        
        return ConsumablesCostResult(
            mode=mode,
            consumables_quantity=to_float(qty),
            consumption_factor=to_float(F),
            unit_rate=to_float(R),
            fabrication_cost=None, percentage=None,
            consumables_cost=to_float(cost_rounded),
            formula=f"Consumables = WeldLen({format_formula_value(L, 4)}m) × Factor({format_formula_value(F, 4)}kg/m) × Rate({format_formula_value(R, 2)}) = {format_formula_value(cost_rounded, 2)}",
            intermediate_values={
                "weld_length_m": to_float(L),
                "consumption_factor_kg_per_m": to_float(F),
                "consumables_qty_kg": to_float(qty),
                "unit_rate": to_float(R),
            }
        )
    elif mode == ConsumableMode.PERCENTAGE:
        if fabrication_cost is None or percentage is None:
            raise ValueError("PERCENTAGE mode requires fabrication_cost and percentage")
        
        # Validate inputs
        validate_positive(fabrication_cost, "Fabrication cost", allow_zero=True)
        validate_positive(percentage, "Percentage", allow_zero=True)
        
        # Convert to Decimal
        F = to_decimal(fabrication_cost)
        P = to_decimal(percentage)
        
        # Calculate cost
        cost = calculate_percentage(F, P)
        
        # Round to standard precision
        cost_rounded = round_cost(cost)
        
        return ConsumablesCostResult(
            mode=mode,
            consumables_quantity=None, consumption_factor=None, unit_rate=None,
            fabrication_cost=to_float(F), percentage=to_float(P),
            consumables_cost=to_float(cost_rounded),
            formula=f"Consumables = FabCost({format_formula_value(F, 2)}) × {format_formula_value(P, 2)}% = {format_formula_value(cost_rounded, 2)}",
            intermediate_values={"fabrication_cost": to_float(F), "percentage": to_float(P)}
        )
    else:
        raise ValueError(f"Unknown ConsumableMode: {mode}")
