"""
C&J Gulf Equipment Manufacturing LLC
Master Rate Card Configuration
================================

Reference Job: CNJ/142676/01/2025 (Descon)
Date: 2025 baseline rates
Status: PRODUCTION LOCKED

These rates are derived from the reference costing sheet and represent
C&J's standard pricing structure. DO NOT modify without authorization.

Usage:
    1. Database seeder loads these rates on system initialization
    2. Costing engine retrieves active rates from database
    3. Rate overrides require admin approval and audit trail
"""
from typing import Dict, Any, List

# ═══════════════════════════════════════════════════════════════
# MATERIAL RATES (Row 23)
# ═══════════════════════════════════════════════════════════════
MATERIAL_RATES: Dict[str, Any] = {
    "structural_steel_aed_per_kg": {
        "value": 5.50,
        "unit": "AED/kg",
        "description": "Structural steel material rate (S275/A36 grade)",
        "category": "material",
        "reference": "CNJ/142676 - Row 23"
    },
    "stainless_steel_aed_per_kg": {
        "value": 22.00,
        "unit": "AED/kg",
        "description": "Stainless steel material rate (304/316 grade)",
        "category": "material",
        "reference": "Market average"
    },
}

# ═══════════════════════════════════════════════════════════════
# FASTENERS & CONSUMABLES (Rows 24, 28)
# ═══════════════════════════════════════════════════════════════
FASTENER_RATES: Dict[str, Any] = {
    "bolt_m16_aed_per_piece": {
        "value": 2.50,
        "unit": "AED/piece",
        "description": "M16 bolt grade 8.8 with nut and washer",
        "category": "fasteners",
        "reference": "CNJ/142676 - Row 24"
    },
    "bolt_m20_aed_per_piece": {
        "value": 3.80,
        "unit": "AED/piece",
        "description": "M20 bolt grade 8.8 with nut and washer",
        "category": "fasteners",
        "reference": "CNJ/142676 - Row 24"
    },
    "bolt_m24_aed_per_piece": {
        "value": 5.20,
        "unit": "AED/piece",
        "description": "M24 bolt grade 8.8 with nut and washer",
        "category": "fasteners",
        "reference": "Market average"
    },
    "consumables_percentage_of_steel": {
        "value": 3.5,
        "unit": "%",
        "description": "Consumables as % of structural steel weight (electrodes, gas, cutting discs)",
        "category": "consumables",
        "reference": "CNJ/142676 - Row 28 (5348/(2741*5.5)) = 3.5%",
        "formula": "Consumables = Total Steel Weight (kg) × Steel Rate (AED/kg) × 3.5%"
    },
}

# ═══════════════════════════════════════════════════════════════
# PAINT MATERIAL (Row 25)
# ═══════════════════════════════════════════════════════════════
PAINT_RATES: Dict[str, Any] = {
    "paint_2pack_epoxy_aed_per_litre": {
        "value": 85.00,
        "unit": "AED/litre",
        "description": "2-pack epoxy paint system (150 DFT)",
        "category": "paint_material",
        "reference": "CNJ/142676 - Row 25"
    },
    "paint_coverage_factor_m2_per_litre": {
        "value": 6.67,
        "unit": "m²/litre",
        "description": "Paint coverage at 150 DFT (1 litre covers 6.67 m²)",
        "category": "paint_material",
        "reference": "Standard 150 DFT coverage",
        "formula": "Paint Litres = Surface Area (m²) / 6.67"
    },
}

# ═══════════════════════════════════════════════════════════════
# LABOUR RATES & FACTORS (Rows 29-35)
# ═══════════════════════════════════════════════════════════════
LABOUR_RATES: Dict[str, Any] = {
    # Base hourly rate
    "labour_hourly_rate_aed": {
        "value": 35.00,
        "unit": "AED/hour",
        "description": "Standard fabrication labour hourly rate",
        "category": "labour",
        "reference": "CNJ/142676 calculation"
    },
    
    # Manhour factors (hours per kg of steel)
    "welding_manhours_per_kg": {
        "value": 0.35,
        "unit": "hours/kg",
        "description": "Welding manhours factor",
        "category": "labour",
        "reference": "CNJ/142676 - Row 29 (960 hrs / 2741 kg) = 0.35 hr/kg",
        "formula": "Welding Manhours = Steel Weight (kg) × 0.35"
    },
    "fabrication_manhours_per_kg": {
        "value": 0.28,
        "unit": "hours/kg",
        "description": "Fabrication (cutting, drilling, assembly) manhours factor",
        "category": "labour",
        "reference": "CNJ/142676 - Row 30 (768 hrs / 2741 kg) = 0.28 hr/kg",
        "formula": "Fabrication Manhours = Steel Weight (kg) × 0.28"
    },
    "fitting_manhours_per_kg": {
        "value": 0.18,
        "unit": "hours/kg",
        "description": "Fitting & assembly manhours factor",
        "category": "labour",
        "reference": "CNJ/142676 - Row 31 (493 hrs / 2741 kg) = 0.18 hr/kg",
        "formula": "Fitting Manhours = Steel Weight (kg) × 0.18"
    },
    "grinding_manhours_per_kg": {
        "value": 0.07,
        "unit": "hours/kg",
        "description": "Grinding & finishing manhours factor",
        "category": "labour",
        "reference": "CNJ/142676 - Row 32 (192 hrs / 2741 kg) = 0.07 hr/kg",
        "formula": "Grinding Manhours = Steel Weight (kg) × 0.07"
    },
}

