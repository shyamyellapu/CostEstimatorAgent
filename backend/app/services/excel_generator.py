"""Excel generator based on the sample workbook template in ReferenceFiles."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

logger = logging.getLogger(__name__)


class ExcelGenerator:
    """Generate output Excel in the same format as Sample Job Costing Sheet.xlsx."""

    def __init__(self) -> None:
        # .../backend/app/services/excel_generator.py -> project root at parents[3]
        project_root = Path(__file__).resolve().parents[3]
        self.template_path = project_root / "ReferenceFiles" / "Sample Job Costing Sheet.xlsx"

    def generate(
        self,
        job_data: Dict[str, Any],
        costing_result: Dict[str, Any],
        rates: Dict[str, Any],
    ) -> bytes:
        """Generate workbook bytes using the sample template as base."""
        wb = self._load_template_workbook()
        ws = wb.worksheets[0]

        self._fill_costing_template(ws, job_data, costing_result, rates)
        self._append_rates_sheet(wb, rates)
        self._append_audit_sheet(wb, costing_result.get("audit_trail", []))

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()

    def _load_template_workbook(self) -> Workbook:
        if not self.template_path.exists():
            raise FileNotFoundError(f"Excel template not found: {self.template_path}")
        return load_workbook(self.template_path)

    def _fill_costing_template(
        self,
        ws,
        job_data: Dict[str, Any],
        costing_result: Dict[str, Any],
        rates: Dict[str, Any],
    ) -> None:
        totals = costing_result or {}
        line_items = totals.get("line_items", []) or []
        extracted_data = job_data.get("extracted_data", {}) or {}

        # ──────────────────────────────────────────────────────────────
        # HEADER SECTION (Rows 1-12)
        # ──────────────────────────────────────────────────────────────
        job_number = str(job_data.get("job_number") or job_data.get("reference_number") or "")
        client_name = str(job_data.get("client_name") or extracted_data.get("client") or "")
        project_name = str(job_data.get("project_name") or extracted_data.get("project_name") or "")
        project_ref = str(job_data.get("project_ref") or extracted_data.get("drawing_number") or "")
        unit_area = str(extracted_data.get("unit_area") or "")

        ws["A3"] = f"REF NO: {job_number}" if job_number else "REF NO:"
        ws["C4"] = client_name
        ws["G4"] = datetime.now().strftime("%Y-%m-%d")
        ws["O4"] = project_ref
        ws["O5"] = job_number
        ws["C7"] = project_name
        ws["G7"] = "X" if ("module" in project_name.lower() or "module" in unit_area.lower()) else ""

        # ──────────────────────────────────────────────────────────────
        # EXTRACT COSTING DATA FROM RESULTS & EXTRACTED DATA
        # ──────────────────────────────────────────────────────────────
        total_weight_kg = self._safe_float(totals.get("total_weight_kg"))
        total_material_cost = self._safe_float(totals.get("total_material_cost"))
        total_direct_cost = self._safe_float(totals.get("total_direct_cost"))
        total_fabrication_cost = self._safe_float(totals.get("total_fabrication_cost"))
        total_welding_cost = self._safe_float(totals.get("total_welding_cost"))
        total_consumables_cost = self._safe_float(totals.get("total_consumables_cost"))
        total_surface_treatment_cost = self._safe_float(totals.get("total_surface_treatment_cost"))
        overhead_cost = self._safe_float(totals.get("overhead_cost"))
        selling_price = self._safe_float(totals.get("selling_price"))
        profit_amount = self._safe_float(totals.get("profit_amount"))

        # Extracted costing inputs from AI extraction
        costing_inputs = extracted_data.get("costing_sheet_inputs", {}) or {}
        structural_steel_total_kg = self._safe_float(costing_inputs.get("structural_steel_total_kg"), total_weight_kg)
        bolt_quantity_nos = self._safe_float(costing_inputs.get("bolt_quantity_nos"), 0.0)
        paint_litres = self._safe_float(costing_inputs.get("paint_litres"), 0.0)
        welding_consumable_kg = self._safe_float(costing_inputs.get("welding_consumable_kg"), 0.0)
        fabrication_hours = self._safe_float(costing_inputs.get("fabrication_hours"), 0.0)
        galvanizing_weight_kg = self._safe_float(costing_inputs.get("galvanizing_weight_kg"), 0.0)
        blasting_area_m2 = self._safe_float(costing_inputs.get("blasting_area_m2"), 0.0)
        painting_area_m2 = self._safe_float(costing_inputs.get("painting_area_m2"), 0.0)

        # Fallback: compute from line items if not extracted
        if not fabrication_hours:
            fabrication_hours = self._sum_first_present(
                line_items,
                ["fabrication_manhours", "fabrication_hours", "manhours", "labor_manhours"],
            )
        welding_manhours = self._sum_first_present(
            line_items,
            ["welding_manhours", "welding_hours", "weld_manhours", "welding_time_hr"],
        )
        surface_area = self._sum_first_present(
            line_items,
            ["surface_area_m2", "surface_area"],
        )
        if not blasting_area_m2:
            blasting_area_m2 = surface_area
        if not painting_area_m2:
            painting_area_m2 = surface_area

        # Rates from configuration
        material_rate = self._safe_float(rates.get("material_rate_per_kg"), default=4.0)
        fabrication_hourly_rate = self._safe_float(rates.get("fabrication_hourly_rate"), default=45.0)
        welding_hourly_rate = self._safe_float(rates.get("welding_hourly_rate"), default=45.0)
        consumable_unit_rate = self._safe_float(rates.get("consumable_unit_rate"), default=15.0)
        surface_treatment_rate = self._safe_float(rates.get("surface_treatment_rate_per_m2"), default=55.0)

        # ──────────────────────────────────────────────────────────────
        # ROW 23: STRUCTURAL STEEL MATERIAL (Kg)
        # ──────────────────────────────────────────────────────────────
        ws["B23"] = "Structural Steel Material"
        ws["G23"] = structural_steel_total_kg
        ws["H23"] = "Kg"
        ws["J23"] = material_rate
        # Row 23 formula in K23: =G23*J23

        # ──────────────────────────────────────────────────────────────
        # ROW 24: BOLTS / FASTENERS (Nos)
        # ──────────────────────────────────────────────────────────────
        ws["B24"] = "M20x90 Long Bolts HEX HD"
        ws["G24"] = bolt_quantity_nos if bolt_quantity_nos > 0 else ""
        ws["H24"] = "Nos"
        # J24 rate kept from template (12.5 AED default)

        # ──────────────────────────────────────────────────────────────
        # ROW 25: PAINT MATERIAL (litres)
        # ──────────────────────────────────────────────────────────────
        ws["B25"] = "Paint Material"
        ws["G25"] = paint_litres if paint_litres > 0 else ""
        ws["H25"] = "litres"
        # J25 rate kept from template (21 AED default)

        # ──────────────────────────────────────────────────────────────
        # ROW 29: WELDING LABOUR (Kg consumables or Manhours)
        # ──────────────────────────────────────────────────────────────
        ws["B29"] = "Structural Welding consumables"
        # Use welding_consumable_kg if available, else fallback
        welding_qty = welding_consumable_kg if welding_consumable_kg > 0 else welding_manhours
        ws["I29"] = welding_qty if welding_qty > 0 else ""
        ws["H29"] = "Kg" if welding_consumable_kg > 0 else "Hrs"
        ws["J29"] = consumable_unit_rate if welding_consumable_kg > 0 else welding_hourly_rate

        # ──────────────────────────────────────────────────────────────
        # ROW 30: FABRICATION LABOUR (Manhours)
        # ──────────────────────────────────────────────────────────────
        ws["B30"] = "Structural Fabrication labour"
        ws["I30"] = fabrication_hours if fabrication_hours > 0 else ""
        ws["H30"] = "Hrs"
        ws["J30"] = fabrication_hourly_rate
        # Row 30 formula in K30: =I30*J30

        # ──────────────────────────────────────────────────────────────
        # ROW 39: GALVANIZING (Kg)
        # ──────────────────────────────────────────────────────────────
        ws["B39"] = "Galvanizing Work"
        ws["G39"] = galvanizing_weight_kg if galvanizing_weight_kg > 0 else ""
        ws["H39"] = "Kg"
        # J39 rate kept from template (2000 AED default or as configured)

        # ──────────────────────────────────────────────────────────────
        # ROW 40: BLASTING (SQM)
        # ──────────────────────────────────────────────────────────────
        ws["B40"] = f"Blasting ({blasting_area_m2:.2f} Sq M)"
        ws["G40"] = blasting_area_m2 if blasting_area_m2 > 0 else ""
        ws["H40"] = "SQM"
        ws["J40"] = surface_treatment_rate
        # Row 40 formula in K40: =G40*J40

        # ──────────────────────────────────────────────────────────────
        # ROW 41: PAINTING (SQM)
        # ──────────────────────────────────────────────────────────────
        ws["B41"] = f"Painting ({painting_area_m2:.2f} Sq M)"
        ws["G41"] = painting_area_m2 if painting_area_m2 > 0 else ""
        ws["H41"] = "SQM"
        ws["J41"] = surface_treatment_rate
        # Row 41 formula in K41: =G41*J41

        # ──────────────────────────────────────────────────────────────
        # TOTALS SECTION (Rows 55-62)
        # ──────────────────────────────────────────────────────────────
        # D55: Total cost (sum of K16:K54 from template formulas)
        ws["D55"] = total_direct_cost if total_direct_cost > 0 else ""

        # D56: Overheads (from template or calculated)
        ws["D56"] = overhead_cost if overhead_cost > 0 else ""

        # D57: GRAND TOTAL = D55 + D56
        grand_total = (total_direct_cost or 0) + (overhead_cost or 0)
        ws["D57"] = grand_total if grand_total > 0 else ""

        # D58: Selling Price
        ws["D58"] = selling_price if selling_price > 0 else ""

        # D59: Net Profit = D58 - D57
        profit = (selling_price or 0) - grand_total
        ws["D59"] = profit if profit != 0 else ""

        # F61: Profit Margin % = D59 / D58
        if selling_price and selling_price > 0:
            ws["F61"] = profit / selling_price
            ws["F61"].number_format = "0.0%"

        # ──────────────────────────────────────────────────────────────
        # NUMERIC FORMATTING
        # ──────────────────────────────────────────────────────────────
        # Currency format for costs
        for cell_ref in ["D55", "D56", "D57", "D58", "D59"]:
            if ws[cell_ref].value:
                ws[cell_ref].number_format = "#,##0.00"

        # Quantity/Weight format (3 decimals)
        for cell_ref in ["G23", "G24", "G25", "I29", "I30", "G39", "G40", "G41"]:
            if ws[cell_ref].value:
                ws[cell_ref].number_format = "#,##0.000"

        # Rate format (2 decimals)
        for cell_ref in ["J23", "J29", "J30", "J40", "J41"]:
            if ws[cell_ref].value:
                ws[cell_ref].number_format = "#,##0.00"

    def _append_rates_sheet(self, wb: Workbook, rates: Dict[str, Any]) -> None:
        ws = wb.create_sheet("RATES & CONFIG")
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["A"].width = 36
        ws.column_dimensions["B"].width = 18
        ws.column_dimensions["C"].width = 16

        ws.merge_cells("A1:C1")
        ws["A1"] = "RATE CONFIGURATION SNAPSHOT"
        ws["A1"].font = Font(name="Calibri", bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor="1F3864")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        headers = ["Parameter", "Value", "Unit"]
        for col, h in enumerate(headers, 1):
            c = ws.cell(3, col, h)
            c.font = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F3864")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = self._thin_border()

        units = {
            "material_rate_per_kg": "AED/kg",
            "fabrication_hourly_rate": "AED/hr",
            "welding_hourly_rate": "AED/hr",
            "surface_treatment_rate_per_m2": "AED/m2",
            "overhead_percentage": "%",
            "profit_margin_percentage": "%",
        }

        row = 4
        for key, val in rates.items():
            ws.cell(row, 1, key)
            ws.cell(row, 2, self._safe_float(val, default=0.0))
            ws.cell(row, 3, units.get(key, ""))
            for col in [1, 2, 3]:
                c = ws.cell(row, col)
                c.font = Font(name="Calibri", size=9)
                c.border = self._thin_border()
            ws.cell(row, 2).number_format = "#,##0.000"
            row += 1

    def _append_audit_sheet(self, wb: Workbook, audit_trail: List[Dict[str, Any]]) -> None:
        ws = wb.create_sheet("AUDIT TRAIL")
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 14
        ws.column_dimensions["C"].width = 80

        ws.merge_cells("A1:C1")
        ws["A1"] = "CALCULATION AUDIT TRAIL"
        ws["A1"].font = Font(name="Calibri", bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor="1F3864")
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        for idx, h in enumerate(["Step / Item", "Status", "Details"], start=1):
            c = ws.cell(2, idx, h)
            c.font = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F3864")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = self._thin_border()

        row = 3
        for entry in audit_trail:
            step = entry.get("item_tag") or entry.get("step") or ""
            status = entry.get("status") or "ok"
            details = {k: v for k, v in entry.items() if k not in {"item_tag", "step", "status"}}
            ws.cell(row, 1, str(step))
            ws.cell(row, 2, str(status))
            ws.cell(row, 3, str(details))
            for col in [1, 2, 3]:
                c = ws.cell(row, col)
                c.font = Font(name="Calibri", size=9)
                c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
                c.border = self._thin_border()
            row += 1

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _sum_first_present(self, items: List[Dict[str, Any]], field_names: List[str]) -> float:
        total = 0.0
        for item in items:
            value = None
            for field_name in field_names:
                if field_name in item and item[field_name] is not None:
                    value = item[field_name]
                    break
            if value is not None:
                total += self._safe_float(value, default=0.0)
        return total

    @staticmethod
    def _thin_border() -> Border:
        side = Side(style="thin")
        return Border(left=side, right=side, top=side, bottom=side)


excel_generator = ExcelGenerator()
