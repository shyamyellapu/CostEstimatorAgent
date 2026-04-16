"""
Welding Cost Calculator — deterministic.
Formula:
  Weld Length = No. of Joints × Length per Joint
  Welding Manhours = Weld Length × Time per meter (hr/m)
  Welding Cost = Welding Manhours × Hourly Rate
"""
from dataclasses import dataclass


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
    """
    if num_joints < 0:
        raise ValueError("num_joints must be >= 0")

    weld_length_mm = num_joints * length_per_joint_mm
    weld_length_m = weld_length_mm / 1000.0
    welding_manhours = weld_length_m * time_per_m_hr
    welding_cost = welding_manhours * hourly_rate

    return WeldingCostResult(
        num_joints=num_joints,
        length_per_joint_mm=length_per_joint_mm,
        weld_length_mm=round(weld_length_mm, 2),
        weld_length_m=round(weld_length_m, 4),
        time_per_m_hr=time_per_m_hr,
        welding_manhours=round(welding_manhours, 4),
        hourly_rate=hourly_rate,
        welding_cost=round(welding_cost, 2),
        formula=(
            f"WeldLen = Joints({num_joints}) × LenPerJoint({length_per_joint_mm}mm) = {weld_length_mm:.2f}mm; "
            f"WeldMH = {weld_length_m:.4f}m × {time_per_m_hr}hr/m = {welding_manhours:.4f}hr; "
            f"WeldCost = {welding_manhours:.4f}hr × {hourly_rate}/hr = {welding_cost:.2f}"
        ),
        intermediate_values={
            "num_joints": num_joints,
            "length_per_joint_mm": length_per_joint_mm,
            "weld_length_mm": round(weld_length_mm, 2),
            "weld_length_m": round(weld_length_m, 4),
            "time_per_m_hr": time_per_m_hr,
            "welding_manhours": round(welding_manhours, 4),
            "hourly_rate": hourly_rate,
        }
    )
