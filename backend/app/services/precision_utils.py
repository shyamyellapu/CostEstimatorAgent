"""
Precision Utilities for Job Costing Calculations.
Provides consistent rounding, validation, and precision handling across all cost modules.
Addresses floating-point accuracy issues and ensures financial calculation precision.
"""
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Union, Optional
import logging

logger = logging.getLogger(__name__)

# Set decimal precision for financial calculations
getcontext().prec = 28  # High precision for intermediate calculations


class PrecisionConfig:
    """Centralized precision configuration for all calculations."""
    
    # Rounding precision for different types of values
    WEIGHT_DECIMALS = 4          # kg - 4 decimal places
    DIMENSION_DECIMALS = 2       # mm - 2 decimal places  
    MANHOUR_DECIMALS = 4         # hours - 4 decimal places
    AREA_DECIMALS = 4            # m² - 4 decimal places
    COST_DECIMALS = 2            # AED - 2 decimal places (currency)
    RATE_DECIMALS = 4            # rates - 4 decimal places
    PERCENTAGE_DECIMALS = 2      # % - 2 decimal places
    
    # Validation thresholds
    MIN_WEIGHT_KG = 0.0001       # Minimum weight to consider (0.1 gram)
    MAX_WEIGHT_KG = 1000000.0    # Maximum reasonable weight (1000 tons)
    MIN_DIMENSION_MM = 0.01      # Minimum dimension (0.01 mm)
    MAX_DIMENSION_MM = 100000.0  # Maximum dimension (100 meters)
    MIN_COST = 0.0
    MAX_COST = 1_000_000_000.0   # 1 billion AED maximum
    
    # Calculation tolerance for validation
    CALC_TOLERANCE = Decimal('0.01')  # 1 cent tolerance for verification


def to_decimal(value: Union[float, int, str, Decimal, None], default: Optional[Decimal] = None) -> Optional[Decimal]:
    """
    Safely convert value to Decimal with proper error handling.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Decimal value or default
    """
    if value is None or value == "":
        return default
    
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError) as e:
        logger.warning(f"Failed to convert {value} to Decimal: {e}. Using default: {default}")
        return default


