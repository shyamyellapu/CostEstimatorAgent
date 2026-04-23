"""
Steel Section Reference Table
=============================
Standard unit weights (kg/m) for structural steel sections.
Based on BS EN 10365:2017 and common Gulf region fabrication tables.

Used for:
1. Weight validation and cross-checking
2. Auto-populating missing weight data
3. Detecting extraction errors (weight > 20% off = flag)
"""
from typing import Dict, Optional, Tuple
from decimal import Decimal
import re

# Standard unit weights in kg/m
SECTION_WEIGHTS: Dict[str, float] = {
    # Universal Columns (UC)
    "UC 356×406×634": 634.0,
    "UC 356×406×551": 551.0,
    "UC 356×406×467": 467.0,
    "UC 356×406×393": 393.0,
    "UC 356×406×340": 340.0,
    "UC 356×406×287": 287.0,
    "UC 356×406×235": 235.0,
    "UC 356×368×202": 202.0,
    "UC 356×368×177": 177.0,
    "UC 356×368×153": 153.0,
    "UC 356×368×129": 129.0,
    "UC 305×305×283": 283.0,
    "UC 305×305×240": 240.0,
    "UC 305×305×198": 198.0,
    "UC 305×305×158": 158.0,
    "UC 305×305×137": 137.0,
    "UC 305×305×118": 118.0,
    "UC 305×305×97": 97.0,
    "UC 254×254×167": 167.0,
    "UC 254×254×132": 132.0,
    "UC 254×254×107": 107.0,
    "UC 254×254×89": 89.0,
    "UC 254×254×73": 73.0,
    "UC 203×203×86": 86.0,
    "UC 203×203×71": 71.0,
    "UC 203×203×60": 60.0,
    "UC 203×203×52": 52.0,
    "UC 203×203×46": 46.0,
    "UC 152×152×37": 37.0,
    "UC 152×152×30": 30.0,
    "UC 152×152×23": 23.0,
    
    # Universal Beams (UB)
    "UB 914×419×388": 388.0,
    "UB 914×305×289": 289.0,
    "UB 914×305×253": 253.0,
    "UB 914×305×224": 224.0,
    "UB 838×292×226": 226.0,
    "UB 838×292×194": 194.0,
    "UB 762×267×197": 197.0,
    "UB 762×267×173": 173.0,
    "UB 762×267×147": 147.0,
    "UB 686×254×170": 170.0,
    "UB 686×254×152": 152.0,
    "UB 686×254×140": 140.0,
    "UB 686×254×125": 125.0,
    "UB 610×305×238": 238.0,
    "UB 610×305×179": 179.0,
    "UB 610×305×149": 149.0,
    "UB 610×229×140": 140.0,
    "UB 610×229×125": 125.0,
    "UB 610×229×113": 113.0,
    "UB 610×229×101": 101.0,
    "UB 533×210×122": 122.0,
    "UB 533×210×109": 109.0,
    "UB 533×210×101": 101.0,
    "UB 533×210×92": 92.0,
    "UB 533×210×82": 82.0,
    "UB 457×191×98": 98.0,
    "UB 457×191×89": 89.0,
    "UB 457×191×82": 82.0,
    "UB 457×191×74": 74.0,
    "UB 457×191×67": 67.0,
    "UB 457×152×82": 82.0,
    "UB 457×152×74": 74.0,
    "UB 457×152×67": 67.0,
    "UB 457×152×60": 60.0,
    "UB 457×152×52": 52.0,
    "UB 406×178×74": 74.0,
    "UB 406×178×67": 67.0,
    "UB 406×178×60": 60.0,
    "UB 406×178×54": 54.0,
    "UB 406×140×46": 46.0,
    "UB 406×140×39": 39.0,
    "UB 356×171×67": 67.0,
    "UB 356×171×57": 57.0,
    "UB 356×171×51": 51.0,
    "UB 356×171×45": 45.0,
    "UB 356×127×39": 39.0,
    "UB 356×127×33": 33.0,
    "UB 305×165×54": 54.0,
    "UB 305×165×46": 46.0,
    "UB 305×165×40": 40.0,
    "UB 305×127×48": 48.0,
    "UB 305×127×42": 42.0,
    "UB 305×127×37": 37.0,
    "UB 305×102×33": 33.0,
    "UB 305×102×28": 28.0,
    "UB 305×102×25": 25.0,
    "UB 254×146×43": 43.0,
    "UB 254×146×37": 37.0,
    "UB 254×146×31": 31.0,
    "UB 254×102×28": 28.0,
    "UB 254×102×25": 25.0,
    "UB 254×102×22": 22.0,
    "UB 203×133×30": 30.0,
    "UB 203×133×25": 25.1,
    "UB 203×102×23": 23.1,
    "UB 178×102×19": 19.0,
    "UB 152×89×16": 16.0,
    "UB 127×76×13": 13.0,
    
    # Parallel Flange Channels (PFC)
    "PFC 430×100×64": 64.4,
    "PFC 380×100×54": 54.0,
    "PFC 300×100×46": 45.5,
    "PFC 300×90×41": 41.0,
    "PFC 260×90×35": 34.8,
    "PFC 260×75×28": 27.6,
    "PFC 230×90×32": 32.2,
    "PFC 230×75×26": 25.7,
    "PFC 200×90×30": 29.7,
    "PFC 200×75×23": 23.4,
    "PFC 180×90×26": 26.1,
    "PFC 180×75×20": 20.3,
    "PFC 150×90×24": 24.0,
    "PFC 150×75×18": 17.9,
    "PFC 125×65×15": 14.8,
    "PFC 100×50×10": 10.2,
    
    # Equal Angles (L)
    "L 200×200×24": 72.1,
    "L 200×200×20": 60.8,
    "L 200×200×18": 54.7,
    "L 200×200×16": 48.5,
    "L 150×150×18": 40.1,
    "L 150×150×15": 33.8,
    "L 150×150×12": 27.3,
    "L 150×150×10": 22.9,
    "L 125×125×12": 22.5,
    "L 125×125×10": 18.8,
    "L 125×125×8": 15.1,
    "L 100×100×12": 18.2,
    "L 100×100×10": 15.1,
    "L 100×100×8": 12.2,
    "L 90×90×12": 16.3,
    "L 90×90×10": 13.6,
    "L 90×90×8": 10.9,
    "L 80×80×10": 12.2,
    "L 80×80×8": 9.63,
    "L 75×75×10": 11.4,
    "L 75×75×8": 8.99,
    "L 75×75×6": 6.85,
    "L 70×70×7": 7.38,
    "L 65×65×8": 7.73,
    "L 60×60×8": 6.91,
    "L 60×60×6": 5.28,
    "L 50×50×6": 4.37,
    "L 50×50×5": 3.67,
    "L 45×45×5": 3.30,
    "L 40×40×5": 2.97,
    
    # Unequal Angles (L)
    "L 200×150×18": 47.1,
    "L 200×150×15": 39.6,
    "L 200×150×12": 31.8,
    "L 200×100×15": 33.7,
    "L 200×100×12": 27.3,
    "L 200×100×10": 22.9,
    "L 150×90×12": 21.6,
    "L 150×90×10": 18.2,
    "L 125×75×12": 17.8,
    "L 125×75×10": 14.9,
    "L 125×75×8": 12.0,
    "L 100×75×10": 13.0,
    "L 100×75×8": 10.3,
    "L 100×65×10": 12.3,
    "L 100×65×8": 9.61,
    "L 80×60×8": 8.34,
    "L 80×60×7": 7.36,
    "L 75×50×8": 7.39,
    "L 75×50×6": 5.65,
    "L 65×50×6": 5.13,
    "L 60×40×6": 4.48,
    
    # Tees cut from UC (UCT - approximate as half of parent UC)
    "UCT 152×152×30": 15.0,
    "UCT 152×152×23": 11.5,
    "UCT 203×203×46": 23.0,
    "UCT 203×203×52": 26.0,
    
    # Tees cut from UB (UBT - approximate as half of parent UB)
    "UBT 203×133×30": 15.0,
    "UBT 203×133×25": 12.5,
    "UBT 133×101×15": 14.9,
    
    # Rectangular Hollow Sections (RHS) - common sizes
    "RHS 400×200×12.5": 115.0,
    "RHS 400×200×10": 93.9,
    "RHS 300×200×10": 77.1,
    "RHS 300×200×8": 62.8,
    "RHS 250×150×10": 60.1,
    "RHS 250×150×8": 49.1,
    "RHS 200×100×8": 37.7,
    "RHS 200×100×6": 29.1,
    "RHS 150×100×6": 24.3,
    "RHS 150×100×5": 20.5,
    "RHS 120×80×6": 19.2,
    "RHS 120×80×5": 16.3,
    "RHS 100×50×5": 11.8,
    "RHS 100×50×4": 9.58,
    
    # Square Hollow Sections (SHS) - common sizes
    "SHS 400×400×12.5": 182.0,
    "SHS 400×400×10": 148.0,
    "SHS 350×350×12.5": 158.0,
    "SHS 350×350×10": 128.0,
    "SHS 300×300×12.5": 134.0,
    "SHS 300×300×10": 108.0,
    "SHS 250×250×10": 87.3,
    "SHS 250×250×8": 71.2,
    "SHS 200×200×10": 66.9,
    "SHS 200×200×8": 54.7,
    "SHS 150×150×8": 40.1,
    "SHS 150×150×6": 31.0,
    "SHS 120×120×6": 24.3,
    "SHS 120×120×5": 20.5,
    "SHS 100×100×6": 19.8,
    "SHS 100×100×5": 16.7,
    "SHS 90×90×5": 14.9,
    "SHS 80×80×5": 13.1,
    "SHS 60×60×5": 9.61,
    "SHS 50×50×5": 7.85,
    
    # Circular Hollow Sections (CHS) - common sizes
    "CHS 508×12.5": 152.0,
    "CHS 508×10": 123.0,
    "CHS 457×12.5": 137.0,
    "CHS 457×10": 111.0,
    "CHS 406×12.5": 121.0,
    "CHS 406×10": 98.3,
    "CHS 356×12.5": 106.0,
    "CHS 356×10": 85.5,
    "CHS 323×10": 77.3,
    "CHS 323×8": 62.6,
    "CHS 273×10": 65.1,
    "CHS 273×8": 52.7,
    "CHS 219×8": 42.3,
    "CHS 219×6": 32.2,
    "CHS 168×8": 32.4,
    "CHS 168×6": 24.7,
    "CHS 114×6": 16.7,
    "CHS 114×5": 14.0,
    "CHS 89×5": 10.9,
    "CHS 76×5": 9.31,
    "CHS 60×5": 7.32,
    "CHS 48×5": 5.79,
}


