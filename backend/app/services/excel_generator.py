"""
Excel Generator — produces real .xlsx workbook matching job costing sheet structure.
Uses openpyxl with formula strings preserved.
Template approach: programmatically replicates the sample costing sheet layout.
"""
import io
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side,
    GradientFill
)
from openpyxl.utils import get_column_letter
from openpyxl.styles.numbers import FORMAT_NUMBER_COMMA_SEPARATED1

logger = logging.getLogger(__name__)

# ─── Style Helpers ────────────────────────────────────────────────────────────

NAVY = "1F3864"
LIGHT_BLUE = "D9E1F2"
YELLOW = "FFFF00"
GREEN = "E2EFDA"
ORANGE = "FCE4D6"
WHITE = "FFFFFF"
LIGHT_GREY = "F2F2F2"

def header_font(bold=True, size=11, color="FFFFFF"):
    return Font(name="Calibri", bold=bold, size=size, color=color)

def body_font(bold=False, size=10, color="000000"):
    return Font(name="Calibri", bold=bold, size=size, color=color)

def fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def thin_border():
    side = Side(style="thin")
    return Border(left=side, right=side, top=side, bottom=side)

def center_align():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)

def right_align():
    return Alignment(horizontal="right", vertical="center")

def left_align():
    return Alignment(horizontal="left", vertical="center", wrap_text=True)

CURRENCY_FMT = '#,##0.00'
NUMBER_FMT = '#,##0.000'
WEIGHT_FMT = '#,##0.0000'


