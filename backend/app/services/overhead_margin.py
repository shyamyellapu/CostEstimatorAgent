"""
Overhead & Profit Margin Calculator — deterministic.
Overhead: Overhead Cost = Total Direct Cost × Overhead %
Selling:  Selling Price = Total Cost (incl. overhead) × (1 + Margin %)
"""
from dataclasses import dataclass


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
    """
    if total_direct_cost < 0:
        raise ValueError("total_direct_cost must be >= 0")

    overhead_cost = total_direct_cost * (overhead_percentage / 100.0)
    total_with_overhead = total_direct_cost + overhead_cost
    profit_amount = total_with_overhead * (profit_margin_percentage / 100.0)
    selling_price = total_with_overhead + profit_amount

    return OverheadMarginResult(
        total_direct_cost=round(total_direct_cost, 2),
        overhead_percentage=overhead_percentage,
        overhead_cost=round(overhead_cost, 2),
        total_cost_with_overhead=round(total_with_overhead, 2),
        profit_margin_percentage=profit_margin_percentage,
        profit_amount=round(profit_amount, 2),
        selling_price=round(selling_price, 2),
        formula_overhead=(
            f"Overhead = DirectCost({total_direct_cost:.2f}) × {overhead_percentage}% = {overhead_cost:.2f}"
        ),
        formula_selling=(
            f"SellingPrice = TotalCost({total_with_overhead:.2f}) × (1 + {profit_margin_percentage}%) = {selling_price:.2f}"
        ),
        intermediate_values={
            "total_direct_cost": round(total_direct_cost, 2),
            "overhead_percentage": overhead_percentage,
            "overhead_cost": round(overhead_cost, 2),
            "total_cost_with_overhead": round(total_with_overhead, 2),
            "profit_margin_percentage": profit_margin_percentage,
            "profit_amount": round(profit_amount, 2),
        }
    )
