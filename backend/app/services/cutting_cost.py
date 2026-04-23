"""
Cutting / Machining Cost Calculator — deterministic.
Two supported modes:
  Mode A: per-cut   → Cost = No. of Cuts × Rate per Cut
  Mode B: time-based → Cost = Time (hr) × Rate per Hour

IMPROVED: Enhanced precision using Decimal arithmetic and comprehensive validation.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from decimal import Decimal

from app.services.precision_utils import (
    to_decimal, round_cost, validate_positive,
    to_float, format_formula_value
)


class CuttingMode(str, Enum):
    PER_CUT = "per_cut"
    TIME_BASED = "time_based"


@dataclass
class CuttingCostResult:
    mode: str
    num_cuts: Optional[int]
    rate_per_cut: Optional[float]
    time_hr: Optional[float]
    hourly_rate: Optional[float]
    cutting_cost: float
    formula: str
    intermediate_values: dict


def calculate_cutting_cost(
    mode: CuttingMode,
    num_cuts: Optional[int] = None,
    rate_per_cut: Optional[float] = None,
    time_hr: Optional[float] = None,
    hourly_rate: Optional[float] = None,
) -> CuttingCostResult:
    """
    Cutting/machining cost.
    PER_CUT:    Cost = Cuts × Rate/cut
    TIME_BASED: Cost = Time × Rate/hr
    
    Improved with Decimal precision and validation.
    """
    if mode == CuttingMode.PER_CUT:
        if num_cuts is None or rate_per_cut is None:
            raise ValueError("PER_CUT mode requires num_cuts and rate_per_cut")
        
        # Validate inputs
        if num_cuts < 0:
            raise ValueError(f"num_cuts must be >= 0, got {num_cuts}")
        validate_positive(rate_per_cut, "Rate per cut", allow_zero=False)
        
        # Convert to Decimal
        N = Decimal(str(num_cuts))
        R = to_decimal(rate_per_cut)
        
        # Calculate cost
        cost = N * R
        cost_rounded = round_cost(cost)
        
        return CuttingCostResult(
            mode=mode, num_cuts=num_cuts, rate_per_cut=to_float(R),
            time_hr=None, hourly_rate=None,
            cutting_cost=to_float(cost_rounded),
            formula=f"Cutting = Cuts({num_cuts}) × Rate({format_formula_value(R, 2)}/cut) = {format_formula_value(cost_rounded, 2)}",
            intermediate_values={"num_cuts": num_cuts, "rate_per_cut": to_float(R)}
        )
    elif mode == CuttingMode.TIME_BASED:
        if time_hr is None or hourly_rate is None:
            raise ValueError("TIME_BASED mode requires time_hr and hourly_rate")
        
        # Validate inputs
        validate_positive(time_hr, "Time", allow_zero=True)
        validate_positive(hourly_rate, "Hourly rate", allow_zero=False)
        
        # Convert to Decimal
        T = to_decimal(time_hr)
        R = to_decimal(hourly_rate)
        
        # Calculate cost
        cost = T * R
        cost_rounded = round_cost(cost)
        
        return CuttingCostResult(
            mode=mode, num_cuts=None, rate_per_cut=None,
            time_hr=to_float(T), hourly_rate=to_float(R),
            cutting_cost=to_float(cost_rounded),
            formula=f"Cutting = Time({format_formula_value(T, 4)}hr) × Rate({format_formula_value(R, 2)}/hr) = {format_formula_value(cost_rounded, 2)}",
            intermediate_values={"time_hr": to_float(T), "hourly_rate": to_float(R)}
        )
    else:
        raise ValueError(f"Unknown CuttingMode: {mode}")