class ExcelGenerator:

    def generate(
        self,
        job_data: Dict[str, Any],
        costing_result: Dict[str, Any],
        rates: Dict[str, Any],
    ) -> bytes:
        """Generate the full job costing workbook and return as bytes."""
        wb = Workbook()

        # Remove default sheet
        wb.remove(wb.active)

        # Create sheets
        self._create_cover_sheet(wb, job_data)
        self._create_costing_sheet(wb, job_data, costing_result, rates)
        self._create_rates_sheet(wb, rates)
        self._create_audit_sheet(wb, costing_result.get("audit_trail", []))

        # Save to bytes
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()

    def _create_cover_sheet(self, wb: Workbook, job: Dict):
        ws = wb.create_sheet("JOB SUMMARY")
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 45
        ws.column_dimensions["C"].width = 20
        ws.column_dimensions["D"].width = 20

        # Title banner
        ws.merge_cells("A1:D1")
        ws["A1"] = "JOB COST ESTIMATION SHEET"
        ws["A1"].font = Font(name="Calibri", bold=True, size=16, color=WHITE)
        ws["A1"].fill = fill(NAVY)
        ws["A1"].alignment = center_align()
        ws.row_dimensions[1].height = 35

        ws.merge_cells("A2:D2")
        ws["A2"] = f"Generated: {datetime.now().strftime('%d %B %Y %H:%M')}"
        ws["A2"].font = body_font(size=9, color="666666")
        ws["A2"].alignment = center_align()
        ws["A2"].fill = fill(LIGHT_BLUE)

        # Job info rows
        def info_row(row, label, value, val_fill=WHITE):
            ws[f"A{row}"] = label
            ws[f"A{row}"].font = body_font(bold=True)
            ws[f"A{row}"].fill = fill(LIGHT_GREY)
            ws[f"A{row}"].border = thin_border()
            ws[f"A{row}"].alignment = left_align()
            ws.merge_cells(f"B{row}:D{row}")
            ws[f"B{row}"] = value
            ws[f"B{row}"].font = body_font()
            ws[f"B{row}"].fill = fill(val_fill)
            ws[f"B{row}"].border = thin_border()
            ws[f"B{row}"].alignment = left_align()
            ws.row_dimensions[row].height = 20

        info_row(4, "Job Number", job.get("job_number", ""))
        info_row(5, "Client", job.get("client_name", ""))
        info_row(6, "Project", job.get("project_name", ""))
        info_row(7, "Reference", job.get("project_ref", ""))
        info_row(8, "Currency", job.get("currency", "AED"))
        info_row(9, "Prepared By", "Cost Estimator AI Agent")
        info_row(10, "Date", datetime.now().strftime("%d-%b-%Y"))

        # Summary financials
        ws.merge_cells("A12:D12")
        ws["A12"] = "COST SUMMARY"
        ws["A12"].font = header_font(color="000000", size=12)
        ws["A12"].fill = fill(LIGHT_BLUE)
        ws["A12"].alignment = center_align()
        ws.row_dimensions[12].height = 25

        # Write actual values from costing result
        cr = job.get("_costing_result", {})
        summary_vals = [
            ("Total Weight (kg)", cr.get("total_weight_kg", 0)),
            ("Total Material Cost", cr.get("total_material_cost", 0)),
            ("Total Fabrication Cost", cr.get("total_fabrication_cost", 0)),
            ("Total Welding Cost", cr.get("total_welding_cost", 0)),
            ("Total Consumables", cr.get("total_consumables_cost", 0)),
            ("Total Cutting Cost", cr.get("total_cutting_cost", 0)),
            ("Total Surface Treatment", cr.get("total_surface_treatment_cost", 0)),
            ("Total Direct Cost", cr.get("total_direct_cost", 0)),
            (f"Overhead ({cr.get('overhead_percentage', 15)}%)", cr.get("overhead_cost", 0)),
            ("Total Cost incl. Overhead", cr.get("total_direct_cost", 0) + cr.get("overhead_cost", 0)),
            (f"Profit Margin ({cr.get('profit_margin_percentage', 12)}%)", cr.get("profit_amount", 0)),
            ("SELLING PRICE", cr.get("selling_price", 0)),
        ]

        for i, (label, value) in enumerate(summary_vals):
            row = 13 + i
            ws[f"A{row}"] = label
            ws[f"A{row}"].font = body_font(bold=(label == "SELLING PRICE"))
            ws[f"A{row}"].fill = fill(ORANGE if label == "SELLING PRICE" else WHITE)
            ws[f"A{row}"].border = thin_border()
            ws[f"A{row}"].alignment = left_align()
            ws.merge_cells(f"B{row}:C{row}")
            ws[f"B{row}"] = value
            ws[f"B{row}"].font = body_font(bold=(label == "SELLING PRICE"), size=11 if label == "SELLING PRICE" else 10)
            ws[f"B{row}"].fill = fill(ORANGE if label == "SELLING PRICE" else WHITE)
            ws[f"B{row}"].border = thin_border()
            ws[f"B{row}"].number_format = CURRENCY_FMT
            ws[f"B{row}"].alignment = right_align()
            ws[f"D{row}"] = job.get("currency", "AED")
            ws[f"D{row}"].font = body_font()
            ws[f"D{row}"].border = thin_border()
            ws[f"D{row}"].alignment = center_align()
            ws.row_dimensions[row].height = 20

    def _create_costing_sheet(self, wb: Workbook, job: Dict, cr: Dict, rates: Dict):
        ws = wb.create_sheet("JOB COSTING")
        ws.sheet_view.showGridLines = False

        # Column widths matching sample structure (20 columns: A-T)
        col_widths = {
            "A": 8, "B": 50, "C": 8, "D": 8, "E": 8, "F": 8, "G": 10, "H": 8, "I": 10, "J": 10,
            "K": 12, "L": 12, "M": 10, "N": 8, "O": 10, "P": 12, "Q": 12, "R": 8, "S": 8, "T": 8
        }
        for col, w in col_widths.items():
            ws.column_dimensions[col].width = w

        # ─── HEADER AREA (Rows 1-13) ──────────────────────────────────────────
        # Company name
        ws.merge_cells("A1:T1")
        ws["A1"] = "C&J GULF EQUIPMENT MANUFACTURING L.L.C"
        ws["A1"].font = header_font(size=14, color="000000", bold=True)
        ws["A1"].alignment = center_align()

        # Job Costing Sheet title
        ws.merge_cells("E2:J2")
        ws["E2"] = "Job Costing Sheet"
        ws["E2"].font = header_font(size=12, color="000000", bold=True)
        ws["E2"].alignment = center_align()

        # REF NO
        ws.merge_cells("A3:D3")
        ws["A3"] = f"REF NO: {job.get('job_number', 'CNJ/XXXXXX/01/2026')}"
        ws["A3"].font = body_font(bold=True)
        ws["A3"].alignment = left_align()

        # Customer details
        ws["A4"] = "CUSTOMER NAME"
        ws.merge_cells("B4:D4")
        ws["B4"] = job.get("client_name", "")
        ws["E4"] = "DATE"
        ws.merge_cells("F4:H4")
        ws["F4"] = datetime.now().strftime("%Y-%m-%d")
        ws["I4"] = "ENQUIRY No"
        ws.merge_cells("J4:L4")
        ws["J4"] = job.get("project_ref", "")

        ws["A5"] = "CUSTOMER CODE"
        ws.merge_cells("B5:D5")
        ws["B5"] = ""
        ws["E5"] = "ATTENTION OF"
        ws.merge_cells("F5:H5")
        ws["F5"] = ""
        ws["I5"] = "JOB NO."
        ws.merge_cells("J5:L5")
        ws["J5"] = job.get("job_number", "")

        ws["A6"] = "EMAIL"
        ws.merge_cells("B6:D6")
        ws["B6"] = ""
        ws["E6"] = "CONTACT NO:"
        ws.merge_cells("F6:H6")
        ws["F6"] = ""
        ws["I6"] = "JORL DATE:"
        ws.merge_cells("J6:L6")
        ws["J6"] = ""

        ws["A7"] = "PROJECT PACKAGE DETAILS"
        ws.merge_cells("B7:D7")
        ws["B7"] = job.get("project_name", "")
        ws["E7"] = "MODULE WORK"
        ws["F7"] = "X" if "module" in job.get("project_name", "").lower() else ""
        ws["G7"] = "SKID MOUNTED PACKAGE"
        ws.merge_cells("H7:J7")
        ws["H7"] = ""
        ws["K7"] = "CEMENT LINING"
        ws.merge_cells("L7:N7")
        ws["L7"] = ""

        # Empty rows
        for row in [8, 9, 10, 11, 12]:
            pass

        # CUSTOMER P.O. Ref
        ws["A9"] = "CUSTOMER P.O. Ref :"
        ws.merge_cells("B9:D9")
        ws["B9"] = ""

        # SALES EMPLOYEE CODE
        ws["A10"] = " SALES EMPOLOYEE CODE"
        ws.merge_cells("B10:D10")
        ws["B10"] = ""

        # NETSUITE fields
        ws["A11"] = "NETSUITE INVOICE NO:"
        ws.merge_cells("B11:D11")
        ws["B11"] = ""
        ws["E11"] = "NETSUITE AGEING REPORT:"
        ws.merge_cells("F11:H11")
        ws["F11"] = ""

        # PENDING PAYMENT
        ws["A12"] = "PENDING PAYMENT"
        ws.merge_cells("B12:D12")
        ws["B12"] = ""

        # Section headers
        ws.merge_cells("F13:L13")
        ws["F13"] = "COST AT OFFER ACCEPTANCE AS PER ESTIMATION"
        ws["F13"].font = header_font(size=10, color="000000", bold=True)
        ws["F13"].alignment = center_align()
        ws["F13"].fill = fill(LIGHT_BLUE)

        ws.merge_cells("M13:R13")
        ws["M13"] = "ACTUAL MANUFACTURING COST"
        ws["M13"].font = header_font(size=10, color="000000", bold=True)
        ws["M13"].alignment = center_align()
        ws["M13"].fill = fill(LIGHT_BLUE)

        # ─── TABLE HEADERS (Row 14) ───────────────────────────────────────────
        headers = [
            "Sr No", "Item Description", "", "", "", "", "Qty", "Unit", "Manhours", "Unit cost", "Total cost", "Remarks",
            "Qty", "Unit", "Unit cost", "Total cost", "Remarks", "", "", ""
        ]
        header_row_idx = 14
        for col_idx, hdr in enumerate(headers, start=1):
            cell = ws.cell(row=header_row_idx, column=col_idx, value=hdr)
            cell.font = header_font(size=9, color=WHITE)
            cell.fill = fill(NAVY)
            cell.alignment = center_align()
            cell.border = thin_border()
        
        ws.merge_cells("B14:F14") # Merge description columns
        ws.merge_cells("M14:Q14") # Merge right side description
        ws.row_dimensions[header_row_idx].height = 25

        # ─── DATA ROWS ───────────────────────────────────────────────────────
        current_row = 15

        # Section 1: Design & Drafting
        design_items = [
            ("1", "Design, Drafting & Drawing Charges", 0, "lot", "", "", "", "", "", ""),
            ("1.1", "Gaps in customer design", 0, "lot", "", "", "", "", "", ""),
            ("2", "BOM/BOQ Preparation", 0, "lot", "", "", "", "", "", ""),
            ("2.1", "Changes in BOM due to Design change", 0, "lot", "", "", "", "", "", ""),
            ("3", "Technical recommendations to customer", 0, "lot", "", "", "", "", "", ""),
            ("4", "Gaps in our estimation", 0, "lot", "", "", "", "", "", ""),
        ]
        
        for sr, desc, qty, unit, *extra in design_items:
            ws[f"A{current_row}"] = sr
            ws.merge_cells(f"B{current_row}:F{current_row}")
            ws[f"B{current_row}"] = desc
            ws[f"G{current_row}"] = qty
            ws[f"H{current_row}"] = unit
            ws[f"K{current_row}"] = f"=G{current_row}*J{current_row}"
            for c in range(1, 21):
                ws.cell(row=current_row, column=c).border = thin_border()
            current_row += 1

        # Section 5: Material Cost
        ws[f"A{current_row}"] = "5"
        ws.merge_cells(f"B{current_row}:F{current_row}")
        ws[f"B{current_row}"] = "Material Cost"
        ws[f"B{current_row}"].font = body_font(bold=True)
        current_row += 1

        # Dynamic material items from costing result
        line_items = cr.get("line_items", [])
        mat_start = current_row
        for i, item in enumerate(line_items):
            ws[f"A{current_row}"] = f"5.{i+1}"
            ws.merge_cells(f"B{current_row}:F{current_row}")
            ws[f"B{current_row}"] = f"{item.get('description','')} ({item.get('section_type','')})"
            ws[f"G{current_row}"] = item.get("weight_kg", 0)
            ws[f"H{current_row}"] = "Kg"
            ws[f"J{current_row}"] = rates.get("material_rate_per_kg", 4.0)
            ws[f"K{current_row}"] = f"=G{current_row}*J{current_row}"
            
            # Right side - Actual manufacturing cost (same as estimation for material)
            ws[f"M{current_row}"] = item.get("weight_kg", 0)
            ws[f"N{current_row}"] = "Kg"
            ws[f"O{current_row}"] = rates.get("material_rate_per_kg", 4.0)
            ws[f"P{current_row}"] = f"=M{current_row}*O{current_row}"
            
            for c in range(1, 21):
                ws.cell(row=current_row, column=c).border = thin_border()
            current_row += 1
        mat_end = current_row - 1

        # Section 6: Material Inspection Charges
        ws[f"A{current_row}"] = "6"
        ws.merge_cells(f"B{current_row}:F{current_row}")
        ws[f"B{current_row}"] = "Material Inspection Charges"
        ws[f"G{current_row}"] = 0
        ws[f"H{current_row}"] = "lot"
        ws[f"K{current_row}"] = f"=G{current_row}*J{current_row}"
        for c in range(1, 21):
            ws.cell(row=current_row, column=c).border = thin_border()
        current_row += 1

        # Empty row
        current_row += 1

        # Section 7: Labour & Fabrication Cost
        ws[f"A{current_row}"] = "7"
        ws.merge_cells(f"B{current_row}:F{current_row}")
        ws[f"B{current_row}"] = "Labour & Fabrication Cost"
        ws[f"B{current_row}"].font = body_font(bold=True)
        current_row += 1

        # Fabrication sub-items
        fab_items = [
            ("7.1", f"Structural Welding considering {cr.get('total_welding_manhours', 0):.1f} labor hours", cr.get("total_weight_kg", 0), "Kg", cr.get("total_welding_manhours", 0), rates.get("welding_hourly_rate", 45.0)),
            ("7.2", f"Structural Fabrication considering {cr.get('total_manhours', 0):.1f} labor hours", cr.get("total_weight_kg", 0), "Kg", cr.get("total_manhours", 0), rates.get("fabrication_hourly_rate", 45.0)),
            ("7.3", "Hydrotesting", 0, "Inch Dia", 0, rates.get("fabrication_hourly_rate", 45.0)),
            ("7.4", "Machining 8 labour hours per day for 4 days", 0, "Kg", 32, rates.get("fabrication_hourly_rate", 45.0)),
        ]
        
        for sr, desc, qty, unit, manhours, rate in fab_items:
            ws[f"A{current_row}"] = sr
            ws.merge_cells(f"B{current_row}:F{current_row}")
            ws[f"B{current_row}"] = desc
            ws[f"G{current_row}"] = qty
            ws[f"H{current_row}"] = unit
            ws[f"I{current_row}"] = manhours
            ws[f"J{current_row}"] = rate
            ws[f"K{current_row}"] = f"=I{current_row}*J{current_row}"
            
            # Right side - same for now
            ws[f"M{current_row}"] = qty
            ws[f"N{current_row}"] = unit
            ws[f"O{current_row}"] = rate
            ws[f"P{current_row}"] = f"=M{current_row}*O{current_row}"
            
            for c in range(1, 21):
                ws.cell(row=current_row, column=c).border = thin_border()
            current_row += 1

        # Section 8: Consumables
        ws[f"A{current_row}"] = "8"
        ws.merge_cells(f"B{current_row}:F{current_row}")
        ws[f"B{current_row}"] = "Consumables"
        ws[f"G{current_row}"] = 1
        ws[f"H{current_row}"] = "lot"
        ws[f"J{current_row}"] = cr.get("total_consumables_cost", 0)
        ws[f"K{current_row}"] = f"=G{current_row}*J{current_row}"
        for c in range(1, 21):
            ws.cell(row=current_row, column=c).border = thin_border()
        current_row += 1

        # Additional sections from sample
        additional_sections = [
            ("9", "Subcontractor Costing", 0, "lot", "", ""),
            ("9.1", "Machining & Threading", 0, "Pcs", "", ""),
            ("10", "Testing & Quality Control", "", "", "", ""),
            ("10.1", "10% MPI/DPT", 10, "Visits", "", 600),
            ("11", "Surface Preparation & Coating", "", "", "", ""),
            ("11.1", "Galvanizing Work", 0, "Kg", "", 2000),
            ("11.2", f"Blasting ({cr.get('total_surface_area_m2', 0):.1f} Sq M)", cr.get("total_surface_area_m2", 0), "SQM", f"=1/13.3*G{current_row+1}*3", rates.get("surface_treatment_rate_per_m2", 55.0)),
            ("11.3", f"Painting ({cr.get('total_surface_area_m2', 0):.1f} Sq M for 2 coat paint system)", cr.get("total_surface_area_m2", 0), "SQM", f"=1/6.65*G{current_row+2}*3", rates.get("surface_treatment_rate_per_m2", 55.0)),
            ("12", "Third-Party Inspection (TPI)", 0, "lot", "", ""),
            ("13", "QA/QC Documentation & Certification", 1, "lot", "", 3000),
            ("14", "Packing and loading", 1, "Lot", "", 3000),
            ("16", "Insurance", 0, "lot", "", ""),
            ("17", "Permits, Licenses & Regulatory Fees", 0, "Nos", "", ""),
            ("18", "Equipment Rental & Maintenance", 0, "lot", "", ""),
            ("20", "Contingency Fund", 0, "lot", "", ""),
            ("21", "Taxes & Duties", 0, "lot", "", ""),
            ("22", "Warranty & Guarantee Costs", 0, "lot", "", ""),
            ("23", "Project Management Fees", 0, "lot", "", ""),
            ("24", "Environmental Compliance Costs", 0, "lot", "", ""),
            ("25", "Training & Certification", 0, "lot", "", ""),
            ("26", "Marketing & Sales Costs", 0, "lot", "", ""),
        ]

        for sr, desc, qty, unit, manhours, rate in additional_sections:
            ws[f"A{current_row}"] = sr
            ws.merge_cells(f"B{current_row}:F{current_row}")
            ws[f"B{current_row}"] = desc
            ws[f"G{current_row}"] = qty
            ws[f"H{current_row}"] = unit
            if manhours:
                ws[f"I{current_row}"] = manhours
            if rate:
                ws[f"J{current_row}"] = rate
            ws[f"K{current_row}"] = f"=G{current_row}*J{current_row}" if qty and rate else ""
            for c in range(1, 21):
                ws.cell(row=current_row, column=c).border = thin_border()
            current_row += 1

        # ─── TOTALS ───────────────────────────────────────────────────────────
        current_row += 1
        ws[f"B{current_row}"] = "Total cost"
        ws[f"D{current_row}"] = f"=SUM(K15:K{current_row-1})"
        ws[f"D{current_row}"].font = header_font(color="000000", bold=True)
        ws[f"D{current_row}"].fill = fill(YELLOW)
        ws[f"S{current_row}"] = f"=SUM(P15:P{current_row-1})"  # Sum of right side totals

        current_row += 1
        ws[f"B{current_row}"] = "19.Overheads"
        ws[f"D{current_row}"] = f"=S{current_row-1}"  # Use right side total for overheads
        ws[f"D{current_row}"].font = body_font(bold=True)

        current_row += 1
        ws[f"B{current_row}"] = "GRAND TOTAL"
        ws[f"D{current_row}"] = f"=D{current_row-2}+D{current_row-1}"
        ws[f"D{current_row}"].font = header_font(color="000000", bold=True)
        ws[f"D{current_row}"].fill = fill(GREEN)

        current_row += 1
        ws[f"B{current_row}"] = "Selling Price"
        ws[f"D{current_row}"] = cr.get("selling_price", 0)
        ws[f"D{current_row}"].font = header_font(color="000000", bold=True)
        ws[f"D{current_row}"].fill = fill(ORANGE)

        current_row += 1
        ws[f"B{current_row}"] = "Net Profit"
        ws[f"D{current_row}"] = f"=D{current_row-1}-D{current_row-2}"
        ws[f"D{current_row}"].font = body_font(bold=True)

        # Profit margin calculation
        current_row += 1
        ws[f"B{current_row}"] = f"=D{current_row-1}/D{current_row-2}"

        # Signatures
        current_row += 2
        ws[f"F{current_row}"] = "ESTIMATION ENGR."
        ws[f"H{current_row}"] = "Sachin Ahire"
        ws[f"L{current_row}"] = "PLANNING ENGR."
        ws[f"N{current_row}"] = "Sachin Ahire"

        current_row += 1
        ws[f"F{current_row}"] = "MANAGER:"
        ws[f"H{current_row}"] = "Subash Valrani"
        ws[f"L{current_row}"] = "MANAGER:"
        ws[f"N{current_row}"] = "Subash Valrani"

        current_row += 1
        ws[f"L{current_row}"] = "ACCOUNTANT:"
        ws[f"N{current_row}"] = "Zeeshan"

        # Apply number formats
        for row in range(15, current_row + 1):
            for col in ["D", "K", "P"]:
                if ws[f"{col}{row}"].value:
                    ws[f"{col}{row}"].number_format = CURRENCY_FMT
            for col in ["G", "I", "M"]:
                if ws[f"{col}{row}"].value:
                    ws[f"{col}{row}"].number_format = NUMBER_FMT

    def _create_rates_sheet(self, wb: Workbook, rates: Dict):
        ws = wb.create_sheet("RATES & CONFIG")
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["A"].width = 35
        ws.column_dimensions["B"].width = 15
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 30

        ws.merge_cells("A1:D1")
        ws["A1"] = "RATE CONFIGURATION (Snapshot at time of calculation)"
        ws["A1"].font = header_font(size=12)
        ws["A1"].fill = fill(NAVY)
        ws["A1"].alignment = center_align()
        ws.row_dimensions[1].height = 30

        headers = ["Parameter", "Value", "Unit", "Description"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col, value=h)
            cell.font = header_font(color=WHITE, size=10)
            cell.fill = fill(NAVY)
            cell.border = thin_border()
            cell.alignment = center_align()
        ws.row_dimensions[3].height = 22

        rate_descriptions = {
            "material_rate_per_kg": ("Material Rate", "AED/kg", "Steel material rate per kg"),
            "fabrication_rate_per_kg": ("Fabrication Rate (weight)", "AED/kg", "Weight-based fabrication rate"),
            "fabrication_hourly_rate": ("Fabrication Hourly Rate", "AED/hr", "Manhour-based fabrication rate"),
            "manhour_factor_hr_per_kg": ("Manhour Factor", "hr/kg", "Fabrication manhours per kg of steel"),
            "welding_time_per_m_hr": ("Welding Time", "hr/m", "Welding manhours per meter of weld"),
            "welding_hourly_rate": ("Welding Hourly Rate", "AED/hr", "Welding labor rate"),
            "consumable_factor_kg_per_m": ("Consumable Factor", "kg/m", "Welding consumables per meter of weld"),
            "consumable_unit_rate": ("Consumable Unit Rate", "AED/kg", "Rate for welding consumables"),
            "cutting_rate_per_cut": ("Cutting Rate", "AED/cut", "Rate per cut/saw cut"),
            "surface_treatment_rate_per_m2": ("Surface Treatment Rate", "AED/m²", "Blast & prime or painting rate"),
            "overhead_percentage": ("Overhead %", "%", "Overhead percentage on direct cost"),
            "profit_margin_percentage": ("Profit Margin %", "%", "Net profit margin on total cost"),
            "steel_density_kg_m3": ("Steel Density", "kg/m³", "Default steel density"),
            "weld_length_per_joint_mm": ("Weld Length/Joint", "mm", "Default weld length per joint"),
        }

        for row_idx, (key, value) in enumerate(rates.items(), start=4):
            desc_tuple = rate_descriptions.get(key, (key, "", ""))
            row_fill = fill(LIGHT_GREY) if row_idx % 2 == 0 else fill(WHITE)
            ws.cell(row=row_idx, column=1, value=desc_tuple[0]).fill = row_fill
            ws.cell(row=row_idx, column=2, value=value).fill = row_fill
            ws.cell(row=row_idx, column=2).number_format = NUMBER_FMT
            ws.cell(row=row_idx, column=2).alignment = right_align()
            ws.cell(row=row_idx, column=3, value=desc_tuple[1]).fill = row_fill
            ws.cell(row=row_idx, column=4, value=desc_tuple[2]).fill = row_fill
            for col in range(1, 5):
                ws.cell(row=row_idx, column=col).border = thin_border()
                ws.cell(row=row_idx, column=col).font = body_font(size=9)
            ws.row_dimensions[row_idx].height = 18

    def _create_audit_sheet(self, wb: Workbook, audit_trail: List):
        ws = wb.create_sheet("AUDIT TRAIL")
        ws.sheet_view.showGridLines = False
        ws.column_dimensions["A"].width = 15
        ws.column_dimensions["B"].width = 15
        ws.column_dimensions["C"].width = 60

        ws.merge_cells("A1:C1")
        ws["A1"] = "CALCULATION AUDIT TRAIL"
        ws["A1"].font = header_font(size=12)
        ws["A1"].fill = fill(NAVY)
        ws["A1"].alignment = center_align()
        ws.row_dimensions[1].height = 30

        for col, h in enumerate(["Step / Item", "Status", "Details"], 1):
            cell = ws.cell(row=2, column=col, value=h)
            cell.font = header_font(color=WHITE, size=10)
            cell.fill = fill(NAVY)
            cell.border = thin_border()
            cell.alignment = center_align()

        for row_idx, entry in enumerate(audit_trail, start=3):
            status = entry.get("status", entry.get("step", ""))
            details = {k: v for k, v in entry.items() if k not in ("step", "status", "item_tag")}
            ws.cell(row=row_idx, column=1, value=entry.get("item_tag") or entry.get("step", "")).border = thin_border()
            ws.cell(row=row_idx, column=2, value=status).border = thin_border()
            ws.cell(row=row_idx, column=3, value=str(details)).border = thin_border()
            for col in range(1, 4):
                ws.cell(row=row_idx, column=col).font = body_font(size=9)
                ws.cell(row=row_idx, column=col).alignment = left_align()
            ws.row_dimensions[row_idx].height = 16


# Singleton
excel_generator = ExcelGenerator()
