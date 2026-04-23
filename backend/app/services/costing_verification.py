"""
Costing Calculation Verification and Testing Utilities
======================================================

This module provides tools for verifying the accuracy of costing calculations
and testing the improvements made to the job costing system.
"""
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging

from app.services.precision_utils import (
    to_decimal, verify_calculation, PrecisionConfig
)

logger = logging.getLogger(__name__)


class CostingVerification:
    """Verification utilities for costing calculations."""
    
    @staticmethod
    def verify_weight_calculation(
        calculated_weight: float,
        manual_check_volume_mm3: float,
        density_kg_m3: float = 7850.0
    ) -> Tuple[bool, str]:
        """
        Verify weight calculation against manual volume calculation.
        
        Args:
            calculated_weight: Weight calculated by the system (kg)
            manual_check_volume_mm3: Manually calculated volume (mm³)
            density_kg_m3: Material density
            
        Returns:
            Tuple of (is_valid, message)
        """
        expected_weight = manual_check_volume_mm3 * density_kg_m3 / 1_000_000_000.0
        
        is_valid = verify_calculation(calculated_weight, expected_weight)
        
        if is_valid:
            msg = f"✓ Weight verified: {calculated_weight:.4f} kg matches expected {expected_weight:.4f} kg"
        else:
            diff = abs(calculated_weight - expected_weight)
            msg = f"✗ Weight mismatch: {calculated_weight:.4f} kg vs expected {expected_weight:.4f} kg (diff: {diff:.4f} kg)"
        
        return is_valid, msg
    
    @staticmethod
    def verify_cost_sum(
        total_cost: float,
        individual_costs: List[float]
    ) -> Tuple[bool, str]:
        """
        Verify that total cost matches sum of individual costs.
        
        Args:
            total_cost: Total cost from system
            individual_costs: List of individual cost components
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Use Decimal for accurate summation
        expected_total = sum(to_decimal(c) for c in individual_costs)
        
        is_valid = verify_calculation(total_cost, float(expected_total))
        
        if is_valid:
            msg = f"✓ Cost sum verified: {total_cost:.2f} AED"
        else:
            diff = abs(to_decimal(total_cost) - expected_total)
            msg = f"✗ Cost sum mismatch: {total_cost:.2f} vs expected {float(expected_total):.2f} (diff: {float(diff):.2f})"
        
        return is_valid, msg
    
    @staticmethod
    def verify_percentage_calculation(
        result: float,
        base_value: float,
        percentage: float
    ) -> Tuple[bool, str]:
        """
        Verify percentage-based calculation.
        
        Args:
            result: Calculated result
            base_value: Base value
            percentage: Percentage applied
            
        Returns:
            Tuple of (is_valid, message)
        """
        expected = base_value * (percentage / 100.0)
        
        is_valid = verify_calculation(result, expected)
        
        if is_valid:
            msg = f"✓ Percentage verified: {result:.2f} = {base_value:.2f} × {percentage}%"
        else:
            msg = f"✗ Percentage mismatch: {result:.2f} vs expected {expected:.2f}"
        
        return is_valid, msg
    
    @staticmethod
    def check_precision_consistency(
        costing_result
    ) -> List[str]:
        """
        Check that all values in costing result have consistent precision.
        
        Args:
            costing_result: CostingResult object
            
        Returns:
            List of warning messages (empty if all consistent)
        """
        warnings = []
        
        # Check cost precision (should be 2 decimals)
        cost_fields = [
            ('total_material_cost', costing_result.total_material_cost),
            ('total_fabrication_cost', costing_result.total_fabrication_cost),
            ('total_welding_cost', costing_result.total_welding_cost),
            ('total_consumables_cost', costing_result.total_consumables_cost),
            ('total_cutting_cost', costing_result.total_cutting_cost),
            ('total_surface_treatment_cost', costing_result.total_surface_treatment_cost),
            ('total_direct_cost', costing_result.total_direct_cost),
            ('overhead_cost', costing_result.overhead_cost),
            ('profit_amount', costing_result.profit_amount),
            ('selling_price', costing_result.selling_price),
        ]
        
        for field_name, value in cost_fields:
            decimals = len(str(value).split('.')[-1]) if '.' in str(value) else 0
            if decimals > PrecisionConfig.COST_DECIMALS:
                warnings.append(
                    f"Warning: {field_name} has {decimals} decimals (expected {PrecisionConfig.COST_DECIMALS})"
                )
        
        # Check weight precision (should be 4 decimals)
        weight_decimals = len(str(costing_result.total_weight_kg).split('.')[-1]) if '.' in str(costing_result.total_weight_kg) else 0
        if weight_decimals > PrecisionConfig.WEIGHT_DECIMALS:
            warnings.append(
                f"Warning: total_weight_kg has {weight_decimals} decimals (expected {PrecisionConfig.WEIGHT_DECIMALS})"
            )
        
        return warnings
    
    @staticmethod
    def compare_old_vs_new(
        old_result: Dict,
        new_result: Dict,
        tolerance: float = 0.01
    ) -> Dict[str, any]:
        """
        Compare results from old and new calculation methods.
        
        Args:
            old_result: Results from old calculation
            new_result: Results from new improved calculation
            tolerance: Acceptable difference (default 1 cent)
            
        Returns:
            Dictionary with comparison results
        """
        comparison = {
            "all_within_tolerance": True,
            "differences": [],
            "improvements": []
        }
        
        # Compare key cost fields
        fields_to_compare = [
            'total_material_cost',
            'total_fabrication_cost',
            'total_welding_cost',
            'total_direct_cost',
            'selling_price'
        ]
        
        for field in fields_to_compare:
            old_val = old_result.get(field, 0)
            new_val = new_result.get(field, 0)
            diff = abs(old_val - new_val)
            
            if diff > tolerance:
                comparison["all_within_tolerance"] = False
                comparison["differences"].append({
                    "field": field,
                    "old_value": old_val,
                    "new_value": new_val,
                    "difference": diff,
                    "percent_change": (diff / old_val * 100) if old_val != 0 else 0
                })
            
            # Check if new value is more precise (fewer trailing decimals issues)
            if diff > 0:
                comparison["improvements"].append({
                    "field": field,
                    "note": "More precise calculation with Decimal arithmetic"
                })
        
        return comparison


def run_verification_suite(costing_result) -> Dict[str, any]:
    """
    Run complete verification suite on a costing result.
    
    Args:
        costing_result: CostingResult object to verify
        
    Returns:
        Dictionary with verification results
    """
    results = {
        "precision_warnings": [],
        "calculation_checks": [],
        "overall_status": "PASS"
    }
    
    # Check precision consistency
    precision_warnings = CostingVerification.check_precision_consistency(costing_result)
    results["precision_warnings"] = precision_warnings
    
    if precision_warnings:
        results["overall_status"] = "WARNING"
    
    # Verify cost summation
    individual_costs = [
        costing_result.total_material_cost,
        costing_result.total_fabrication_cost,
        costing_result.total_welding_cost,
        costing_result.total_consumables_cost,
        costing_result.total_cutting_cost,
        costing_result.total_surface_treatment_cost,
    ]
    
    is_valid, msg = CostingVerification.verify_cost_sum(
        costing_result.total_direct_cost,
        individual_costs
    )
    
    results["calculation_checks"].append({
        "check": "Direct cost summation",
        "valid": is_valid,
        "message": msg
    })
    
    if not is_valid:
        results["overall_status"] = "FAIL"
    
    # Verify overhead calculation
    is_valid, msg = CostingVerification.verify_percentage_calculation(
        costing_result.overhead_cost,
        costing_result.total_direct_cost,
        costing_result.overhead_percentage
    )
    
    results["calculation_checks"].append({
        "check": "Overhead calculation",
        "valid": is_valid,
        "message": msg
    })
    
    if not is_valid:
        results["overall_status"] = "FAIL"
    
    logger.info(f"Verification suite completed: {results['overall_status']}")
    
    return results