def round_decimal(value: Union[Decimal, float], decimals: int) -> Decimal:
    """
    Round Decimal to specified number of decimal places using ROUND_HALF_UP.
    
    Args:
        value: Value to round
        decimals: Number of decimal places
        
    Returns:
        Rounded Decimal value
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    
    quantizer = Decimal(10) ** -decimals
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def round_weight(value: Union[Decimal, float]) -> Decimal:
    """Round weight value to standard precision."""
    return round_decimal(value, PrecisionConfig.WEIGHT_DECIMALS)


def round_cost(value: Union[Decimal, float]) -> Decimal:
    """Round cost value to standard precision (2 decimal places for currency)."""
    return round_decimal(value, PrecisionConfig.COST_DECIMALS)


def round_manhour(value: Union[Decimal, float]) -> Decimal:
    """Round manhour value to standard precision."""
    return round_decimal(value, PrecisionConfig.MANHOUR_DECIMALS)


def round_area(value: Union[Decimal, float]) -> Decimal:
    """Round area value to standard precision."""
    return round_decimal(value, PrecisionConfig.AREA_DECIMALS)


def round_dimension(value: Union[Decimal, float]) -> Decimal:
    """Round dimension value to standard precision."""
    return round_decimal(value, PrecisionConfig.DIMENSION_DECIMALS)


def validate_positive(value: Union[Decimal, float], name: str, allow_zero: bool = True) -> None:
    """
    Validate that a value is positive (or zero if allowed).
    
    Args:
        value: Value to validate
        name: Name of the parameter (for error messages)
        allow_zero: Whether zero is allowed
        
    Raises:
        ValueError: If validation fails
    """
    if value is None:
        raise ValueError(f"{name} cannot be None")
    
    decimal_val = to_decimal(value, Decimal('0'))
    
    if allow_zero:
        if decimal_val < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")
    else:
        if decimal_val <= 0:
            raise ValueError(f"{name} must be > 0, got {value}")


def validate_range(
    value: Union[Decimal, float], 
    name: str, 
    min_val: Optional[float] = None,
    max_val: Optional[float] = None
) -> None:
    """
    Validate that a value is within acceptable range.
    
    Args:
        value: Value to validate
        name: Name of the parameter
        min_val: Minimum acceptable value
        max_val: Maximum acceptable value
        
    Raises:
        ValueError: If value is out of range
    """
    if value is None:
        raise ValueError(f"{name} cannot be None")
    
    decimal_val = to_decimal(value, Decimal('0'))
    
    if min_val is not None and decimal_val < Decimal(str(min_val)):
        raise ValueError(f"{name} must be >= {min_val}, got {value}")
    
    if max_val is not None and decimal_val > Decimal(str(max_val)):
        raise ValueError(f"{name} must be <= {max_val}, got {value}")


def validate_weight(weight_kg: Union[Decimal, float], allow_zero: bool = True) -> None:
    """Validate weight value is within acceptable range."""
    validate_range(
        weight_kg, 
        "Weight",
        min_val=0.0 if allow_zero else PrecisionConfig.MIN_WEIGHT_KG,
        max_val=PrecisionConfig.MAX_WEIGHT_KG
    )


def validate_dimension(dimension_mm: Union[Decimal, float], name: str = "Dimension") -> None:
    """Validate dimension value is within acceptable range."""
    validate_range(
        dimension_mm,
        name,
        min_val=PrecisionConfig.MIN_DIMENSION_MM,
        max_val=PrecisionConfig.MAX_DIMENSION_MM
    )


def validate_cost(cost: Union[Decimal, float], name: str = "Cost") -> None:
    """Validate cost value is within acceptable range."""
    validate_range(
        cost,
        name,
        min_val=PrecisionConfig.MIN_COST,
        max_val=PrecisionConfig.MAX_COST
    )


def safe_divide(
    numerator: Union[Decimal, float], 
    denominator: Union[Decimal, float],
    default: Union[Decimal, float] = Decimal('0')
) -> Decimal:
    """
    Safely divide two numbers, handling division by zero.
    
    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Default value if division by zero
        
    Returns:
        Division result or default
    """
    num = to_decimal(numerator, Decimal('0'))
    den = to_decimal(denominator, Decimal('1'))
    
    if den == 0:
        logger.warning(f"Division by zero: {numerator}/{denominator}, using default {default}")
        return to_decimal(default, Decimal('0'))
    
    return num / den


def sum_decimals(*values: Union[Decimal, float, None]) -> Decimal:
    """
    Sum multiple values with Decimal precision, ignoring None values.
    
    Args:
        *values: Values to sum
        
    Returns:
        Sum as Decimal
    """
    total = Decimal('0')
    for val in values:
        if val is not None:
            total += to_decimal(val, Decimal('0'))
    return total


def calculate_percentage(
    value: Union[Decimal, float],
    percentage: Union[Decimal, float]
) -> Decimal:
    """
    Calculate percentage of a value with proper precision.
    
    Args:
        value: Base value
        percentage: Percentage (e.g., 15 for 15%)
        
    Returns:
        Calculated percentage amount
    """
    val = to_decimal(value, Decimal('0'))
    pct = to_decimal(percentage, Decimal('0'))
    return val * (pct / Decimal('100'))


def verify_calculation(
    calculated: Union[Decimal, float],
    expected: Union[Decimal, float],
    tolerance: Optional[Decimal] = None
) -> bool:
    """
    Verify that a calculated value matches expected value within tolerance.
    
    Args:
        calculated: Calculated value
        expected: Expected value
        tolerance: Acceptable difference (defaults to CALC_TOLERANCE)
        
    Returns:
        True if values match within tolerance
    """
    if tolerance is None:
        tolerance = PrecisionConfig.CALC_TOLERANCE
    
    calc = to_decimal(calculated, Decimal('0'))
    exp = to_decimal(expected, Decimal('0'))
    
    diff = abs(calc - exp)
    return diff <= tolerance


def format_formula_value(value: Union[Decimal, float], decimals: int = 2) -> str:
    """
    Format a value for display in formulas with consistent decimal places.
    
    Args:
        value: Value to format
        decimals: Number of decimal places
        
    Returns:
        Formatted string
    """
    val = to_decimal(value, Decimal('0'))
    rounded = round_decimal(val, decimals)
    return f"{rounded:.{decimals}f}"


def to_float(value: Optional[Decimal]) -> Optional[float]:
    """
    Convert Decimal to float for serialization.
    
    Args:
        value: Decimal value
        
    Returns:
        Float value or None
    """
    if value is None:
        return None
    return float(value)
