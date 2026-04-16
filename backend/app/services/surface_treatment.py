"""
Surface Treatment Cost Calculator — deterministic.
Formula: Cost = Surface Area (m²) × Rate per m²
Surface area must be provided or estimated from item dimensions.
"""
from dataclasses import dataclass
import math


@dataclass
class SurfaceTreatmentResult:
    surface_area_m2: float
    rate_per_m2: float
    treatment_type: str
    surface_treatment_cost: float
    formula: str
    intermediate_values: dict


def estimate_surface_area_plate_m2(
    length_mm: float,
    width_mm: float,
    thickness_mm: float,
    include_edges: bool = True
) -> float:
    """Estimate surface area of a plate including both faces and edges."""
    face_area = 2 * (length_mm * width_mm)
    if include_edges:
        edge_area = 2 * (length_mm * thickness_mm) + 2 * (width_mm * thickness_mm)
    else:
        edge_area = 0.0
    return (face_area + edge_area) / 1_000_000.0  # mm² → m²


def estimate_surface_area_pipe_m2(
    od_mm: float,
    length_mm: float
) -> float:
    """Estimate outer surface area of a pipe."""
    area_mm2 = math.pi * od_mm * length_mm
    return area_mm2 / 1_000_000.0  # mm² → m²


def calculate_surface_treatment(
    surface_area_m2: float,
    rate_per_m2: float,
    treatment_type: str = "blast_and_prime",
) -> SurfaceTreatmentResult:
    """
    Surface treatment cost.
    Formula: Cost = Area (m²) × Rate/m²
    """
    if surface_area_m2 < 0:
        raise ValueError("Surface area must be >= 0")
    if rate_per_m2 < 0:
        raise ValueError("Rate per m² must be >= 0")

    cost = surface_area_m2 * rate_per_m2

    return SurfaceTreatmentResult(
        surface_area_m2=round(surface_area_m2, 4),
        rate_per_m2=rate_per_m2,
        treatment_type=treatment_type,
        surface_treatment_cost=round(cost, 2),
        formula=f"Surface Treatment({treatment_type}) = Area({surface_area_m2:.4f}m²) × Rate({rate_per_m2}/m²) = {cost:.2f}",
        intermediate_values={
            "surface_area_m2": round(surface_area_m2, 4),
            "rate_per_m2": rate_per_m2,
            "treatment_type": treatment_type,
        }
    )