# ═══════════════════════════════════════════════════════════════
# SURFACE TREATMENT (Rows 39-41)
# ═══════════════════════════════════════════════════════════════
SURFACE_TREATMENT_RATES: Dict[str, Any] = {
    "galvanizing_aed_per_kg": {
        "value": 3.20,
        "unit": "AED/kg",
        "description": "Hot-dip galvanizing rate",
        "category": "surface_treatment",
        "reference": "CNJ/142676 - Row 39"
    },
    "blasting_sa25_aed_per_m2": {
        "value": 12.00,
        "unit": "AED/m²",
        "description": "Abrasive blasting to Sa 2.5 standard",
        "category": "surface_treatment",
        "reference": "CNJ/142676 - Row 40"
    },
    "painting_aed_per_m2": {
        "value": 18.00,
        "unit": "AED/m²",
        "description": "Paint application labour (2-pack epoxy system)",
        "category": "surface_treatment",
        "reference": "CNJ/142676 - Row 41"
    },
    "surface_area_factor_m2_per_kg": {
        "value": 0.0256,
        "unit": "m²/kg",
        "description": "Empirical conversion: structural steel weight to paintable surface area",
        "category": "surface_treatment",
        "reference": "CNJ/142676 - (70.14 m² / 2741 kg) = 0.0256 m²/kg",
        "formula": "Surface Area (m²) = Steel Weight (kg) × 0.0256",
        "note": "This factor accounts for typical beam/column cross-sections with partial surface exposure"
    },
}

# ═══════════════════════════════════════════════════════════════
# OVERHEAD & MARGIN (Rows 42-43)
# ═══════════════════════════════════════════════════════════════
OVERHEAD_MARGIN: Dict[str, Any] = {
    "overhead_percentage": {
        "value": 12.0,
        "unit": "%",
        "description": "Factory overhead (utilities, supervision, QA/QC)",
        "category": "overhead",
        "reference": "CNJ/142676 - Row 42"
    },
    "profit_margin_percentage": {
        "value": 15.0,
        "unit": "%",
        "description": "Target profit margin",
        "category": "margin",
        "reference": "CNJ/142676 - Row 43"
    },
}

# ═══════════════════════════════════════════════════════════════
# TRANSPORT & LOGISTICS (Row 44)
# ═══════════════════════════════════════════════════════════════
TRANSPORT_RATES: Dict[str, Any] = {
    "transport_percentage_of_total": {
        "value": 2.5,
        "unit": "%",
        "description": "Transport & logistics as % of subtotal",
        "category": "transport",
        "reference": "Standard for UAE mainland delivery"
    },
    "transport_minimum_aed": {
        "value": 1500.00,
        "unit": "AED",
        "description": "Minimum transport charge",
        "category": "transport",
        "reference": "Standard for UAE mainland delivery"
    },
}

# ═══════════════════════════════════════════════════════════════
# SCHEDULE FACTORS (Drawing Reader validation)
# ═══════════════════════════════════════════════════════════════
SCHEDULE_FACTORS: Dict[str, Any] = {
    "standard_schedule_weeks": {
        "value": 4,
        "unit": "weeks",
        "description": "Standard fabrication schedule for typical jobs (< 5 tonnes)",
        "category": "schedule",
        "reference": "C&J standard lead time"
    },
    "rush_surcharge_percentage": {
        "value": 20.0,
        "unit": "%",
        "description": "Rush delivery surcharge (< 2 weeks)",
        "category": "schedule",
        "reference": "C&J commercial policy"
    },
}


def get_all_rates() -> List[Dict[str, Any]]:
    """
    Get all master rates as a flat list suitable for database seeding.
    
    Returns:
        List of rate dictionaries with keys: key, name, category, value, unit, description
    """
    rates = []
    
    # Combine all rate dictionaries
    all_rate_dicts = [
        MATERIAL_RATES,
        FASTENER_RATES,
        PAINT_RATES,
        LABOUR_RATES,
        SURFACE_TREATMENT_RATES,
        OVERHEAD_MARGIN,
        TRANSPORT_RATES,
        SCHEDULE_FACTORS,
    ]
    
    for rate_dict in all_rate_dicts:
        for key, config in rate_dict.items():
            rates.append({
                "key": key,
                "name": config.get("description", key),
                "category": config.get("category", "general"),
                "value": config["value"],
                "unit": config.get("unit", ""),
                "description": (
                    f"{config.get('description', '')} | "
                    f"Reference: {config.get('reference', 'N/A')}"
                ),
                "is_active": True,
            })
    
    return rates


def get_rate_by_key(key: str) -> float:
    """Get rate value by key."""
    all_rate_dicts = [
        MATERIAL_RATES,
        FASTENER_RATES,
        PAINT_RATES,
        LABOUR_RATES,
        SURFACE_TREATMENT_RATES,
        OVERHEAD_MARGIN,
        TRANSPORT_RATES,
        SCHEDULE_FACTORS,
    ]
    
    for rate_dict in all_rate_dicts:
        if key in rate_dict:
            return rate_dict[key]["value"]
    
    raise KeyError(f"Rate key '{key}' not found in master rate configuration")
