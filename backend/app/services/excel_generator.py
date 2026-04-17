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

        # Header fields
        job_number = str(job_data.get("job_number") or "")
        client_name = str(job_data.get("client_name") or "")
        project_name = str(job_data.get("project_name") or "")
        project_ref = str(job_data.get("project_ref") or "")

        ws["A3"] = f"REF NO: {job_number}" if job_number else "REF NO:"
        ws["C4"] = client_name
        ws["G4"] = datetime.now().strftime("%Y-%m-%d")
        ws["O4"] = project_ref
        ws["O5"] = job_number
        ws["C7"] = project_name
        ws["G7"] = "X" if "module" in project_name.lower() else ""

        total_weight = self._safe_float(totals.get("total_weight_kg"))
        total_material_cost = self._safe_float(totals.get("total_material_cost"))
        total_direct_cost = self._safe_float(totals.get("total_direct_cost"))
        overhead_cost = self._safe_float(totals.get("overhead_cost"))
        selling_price = self._safe_float(totals.get("selling_price"))
        profit_amount = self._safe_float(totals.get("profit_amount"))
        total_consumables_cost = self._safe_float(totals.get("total_consumables_cost"))

        welding_manhours = self._sum_first_present(
            line_items,
            ["welding_manhours", "welding_hours", "weld_manhours", "welding_time_hr"],
        )
        fabrication_manhours = self._sum_first_present(
            line_items,
            ["fabrication_manhours", "fabrication_hours", "manhours", "labor_manhours"],
        )
        surface_area = self._sum_first_present(
            line_items,
            ["surface_area_m2", "surface_area"],
        )

        material_rate = self._safe_float(rates.get("material_rate_per_kg"), default=4.0)
        welding_rate = self._safe_float(rates.get("welding_hourly_rate"), default=45.0)
        fabrication_rate = self._safe_float(rates.get("fabrication_hourly_rate"), default=45.0)
        surface_rate = self._safe_float(rates.get("surface_treatment_rate_per_m2"), default=55.0)

        # Material rows from template
        ws["B23"] = "Structural Steel Material"
        ws["G23"] = total_weight
        ws["H23"] = "Kg"
        ws["J23"] = material_rate

        # If bolt/plate items exist, summarize into row 24; otherwise keep template defaults.
        bolt_like = [
            li for li in line_items
            if str(li.get("section_type", "")).lower() in {"bolt", "plate", "fastener"}
        ]
        if bolt_like:
            top_desc = str(bolt_like[0].get("description") or "Bolts / Plates")
            qty = sum(self._safe_float(li.get("quantity"), default=0.0) for li in bolt_like)
            ws["B24"] = top_desc
            ws["G24"] = qty
            ws["H24"] = "Nos"

        ws["I29"] = welding_manhours
        ws["J29"] = welding_rate
        ws["I30"] = fabrication_manhours
        ws["J30"] = fabrication_rate

        # Consumables and surface treatment lines
        if total_consumables_cost > 0:
            ws["J33"] = total_consumables_cost
        if surface_area > 0:
            ws["G40"] = surface_area
            ws["G41"] = surface_area
        ws["J40"] = surface_rate
        ws["J41"] = surface_rate

        # Totals block from engine outputs
        ws["D55"] = total_direct_cost
        ws["D56"] = overhead_cost
        ws["D57"] = total_direct_cost + overhead_cost
        ws["D58"] = selling_price
        ws["D59"] = profit_amount if profit_amount else (selling_price - (total_direct_cost + overhead_cost))

        # Keep profitability formulas aligned to actual totals.
        ws["F61"] = "Profit Margin"
        if selling_price > 0:
            ws["F62"] = (ws["D59"].value or 0) / selling_price

        # Ensure numeric formatting for key summary outputs.
        for cell_ref in ["D55", "D56", "D57", "D58", "D59", "K23", "K24", "K25", "K29", "K30", "K33", "K40", "K41"]:
            ws[cell_ref].number_format = "#,##0.00"
        for cell_ref in ["G23", "G24", "G25", "I29", "I30", "G40", "G41"]:
            ws[cell_ref].number_format = "#,##0.000"
        ws["F62"].number_format = "0.00%"

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
