"""
Fabrication Cost & Manhours Calculator — deterministic.
Two supported modes:
  Mode A: weight-based   → Fabrication Cost = Weight × Rate/kg
  Mode B: manhour-based  → Fabrication Cost = Manhours × Hourly Rate
Manhours two modes:
  Mode 1: Manhours = Weight × Factor (hr/kg)
  Mode 2: Manhours = Quantity × Time per Unit (hr/unit)
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class FabCalcMode(str, Enum):
    WEIGHT_BASED = "weight_based"
    MANHOUR_BASED = "manhour_based"


class ManhourMode(str, Enum):
    WEIGHT_FACTOR = "weight_factor"
    QTY_TIME = "qty_time"


@dataclass
class ManhourResult:
    manhours: float
    mode: str
    formula: str
    intermediate_values: dict


@dataclass
class FabricationCostResult:
    manhours: Optional[float]
    manhour_rate: Optional[float]
    weight_kg: Optional[float]
    rate_per_kg: Optional[float]
    fabrication_cost: float
    mode: str
    formula: str
    intermediate_values: dict


def calculate_manhours(
    mode: ManhourMode,
    weight_kg: Optional[float] = None,
    factor_hr_per_kg: Optional[float] = None,
    quantity: Optional[float] = None,
    time_per_unit_hr: Optional[float] = None,
) -> ManhourResult:
    """
    Manhours calculation:
    Mode WEIGHT_FACTOR: Manhours = Weight × Factor
    Mode QTY_TIME:      Manhours = Quantity × Time per Unit
    """
    if mode == ManhourMode.WEIGHT_FACTOR:
        if weight_kg is None or factor_hr_per_kg is None:
            raise ValueError("WEIGHT_FACTOR mode requires weight_kg and factor_hr_per_kg")
        mh = weight_kg * factor_hr_per_kg
        return ManhourResult(
            manhours=round(mh, 4),
            mode=mode,
            formula=f"Manhours = Weight({weight_kg:.4f} kg) × Factor({factor_hr_per_kg} hr/kg) = {mh:.4f} hr",
            intermediate_values={"weight_kg": weight_kg, "factor_hr_per_kg": factor_hr_per_kg}
        )
    elif mode == ManhourMode.QTY_TIME:
        if quantity is None or time_per_unit_hr is None:
            raise ValueError("QTY_TIME mode requires quantity and time_per_unit_hr")
        mh = quantity * time_per_unit_hr
        return ManhourResult(
            manhours=round(mh, 4),
            mode=mode,
            formula=f"Manhours = Qty({quantity}) × Time/Unit({time_per_unit_hr} hr) = {mh:.4f} hr",
            intermediate_values={"quantity": quantity, "time_per_unit_hr": time_per_unit_hr}
        )
    else:
        raise ValueError(f"Unknown ManhourMode: {mode}")


def calculate_fabrication_cost(
    mode: FabCalcMode,
    # Weight-based params
    weight_kg: Optional[float] = None,
    rate_per_kg: Optional[float] = None,
    # Manhour-based params
    manhours: Optional[float] = None,
    hourly_rate: Optional[float] = None,
) -> FabricationCostResult:
    """
    Fabrication cost calculation.
    Mode WEIGHT_BASED:  Cost = Weight × Rate/kg
    Mode MANHOUR_BASED: Cost = Manhours × Hourly Rate
    """
    if mode == FabCalcMode.WEIGHT_BASED:
        if weight_kg is None or rate_per_kg is None:
            raise ValueError("WEIGHT_BASED mode requires weight_kg and rate_per_kg")
        cost = weight_kg * rate_per_kg
        return FabricationCostResult(
            manhours=None, manhour_rate=None,
            weight_kg=weight_kg, rate_per_kg=rate_per_kg,
            fabrication_cost=round(cost, 2),
            mode=mode,
            formula=f"Fab Cost = Weight({weight_kg:.4f} kg) × Rate({rate_per_kg}/kg) = {cost:.2f}",
            intermediate_values={"weight_kg": weight_kg, "rate_per_kg": rate_per_kg}
        )
    elif mode == FabCalcMode.MANHOUR_BASED:
        if manhours is None or hourly_rate is None:
            raise ValueError("MANHOUR_BASED mode requires manhours and hourly_rate")
        cost = manhours * hourly_rate
        return FabricationCostResult(
            manhours=manhours, manhour_rate=hourly_rate,
            weight_kg=weight_kg, rate_per_kg=None,
            fabrication_cost=round(cost, 2),
            mode=mode,
            formula=f"Fab Cost = Manhours({manhours:.4f} hr) × Rate({hourly_rate}/hr) = {cost:.2f}",
            intermediate_values={"manhours": manhours, "hourly_rate": hourly_rate}
        )
    else:
        raise ValueError(f"Unknown FabCalcMode: {mode}")
