"""
Weight Calculator — deterministic, formula-transparent.
Supports: plate/rectangular, pipe, beam, angle, channel, flat bar, round bar.
All dimensions in mm, output weight in kg.
Steel density default = 7850 kg/m³
"""
from dataclasses import dataclass
from typing import Optional
import math


STEEL_DENSITY_KG_M3 = 7850.0  # kg/m³ — configurable per job


@dataclass
class WeightResult:
    section_type: str
    weight_kg: float
    formula: str
    intermediate_values: dict
    unit_weight_kg_per_m: Optional[float] = None


def weight_plate(
    length_mm: float,
    width_mm: float,
    thickness_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """
    Plate / rectangular section weight.
    Formula: W = L × W × T × ρ / 1e9  (mm→m³, then × kg/m³)
    """
    volume_mm3 = length_mm * width_mm * thickness_mm
    weight_each = volume_mm3 * density_kg_m3 / 1_000_000_000.0
    total = weight_each * quantity
    return WeightResult(
        section_type="plate",
        weight_kg=round(total, 4),
        formula=f"W = L({length_mm}) × W({width_mm}) × T({thickness_mm}) × ρ({density_kg_m3}) / 1e9 × Qty({quantity})",
        intermediate_values={
            "volume_mm3": round(volume_mm3, 2),
            "weight_each_kg": round(weight_each, 4),
            "quantity": quantity,
            "density_kg_m3": density_kg_m3,
        }
    )


def weight_pipe(
    od_mm: float,
    thickness_mm: float,
    length_mm: float,
    quantity: float = 1.0
) -> WeightResult:
    """
    Pipe / hollow section weight.
    Formula: W = (OD - T) × T × L × 0.02466  (result in kg, length in mm)
    0.02466 = π × ρ_steel / 1e6  ≈ standard pipe weight factor
    """
    PIPE_FACTOR = 0.02466
    weight_each = (od_mm - thickness_mm) * thickness_mm * length_mm * PIPE_FACTOR / 1000.0
    total = weight_each * quantity
    return WeightResult(
        section_type="pipe",
        weight_kg=round(total, 4),
        formula=f"W = (OD({od_mm}) - T({thickness_mm})) × T({thickness_mm}) × L({length_mm}) × 0.02466 / 1000 × Qty({quantity})",
        intermediate_values={
            "od_mm": od_mm,
            "thickness_mm": thickness_mm,
            "length_mm": length_mm,
            "weight_each_kg": round(weight_each, 4),
            "quantity": quantity,
            "pipe_factor": PIPE_FACTOR,
        },
        unit_weight_kg_per_m=round((od_mm - thickness_mm) * thickness_mm * 0.02466, 4)
    )


def weight_round_bar(
    diameter_mm: float,
    length_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """
    Solid round bar weight.
    Formula: W = π/4 × D² × L × ρ / 1e9
    """
    area_mm2 = math.pi / 4.0 * diameter_mm ** 2
    volume_mm3 = area_mm2 * length_mm
    weight_each = volume_mm3 * density_kg_m3 / 1_000_000_000.0
    total = weight_each * quantity
    return WeightResult(
        section_type="round_bar",
        weight_kg=round(total, 4),
        formula=f"W = π/4 × D({diameter_mm})² × L({length_mm}) × ρ({density_kg_m3}) / 1e9 × Qty({quantity})",
        intermediate_values={
            "area_mm2": round(area_mm2, 4),
            "volume_mm3": round(volume_mm3, 2),
            "weight_each_kg": round(weight_each, 4),
            "quantity": quantity,
        }
    )


def weight_flat_bar(
    width_mm: float,
    thickness_mm: float,
    length_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """Flat bar = rectangular section."""
    return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)


def weight_angle(
    leg1_mm: float,
    leg2_mm: float,
    thickness_mm: float,
    length_mm: float,
    quantity: float = 1.0,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """
    Angle section weight (approximate — treats as two plates minus corner overlap).
    Area = (leg1 + leg2 - thickness) × thickness
    """
    area_mm2 = (leg1_mm + leg2_mm - thickness_mm) * thickness_mm
    volume_mm3 = area_mm2 * length_mm
    weight_each = volume_mm3 * density_kg_m3 / 1_000_000_000.0
    total = weight_each * quantity
    return WeightResult(
        section_type="angle",
        weight_kg=round(total, 4),
        formula=f"W = (L1({leg1_mm})+L2({leg2_mm})-T({thickness_mm})) × T({thickness_mm}) × L({length_mm}) × ρ / 1e9 × Qty({quantity})",
        intermediate_values={
            "area_mm2": round(area_mm2, 4),
            "volume_mm3": round(volume_mm3, 2),
            "weight_each_kg": round(weight_each, 4),
            "quantity": quantity,
        }
    )


import logging
logger = logging.getLogger(__name__)

def calculate_weight(
    section_type: str,
    quantity: float = 1.0,
    length_mm: Optional[float] = None,
    width_mm: Optional[float] = None,
    thickness_mm: Optional[float] = None,
    od_mm: Optional[float] = None,
    diameter_mm: Optional[float] = None,
    leg1_mm: Optional[float] = None,
    leg2_mm: Optional[float] = None,
    density_kg_m3: float = STEEL_DENSITY_KG_M3
) -> WeightResult:
    """Universal dispatcher for weight calculation based on section type."""
    st = section_type.lower().replace(" ", "_").replace("-", "_")

    try:
        if st in ("plate", "flat", "flat_bar", "rectangular"):
            if not all([length_mm, width_mm, thickness_mm]):
                logger.warning(f"Plate requires L, W, T. Got: L={length_mm}, W={width_mm}, T={thickness_mm}")
                return WeightResult(section_type="plate", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)

        elif st in ("pipe", "tube", "hollow_section", "hss"):
            if not all([od_mm, thickness_mm, length_mm]):
                logger.warning(f"Pipe requires OD, T, L. Got: OD={od_mm}, T={thickness_mm}, L={length_mm}")
                return WeightResult(section_type="pipe", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_pipe(od_mm, thickness_mm, length_mm, quantity)

        elif st in ("round_bar", "rod", "solid_bar"):
            d = diameter_mm or width_mm
            if not all([d, length_mm]):
                logger.warning(f"Round bar requires D, L. Got: D={d}, L={length_mm}")
                return WeightResult(section_type="round_bar", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_round_bar(d, length_mm, quantity, density_kg_m3)

        elif st in ("angle", "l_section"):
            # Resilient angle logic: fallback to width if legs missing
            if not all([thickness_mm, length_mm]):
                 logger.warning(f"Angle requires T, L. Got: T={thickness_mm}, L={length_mm}")
                 return WeightResult(section_type="angle", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            l1 = leg1_mm or width_mm or 0
            l2 = leg2_mm or l1
            if l1 == 0:
                logger.warning("Angle leg size is 0")
                return WeightResult(section_type="angle", weight_kg=0.0, formula="Leg size is 0", intermediate_values={})
            return weight_angle(l1, l2, thickness_mm, length_mm, quantity, density_kg_m3)

        elif st in ("beam", "channel", "i_beam", "h_beam", "ipn", "upn", "hea", "heb"):
            if not all([length_mm, width_mm, thickness_mm]):
                logger.warning(f"Beam requires L, W, T. Got: L={length_mm}, W={width_mm}, T={thickness_mm}")
                return WeightResult(section_type="beam", weight_kg=0.0, formula="Incomplete dimensions", intermediate_values={})
            return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)

        else:
            # Fallback to plate
            if all([length_mm, width_mm, thickness_mm]):
                return weight_plate(length_mm, width_mm, thickness_mm, quantity, density_kg_m3)
            
            logger.warning(f"Unknown section type or missing dimensions for '{section_type}'")
            return WeightResult(section_type=st, weight_kg=0.0, formula=f"Cannot calculate weight for {st}", intermediate_values={})

    except Exception as e:
        logger.error(f"Internal weight calculator error: {e}")
        return WeightResult(section_type=st, weight_kg=0.0, formula=str(e), intermediate_values={})
