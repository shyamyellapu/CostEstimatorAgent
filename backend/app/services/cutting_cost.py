"""
Cutting / Machining Cost Calculator — deterministic.
Two supported modes:
  Mode A: per-cut   → Cost = No. of Cuts × Rate per Cut
  Mode B: time-based → Cost = Time (hr) × Rate per Hour
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


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
    """
    if mode == CuttingMode.PER_CUT:
        if num_cuts is None or rate_per_cut is None:
            raise ValueError("PER_CUT mode requires num_cuts and rate_per_cut")
        cost = num_cuts * rate_per_cut
        return CuttingCostResult(
            mode=mode, num_cuts=num_cuts, rate_per_cut=rate_per_cut,
            time_hr=None, hourly_rate=None,
            cutting_cost=round(cost, 2),
            formula=f"Cutting = Cuts({num_cuts}) × Rate({rate_per_cut}/cut) = {cost:.2f}",
            intermediate_values={"num_cuts": num_cuts, "rate_per_cut": rate_per_cut}
        )
    elif mode == CuttingMode.TIME_BASED:
        if time_hr is None or hourly_rate is None:
            raise ValueError("TIME_BASED mode requires time_hr and hourly_rate")
        cost = time_hr * hourly_rate
        return CuttingCostResult(
            mode=mode, num_cuts=None, rate_per_cut=None,
            time_hr=time_hr, hourly_rate=hourly_rate,
            cutting_cost=round(cost, 2),
            formula=f"Cutting = Time({time_hr}hr) × Rate({hourly_rate}/hr) = {cost:.2f}",
            intermediate_values={"time_hr": time_hr, "hourly_rate": hourly_rate}
        )
    else:
        raise ValueError(f"Unknown CuttingMode: {mode}")
