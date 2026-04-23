"""
Welding Cost Calculator — deterministic.
Formula:
  Weld Length = No. of Joints × Length per Joint
  Welding Manhours = Weld Length × Time per meter (hr/m)
  Welding Cost = Welding Manhours × Hourly Rate

IMPROVED: Enhanced precision using Decimal arithmetic and comprehensive validation.
"""
from dataclasses import dataclass
from decimal import Decimal

from app.services.precision_utils import (
    to_decimal, round_cost, round_manhour, round_dimension,
    validate_positive, to_float, format_formula_value
)


@dataclass
class WeldingCostResult:
    num_joints: int
    length_per_joint_mm: float
    weld_length_mm: float
    weld_length_m: float
    time_per_m_hr: float
    welding_manhours: float
    hourly_rate: float
    welding_cost: float
    formula: str
    intermediate_values: dict


def calculate_welding_cost(
    num_joints: int,
    length_per_joint_mm: float,
    time_per_m_hr: float,
    hourly_rate: float,
) -> WeldingCostResult:
    """
    Welding cost calculation.
    Weld Length (mm) = Joints × Length/Joint
    Weld Length (m)  = Weld Length (mm) / 1000
    Manhours         = Weld Length (m) × Time/m
    Cost             = Manhours × Rate
    
    Improved with Decimal precision and validation.
    """
    # Validate inputs
    if num_joints < 0:
        raise ValueError(f"num_joints must be >= 0, got {num_joints}")
    validate_positive(length_per_joint_mm, "Length per joint", allow_zero=True)
    validate_positive(time_per_m_hr, "Time per meter", allow_zero=False)
    validate_positive(hourly_rate, "Hourly rate", allow_zero=False)
    
    # Convert to Decimal for precise calculation
    N = Decimal(str(num_joints))
    L_mm = to_decimal(length_per_joint_mm)
    T = to_decimal(time_per_m_hr)
    R = to_decimal(hourly_rate)
    
    # Calculate weld length in mm
    weld_length_mm = N * L_mm
    
    # Convert to meters
    weld_length_m = weld_length_mm / Decimal('1000')
    
    # Calculate manhours
    welding_manhours = weld_length_m * T
    
    # Calculate cost
    welding_cost = welding_manhours * R
    
    # Round to standard precision
    weld_mm_rounded = round_dimension(weld_length_mm)
    weld_m_rounded = round_manhour(weld_length_m)
    mh_rounded = round_manhour(welding_manhours)
    cost_rounded = round_cost(welding_cost)
    
    return WeldingCostResult(
        num_joints=num_joints,
        length_per_joint_mm=to_float(L_mm),
        weld_length_mm=to_float(weld_mm_rounded),
        weld_length_m=to_float(weld_m_rounded),
        time_per_m_hr=to_float(T),
        welding_manhours=to_float(mh_rounded),
        hourly_rate=to_float(R),
        welding_cost=to_float(cost_rounded),
        formula=(
            f"WeldLen = Joints({num_joints}) × LenPerJoint({format_formula_value(L_mm, 2)}mm) = {format_formula_value(weld_mm_rounded, 2)}mm; "
            f"WeldMH = {format_formula_value(weld_m_rounded, 4)}m × {format_formula_value(T, 2)}hr/m = {format_formula_value(mh_rounded, 4)}hr; "
            f"WeldCost = {format_formula_value(mh_rounded, 4)}hr × {format_formula_value(R, 2)}/hr = {format_formula_value(cost_rounded, 2)}"
        ),
        intermediate_values={
            "num_joints": num_joints,
            "length_per_joint_mm": to_float(L_mm),
            "weld_length_mm": to_float(weld_mm_rounded),
            "weld_length_m": to_float(weld_m_rounded),
            "time_per_m_hr": to_float(T),
            "welding_manhours": to_float(mh_rounded),
            "hourly_rate": to_float(R),
        }
    )
