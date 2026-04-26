"""
Overhead & Profit Margin Calculator — deterministic.
Overhead: Overhead Cost = Total Direct Cost × Overhead %
Selling:  Selling Price = Total Cost (incl. overhead) × (1 + Margin %)

IMPROVED: Enhanced precision using Decimal arithmetic and comprehensive validation.
"""
from dataclasses import dataclass
from decimal import Decimal

from app.services.precision_utils import (
    to_decimal, round_cost, calculate_percentage,
    validate_cost, validate_positive, to_float, format_formula_value
)


@dataclass
class OverheadMarginResult:
    total_direct_cost: float
    overhead_percentage: float
    overhead_cost: float
    total_cost_with_overhead: float
    profit_margin_percentage: float
    profit_amount: float
    selling_price: float
    formula_overhead: str
    formula_selling: str
    intermediate_values: dict


def calculate_overhead_and_margin(
    total_direct_cost: float,
    overhead_percentage: float,
    profit_margin_percentage: float,
) -> OverheadMarginResult:
    """
    Overhead and profit margin.
    Overhead Cost  = Total Direct Cost × (Overhead% / 100)
    Total w/ OH    = Direct + Overhead
    Selling Price  = Total w/ OH × (1 + Margin% / 100)
    
    Improved with Decimal precision and validation.
    """
    # Validate inputs
    validate_cost(total_direct_cost, "Total direct cost")
    validate_positive(overhead_percentage, "Overhead percentage", allow_zero=True)
    validate_positive(profit_margin_percentage, "Profit margin percentage", allow_zero=True)
    
    # Convert to Decimal for precise calculation
    direct_cost = to_decimal(total_direct_cost)
    oh_pct = to_decimal(overhead_percentage)
    profit_pct = to_decimal(profit_margin_percentage)
    
    # Calculate overhead
    overhead_cost = calculate_percentage(direct_cost, oh_pct)
    
    # Calculate total with overhead
    total_with_overhead = direct_cost + overhead_cost
    
    # Calculate profit
    profit_amount = calculate_percentage(total_with_overhead, profit_pct)
    
    # Calculate selling price
    selling_price = total_with_overhead + profit_amount
    
    # Round to standard precision
    direct_rounded = round_cost(direct_cost)
    oh_rounded = round_cost(overhead_cost)
    total_oh_rounded = round_cost(total_with_overhead)
    profit_rounded = round_cost(profit_amount)
    selling_rounded = round_cost(selling_price)
    
    return OverheadMarginResult(
        total_direct_cost=to_float(direct_rounded),
        overhead_percentage=to_float(oh_pct),
        overhead_cost=to_float(oh_rounded),
        total_cost_with_overhead=to_float(total_oh_rounded),
        profit_margin_percentage=to_float(profit_pct),
        profit_amount=to_float(profit_rounded),
        selling_price=to_float(selling_rounded),
        formula_overhead=(
            f"Overhead = DirectCost({format_formula_value(direct_cost, 2)}) × {format_formula_value(oh_pct, 2)}% = {format_formula_value(oh_rounded, 2)}"
        ),
        formula_selling=(
            f"SellingPrice = TotalCost({format_formula_value(total_oh_rounded, 2)}) × (1 + {format_formula_value(profit_pct, 2)}%) = {format_formula_value(selling_rounded, 2)}"
        ),
        intermediate_values={
            "total_direct_cost": to_float(direct_rounded),
            "overhead_percentage": to_float(oh_pct),
            "overhead_cost": to_float(oh_rounded),
            "total_cost_with_overhead": to_float(total_oh_rounded),
            "profit_margin_percentage": to_float(profit_pct),
            "profit_amount": to_float(profit_rounded),
        }
    )
