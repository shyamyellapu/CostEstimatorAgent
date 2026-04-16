"""
Consumables Cost Calculator — deterministic.
Two supported modes:
  Mode A: weld-length-based  → Consumables = Weld Length × Consumption Factor × Rate
  Mode B: percentage-based   → Consumables = % of Fabrication Cost
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


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
    """
    if mode == ConsumableMode.WELD_LENGTH:
        if weld_length_m is None or consumption_factor_kg_per_m is None or unit_rate is None:
            raise ValueError("WELD_LENGTH mode requires weld_length_m, consumption_factor_kg_per_m, unit_rate")
        qty = weld_length_m * consumption_factor_kg_per_m
        cost = qty * unit_rate
        return ConsumablesCostResult(
            mode=mode,
            consumables_quantity=round(qty, 4),
            consumption_factor=consumption_factor_kg_per_m,
            unit_rate=unit_rate,
            fabrication_cost=None, percentage=None,
            consumables_cost=round(cost, 2),
            formula=f"Consumables = WeldLen({weld_length_m}m) × Factor({consumption_factor_kg_per_m}kg/m) × Rate({unit_rate}) = {cost:.2f}",
            intermediate_values={
                "weld_length_m": weld_length_m,
                "consumption_factor_kg_per_m": consumption_factor_kg_per_m,
                "consumables_qty_kg": round(qty, 4),
                "unit_rate": unit_rate,
            }
        )
    elif mode == ConsumableMode.PERCENTAGE:
        if fabrication_cost is None or percentage is None:
            raise ValueError("PERCENTAGE mode requires fabrication_cost and percentage")
        cost = fabrication_cost * (percentage / 100.0)
        return ConsumablesCostResult(
            mode=mode,
            consumables_quantity=None, consumption_factor=None, unit_rate=None,
            fabrication_cost=fabrication_cost, percentage=percentage,
            consumables_cost=round(cost, 2),
            formula=f"Consumables = FabCost({fabrication_cost:.2f}) × {percentage}% = {cost:.2f}",
            intermediate_values={"fabrication_cost": fabrication_cost, "percentage": percentage}
        )
    else:
        raise ValueError(f"Unknown ConsumableMode: {mode}")
