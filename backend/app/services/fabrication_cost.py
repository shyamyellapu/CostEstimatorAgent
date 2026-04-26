"""
Fabrication Cost & Manhours Calculator — deterministic.
Two supported modes:
  Mode A: weight-based   → Fabrication Cost = Weight × Rate/kg
  Mode B: manhour-based  → Fabrication Cost = Manhours × Hourly Rate
Manhours two modes:
  Mode 1: Manhours = Weight × Factor (hr/kg)
  Mode 2: Manhours = Quantity × Time per Unit (hr/unit)

IMPROVED: Enhanced precision using Decimal arithmetic and comprehensive validation.
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from decimal import Decimal

from app.services.precision_utils import (
    to_decimal, round_cost, round_manhour, validate_positive,
    to_float, format_formula_value
)


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
    
    Improved with Decimal precision and validation.
    """
    if mode == ManhourMode.WEIGHT_FACTOR:
        if weight_kg is None or factor_hr_per_kg is None:
            raise ValueError("WEIGHT_FACTOR mode requires weight_kg and factor_hr_per_kg")
        
        # Validate inputs
        validate_positive(weight_kg, "Weight", allow_zero=True)
        validate_positive(factor_hr_per_kg, "Factor", allow_zero=False)
        
        # Convert to Decimal
        W = to_decimal(weight_kg)
        F = to_decimal(factor_hr_per_kg)
        
        # Calculate manhours
        mh = W * F
        mh_rounded = round_manhour(mh)
        
        return ManhourResult(
            manhours=to_float(mh_rounded),
            mode=mode,
            formula=f"Manhours = Weight({format_formula_value(W, 4)} kg) × Factor({format_formula_value(F, 4)} hr/kg) = {format_formula_value(mh, 4)} hr",
            intermediate_values={"weight_kg": to_float(W), "factor_hr_per_kg": to_float(F)}
        )
    elif mode == ManhourMode.QTY_TIME:
        if quantity is None or time_per_unit_hr is None:
            raise ValueError("QTY_TIME mode requires quantity and time_per_unit_hr")
        
        # Validate inputs
        validate_positive(quantity, "Quantity", allow_zero=False)
        validate_positive(time_per_unit_hr, "Time per unit", allow_zero=False)
        
        # Convert to Decimal
        Q = to_decimal(quantity)
        T = to_decimal(time_per_unit_hr)
        
        # Calculate manhours
        mh = Q * T
        mh_rounded = round_manhour(mh)
        
        return ManhourResult(
            manhours=to_float(mh_rounded),
            mode=mode,
            formula=f"Manhours = Qty({format_formula_value(Q, 0)}) × Time/Unit({format_formula_value(T, 4)} hr) = {format_formula_value(mh, 4)} hr",
            intermediate_values={"quantity": to_float(Q), "time_per_unit_hr": to_float(T)}
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
    
    Improved with Decimal precision and validation.
    """
    if mode == FabCalcMode.WEIGHT_BASED:
        if weight_kg is None or rate_per_kg is None:
            raise ValueError("WEIGHT_BASED mode requires weight_kg and rate_per_kg")
        
        # Validate inputs
        validate_positive(weight_kg, "Weight", allow_zero=True)
        validate_positive(rate_per_kg, "Rate per kg", allow_zero=False)
        
        # Convert to Decimal
        W = to_decimal(weight_kg)
        R = to_decimal(rate_per_kg)
        
        # Calculate cost
        cost = W * R
        cost_rounded = round_cost(cost)
        
        return FabricationCostResult(
            manhours=None, manhour_rate=None,
            weight_kg=to_float(W), rate_per_kg=to_float(R),
            fabrication_cost=to_float(cost_rounded),
            mode=mode,
            formula=f"Fab Cost = Weight({format_formula_value(W, 4)} kg) × Rate({format_formula_value(R, 2)}/kg) = {format_formula_value(cost, 2)}",
            intermediate_values={"weight_kg": to_float(W), "rate_per_kg": to_float(R)}
        )
    elif mode == FabCalcMode.MANHOUR_BASED:
        if manhours is None or hourly_rate is None:
            raise ValueError("MANHOUR_BASED mode requires manhours and hourly_rate")
        
        # Validate inputs
        validate_positive(manhours, "Manhours", allow_zero=True)
        validate_positive(hourly_rate, "Hourly rate", allow_zero=False)
        
        # Convert to Decimal
        MH = to_decimal(manhours)
        R = to_decimal(hourly_rate)
        
        # Calculate cost
        cost = MH * R
        cost_rounded = round_cost(cost)
        
        return FabricationCostResult(
            manhours=to_float(MH), manhour_rate=to_float(R),
            weight_kg=to_float(to_decimal(weight_kg)) if weight_kg is not None else None, 
            rate_per_kg=None,
            fabrication_cost=to_float(cost_rounded),
            mode=mode,
            formula=f"Fab Cost = Manhours({format_formula_value(MH, 4)} hr) × Rate({format_formula_value(R, 2)}/hr) = {format_formula_value(cost, 2)}",
            intermediate_values={"manhours": to_float(MH), "hourly_rate": to_float(R)}
        )
    else:
        raise ValueError(f"Unknown FabCalcMode: {mode}")