def normalize_section_designation(designation: str) -> str:
    """Normalize section designation for table lookup.
    
    Examples:
        "UC152x152x30" → "UC 152×152×30"
        "ub 203x133x30" → "UB 203×133×30"
        "L100×100×10" → "L 100×100×10"
    """
    # Remove extra spaces
    designation = designation.strip()
    
    # Replace 'x' or 'X' with '×'
    designation = re.sub(r'[xX]', '×', designation)
    
    # Add space after section type if missing
    designation = re.sub(r'^([A-Z]{1,4})(\d)', r'\1 \2', designation, flags=re.IGNORECASE)
    
    # Normalize spaces around dimensions
    designation = re.sub(r'\s*×\s*', '×', designation)
    
    # Uppercase section type
    parts = designation.split(' ', 1)
    if len(parts) == 2:
        designation = parts[0].upper() + ' ' + parts[1]
    
    return designation


def get_section_unit_weight(designation: str) -> Optional[float]:
    """Get standard unit weight for a section designation.
    
    Args:
        designation: Section designation (e.g., "UC 152×152×30", "L 100×100×10")
        
    Returns:
        Unit weight in kg/m, or None if not found
    """
    normalized = normalize_section_designation(designation)
    return SECTION_WEIGHTS.get(normalized)


def validate_weight(
    calculated_weight_kg: float,
    section_designation: str,
    length_mm: float,
    quantity: int = 1,
    tolerance_percent: float = 20.0
) -> Tuple[bool, Optional[str], Optional[float]]:
    """Validate calculated weight against section table.
    
    Args:
        calculated_weight_kg: Weight from extraction or calculation
        section_designation: Section type
        length_mm: Member length
        quantity: Number of members
        tolerance_percent: Acceptable deviation (default 20%)
        
    Returns:
        Tuple of (is_valid, warning_message, expected_weight_kg)
    """
    unit_weight = get_section_unit_weight(section_designation)
    
    if unit_weight is None:
        # Section not in table - cannot validate
        return True, None, None
    
    # Calculate expected weight
    expected_weight = unit_weight * (length_mm / 1000.0) * quantity
    
    # Check tolerance
    if calculated_weight_kg == 0:
        return False, f"Weight is zero (expected {expected_weight:.2f} kg)", expected_weight
    
    deviation_percent = abs(calculated_weight_kg - expected_weight) / expected_weight * 100.0
    
    if deviation_percent > tolerance_percent:
        return False, (
            f"Weight deviation {deviation_percent:.1f}%: "
            f"calculated {calculated_weight_kg:.2f} kg vs expected {expected_weight:.2f} kg "
            f"(unit weight {unit_weight:.2f} kg/m)"
        ), expected_weight
    
    return True, None, expected_weight


def calculate_weight_from_section(
    section_designation: str,
    length_mm: float,
    quantity: int = 1
) -> Optional[float]:
    """Calculate weight using section table.
    
    Args:
        section_designation: Section type
        length_mm: Member length
        quantity: Number of members
        
    Returns:
        Weight in kg, or None if section not in table
    """
    unit_weight = get_section_unit_weight(section_designation)
    
    if unit_weight is None:
        return None
    
    return unit_weight * (length_mm / 1000.0) * quantity


def calculate_plate_weight(
    length_mm: float,
    width_mm: float,
    thickness_mm: float,
    quantity: int = 1,
    density_kg_m3: float = 7850.0
) -> float:
    """Calculate weight of flat plate.
    
    Args:
        length_mm: Plate length
        width_mm: Plate width
        thickness_mm: Plate thickness
        quantity: Number of plates
        density_kg_m3: Material density (default steel = 7850 kg/m³)
        
    Returns:
        Weight in kg
    """
    volume_m3 = (length_mm / 1000.0) * (width_mm / 1000.0) * (thickness_mm / 1000.0)
    return volume_m3 * density_kg_m3 * quantity
