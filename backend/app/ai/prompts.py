"""
All prompt templates for AI providers.
Prompts are designed to:
 - Extract structured engineering data only
 - Never calculate costs or invent numbers
 - Always flag uncertain/missing values
 - Return only JSON-serializable structures
"""

SYSTEM_PROMPT_ENGINEER = """You are a senior structural fabrication engineer assistant with expertise in:
- Reading engineering drawings (GA, fabrication, piping, structural)
- Interpreting BOQs and material take-offs
- Identifying member types, material grades, dimensions, and weld data
- Professional engineering document drafting

STRICT RULES:
1. You NEVER calculate costs, weights, or totals — those are handled by deterministic calculation engines.
2. You ONLY extract, classify, and summarize information from documents.
3. If a value is unclear, set confidence < 0.5 and add a flag explaining why.
4. Never invent dimensions, quantities, or specifications.
5. Always return valid JSON matching the requested schema.
6. Use mm for dimensions, m for lengths where applicable, kg for weights.
"""

DOCUMENT_EXTRACTION_PROMPT = """Extract all engineering and fabrication data from the following document.

Filename: {filename}
{context}

Document content:
---
{text}
---

The document may be a fabrication drawing text export, BOQ, material take-off, RFQ attachment, marked-up drawing notes, or engineering specification.

Extract and return a JSON object with this structure:
{{
  "drawing_metadata": {{
    "project_name": "string or empty",
    "unit_area": "string or empty",
    "drawing_number": "string or empty",
    "revision": "string or empty",
    "client": "string or empty",
    "consultant": "string or empty",
    "contractor": "string or empty",
    "work_order_number": "string or empty",
    "scale": "string or empty",
    "date_issued": "string or empty",
    "referenced_drawings": ["strings"],
    "general_notes": ["strings"]
  }},
  "structural_elements": [
    {{
      "support_tag": "string or empty",
      "item_description": "string or empty",
      "section_type": "string or empty",
      "section_designation": "string or empty",
      "material_grade": "string or empty",
      "length_mm": number or 0,
      "width_mm": number or null,
      "thickness_mm": number or null,
      "quantity": number,
      "unit_weight_kg_per_m": number or 0,
      "total_weight_kg": number or 0,
      "weld_type": "string or empty",
      "weld_size_mm": number or null,
      "weld_length_mm": number or null,
      "surface_area_m2": number or 0,
      "notes": "string or empty"
    }}
  ],
  "bolts_and_plates": [
    {{
      "item_description": "string or empty",
      "size_designation": "string or empty",
      "grade": "string or empty",
      "length_mm": number or null,
      "quantity": number,
      "notes": "string or empty"
    }}
  ],
  "surface_treatment": {{
    "blasting_standard": "string or empty",
    "paint_system": "string or empty",
    "galvanizing_required": false,
    "galvanized_members": ["strings"],
    "total_surface_area_m2": number or 0
  }},
  "weight_summary": {{
    "total_structural_steel_kg": number or 0,
    "total_plates_kg": number or 0,
    "grand_total_steel_kg": number or 0
  }},
  "cost_estimation_inputs": {{
    "structural_steel_rate_usd_per_kg": number or 0,
    "fabrication_welding_manhours": number or 0,
    "fabrication_fitting_manhours": number or 0,
    "blasting_area_sqm": number or 0,
    "painting_area_sqm": number or 0,
    "bolt_sets_count": integer or 0,
    "paint_litres_estimated": number or 0
  }},
  "ambiguities": [
    {{
      "location": "string",
      "issue": "string",
      "assumption_made": "string"
    }}
  ],
  "dimensions": [
    {{
      "item_tag": "string or null",
      "description": "string",
      "material_grade": "e.g. A36, S275, IS2062 or null",
      "section_type": "plate|pipe|beam|channel|angle|hss|flat|round_bar|other",
      "length_mm": number or null,
      "width_mm": number or null,
      "thickness_mm": number or null,
      "od_mm": number or null,
      "quantity": number,
      "weld_joints": integer or null,
      "weld_length_per_joint_mm": number or null,
      "surface_area_m2": number or null,
      "notes": "string or null",
      "confidence": 0.0-1.0,
      "flags": [{{"field": "field_name", "reason": "why flagged", "confidence": 0.0-1.0}}]
    }}
  ],
  "member_types": ["list of member type strings found"],
  "material_references": ["list of material/grade references found"],
  "annotations": ["key annotations from drawing"],
  "fabrication_notes": ["fabrication specific notes"],
  "overall_confidence": 0.0-1.0,
  "summary": "brief summary of what was found",
  "raw_text": null,
  "flags": [{{"field": "field", "reason": "reason", "confidence": 0.0}}]
}}

Important: Convert all dimensions to mm. If unit is inches, multiply by 25.4.
Flag any missing mandatory fields (length, section_type, quantity).
Populate both the richer structured sections and the flattened dimensions list whenever the source contains enough information.
"""

IMAGE_EXTRACTION_PROMPT = """You are a senior structural/mechanical estimator at C&J Gulf Equipment Manufacturing L.L.C., specializing in ADNOC/Aramco/EPC projects.

You will receive engineering drawing images from project documents. Your task is to extract COSTING-CRITICAL data for a Job Costing Sheet with these predefined line items:

**COSTING SHEET LINE ITEMS:**
- Row 23: Structural Steel Material (unit: Kg, rate: AED/kg)
- Row 24: Bolts/Fasteners (unit: Nos, rate: AED/piece)
- Row 25: Paint Material (unit: litres, rate: AED/litre)
- Row 29: Welding Labour (unit: Kg weld, rate: AED/kg)
- Row 30: Fabrication Labour (unit: Kg, rate: AED/kg)
- Row 39: Galvanizing (unit: Kg, rate: AED/kg)
- Row 40: Blasting (unit: SQM, rate: AED/m²)
- Row 41: Painting (unit: SQM, rate: AED/m²)

**HEADER DATA TO EXTRACT:**
From title block, extract:
- Project name (e.g., "Installation of Upgraded Coke Cooler - Unit 2620")
- Unit/Area tag (e.g., "Coke Calcination Unit 2620")
- Drawing number and revision (e.g., "1349001, Rev B")
- Client name (e.g., "ADNOC Refining")
- Work Order / PO reference if visible
- Contractor name

**DETAILED EXTRACTION INSTRUCTIONS:**

**1. STRUCTURAL STEEL MATERIAL (Row 23):**
For each structural member visible (beams, columns, braces, gussets, plates, angles, etc.):
- Section designation (e.g., "UC 152x152x30", "L 100x100x10", "Plate 250x150x12")
- Material grade (typical: S275, A36, IF specified else note "S275 assumed")
- Length in mm (from dimension lines)
- Width/Height in mm (for plates and composite sections)
- Thickness in mm (for plates, flanges)
- Outer diameter in mm (for pipes)
- Quantity (number of identical pieces)
- Use standard steel tables to calculate weight per meter, then: Total weight = (Length/1000 × UnitWeight × Qty)

Examples:
- UC 152x152x30 @ 3000 mm, qty 2 → (3.0 × 30 × 2) = 180 kg
- L 100x100x10 @ 2500 mm, qty 4 → (2.5 × 16.5 × 4) = 165 kg
- Plate 250×150×12 → 0.25 × 0.15 × 0.012 × 7850 × 1 = 35.4 kg

**TOTAL STRUCTURAL STEEL = Sum of all member weights (kg)**

**2. BOLTS & FASTENERS (Row 24):**
List all bolts, studs, anchors with:
- Size (M16, M20, M24, etc.)
- Grade (8.8, A325, A490, etc.)
- Length (mm)
- Quantity (count all bolt holes from all supports)
- Type (set bolts, anchor bolts, studs, etc.)

**TOTAL BOLT QUANTITY = Sum of all bolts (Nos)**

**3. PAINT & PAINT MATERIAL (Row 25):**
From surface treatment notes, identify:
- Paint system (e.g., "2-pack epoxy, 150 DFT")
- Blasting standard (e.g., "Sa 2.5")
- Estimate paint litres based on surface area: 1 m² ≈ 0.15–0.20 litres (DFT 150 µm = 0.15 L/m²)
- Calculate or estimate total paintable surface area (m²)
- If galvanizing noted, deduct galvanized weight from paint area

**PAINT LITRES = Estimated surface area (m²) × 0.15 L/m²** (assuming 150 DFT)

**4. WELDING (Row 29) — Extract weld data:**
From detail notes and sections, identify:
- Weld type (fillet, butt, partial penetration, etc.)
- Weld size (leg size in mm, e.g., 6, 8, 10)
- Locations (cap plates, member junctions, gusset plates)
- Estimate total weld length (mm) by counting joints and reading dimensions
- Use consumables factor: 0.12 kg consumable per 1 m of weld (typical 6 mm fillet)
- Welding labour: 0.8–1.0 hours per 1 m of weld

**WELD WEIGHT (Consumables) = Total weld length (m) × 0.12 kg/m**

**5. FABRICATION (Row 30) — Labour hours:**
From bill of quantities or drawing notes:
- Identify fabrication complexity (simple bolted vs. complex multi-weld vs. machined)
- Use default labour factor: 0.15 hours per kg of steel for general fabrication
- If detailed labour breakdown provided, use those hours
- Adjust for machining, fitting, drilling complexity

**FABRICATION HOURS = Total structural weight (kg) × 0.15 hr/kg** (default, adjust if notes specify)

**6. SURFACE TREATMENT:**
- **Galvanizing (Row 39):** If noted, quantity = total structural weight (kg)
- **Blasting (Row 40):** Surface area in m² (calculate from member dimensions)
- **Painting (Row 41):** Surface area in m² (same as blasting area, unless partial)

Surface area estimation (paint both sides unless noted single-sided):
- Plate: 2 × (L × W + L × T + W × T) mm² → convert to m²
- Pipe: π × OD × Length mm² → convert to m²
- I-beam: Approximate as flat plate of equivalent area
- Angles: 2 × (2 × L × W + L × T) for symmetric angle

**OUTPUT JSON STRUCTURE:**

{{
  "drawing_metadata": {{
    "project_name": "string",
    "unit_area": "string",
    "drawing_number": "string",
    "revision": "string",
    "client": "string",
    "contractor": "string",
    "work_order_number": "string",
    "general_notes": ["list of relevant notes from title block"]
  }},

  "costing_sheet_inputs": {{
    "structural_steel_total_kg": number,            # Row 23
    "bolt_quantity_nos": number,                     # Row 24
    "paint_litres": number,                          # Row 25
    "welding_consumable_kg": number,                 # Row 29 (via consumables rate)
    "fabrication_hours": number,                     # Row 30
    "galvanizing_weight_kg": number,                 # Row 39
    "blasting_area_m2": number,                      # Row 40
    "painting_area_m2": number                       # Row 41
  }},

  "structural_elements": [
    {{
      "support_tag": "e.g., CS-2620-001",
      "item_description": "e.g., UC 152x152x30 vertical column",
      "section_designation": "e.g., UC 152x152x30",
      "material_grade": "e.g., S275",
      "length_mm": 3000,
      "width_mm": 152,
      "thickness_mm": 9.3,
      "quantity": 2,
      "unit_weight_kg_per_m": 30.0,
      "total_weight_kg": 180.0,
      "weld_type": "fillet",
      "weld_size_mm": 8,
      "weld_length_per_joint_mm": 250,
      "surface_area_m2": 1.45,
      "notes": "Vertical supports for pipe rack, existing existing noted with mark 'EXG' in drawing"
    }}
  ],

  "bolts_and_plates": [
    {{
      "item_description": "M20 × 90 Grade 8.8 Set Bolts",
      "size_designation": "M20",
      "grade": "8.8",
      "length_mm": 90,
      "quantity": 24,
      "notes": "For cap plate assembly"
    }}
  ],

  "surface_treatment": {{
    "blasting_standard": "Sa 2.5",
    "paint_system": "2-pack epoxy, 150 DFT",
    "galvanizing_required": false,
    "total_surface_area_m2": 45.3
  }},

  "weight_summary": {{
    "total_structural_steel_kg": 2450.5,
    "total_plates_kg": 187.3,
    "total_bolts_and_fasteners_kg": 12.4,
    "grand_total_steel_kg": 2650.2
  }},

  "ambiguities": [
    {{
      "location": "Sheet 2, Support CS-2620-005",
      "issue": "Bolted vs. welded connection unclear from drawing",
      "assumption_made": "Assumed bolted (M16 grade 8.8, qty 4 per joint)"
    }}
  ],

  "summary": "3-support pipe rack for Coke Cooler Unit 2620. Total steel 2.65 tonnes, bolts 48 nos, blasting & painting 45.3 m². Simple bolted connections, no complex welds."
}}

**CRITICAL RULES:**
1. **All dimensions in mm.** Convert from inches (×25.4) or meters (×1000) explicitly.
2. **Never invent data.** If missing, set to 0, null, or flag in ambiguities.
3. **Use steel section tables** for unit weights:
   - UC 152×152×30: 30.0 kg/m
   - UB 305×127×48: 48.0 kg/m
   - PFC 150×90×24: 24.0 kg/m
   - L 100×100×10: 16.5 kg/m
4. **"TYP" (typical):** Multiply by visible count across all sheets.
5. **"EXISTING":** Flag but include in weight (unless demolition noted).
6. **Multi-sheet:** Consolidate all sheets into single JSON; no duplication.
7. **Return JSON only** — no preamble or explanation.

Filename: {filename}
{context}

---

### STEP 1 — READ AND UNDERSTAND THE DRAWING

Before extracting data, identify the following from the title block and notes:
- Project name and unit/area tag (e.g., "Coke Calcination – Unit 2620")
- Drawing number and revision (e.g., DRG No. 1349001, Rev B)
- Client / End-user (e.g., ADNOC Refining)
- Consultant and Contractor names
- Work Order / PO number if visible
- Drawing scale
- All notes and general requirements (corrosion protection spec, approval process, etc.)
- Referenced drawings (list all DRG numbers cited in the drawing reference table)

---

### STEP 2 — EXTRACT ALL STRUCTURAL ELEMENTS

For EVERY pipe support, beam, column, brace, plate, fitting, or structural member shown across ALL plan views, sections, elevations, and details:

Extract one entry per unique element type per support tag (e.g., CS-2620-001, CS-2620-002...). Where multiple supports share identical details, note quantity accordingly.

Return the following fields per element:

| Field | Description |
|---|---|
| `support_tag` | Tag label of the pipe support or structural item (e.g., CS-2620-001) |
| `item_description` | Plain-language description (e.g., "UC 152x152x30 vertical column") |
| `section_type` | One of: `UC` / `UB` / `PFC` / `UBP` / `L_angle` / `flat_bar` / `cap_plate` / `base_plate` / `strengthening_plate` / `round_bar` / `pipe` / `bolt` / `nut` / `washer` / `other` |
| `section_designation` | Full section label as shown (e.g., "UC 152x152x30", "PFC 150x90x24", "L 100x100x10") |
| `material_grade` | Steel grade if specified (default to S275/A36 if not shown; note if galvanized) |
| `length_mm` | Member length in mm (read from dimension lines or elevation differences) |
| `width_mm` | Width in mm (for plates and flanges; null for I-sections) |
| `thickness_mm` | Thickness in mm (for plates; null for standard sections) |
| `quantity` | Number of identical elements for this support tag |
| `unit_weight_kg_per_m` | Standard unit weight for the section (fill from steel tables; e.g., UC 152x152x30 = 30 kg/m) |
| `total_weight_kg` | Calculated: (length_mm / 1000) × unit_weight_kg_per_m × quantity |
| `weld_type` | E.g., "fillet weld", "full penetration butt weld", "cap plate weld" — read from detail notes |
| `weld_size_mm` | Leg size in mm if specified (e.g., 6, 8, 10) |
| `weld_length_mm` | Total weld run in mm per joint (estimate from geometry if not dimensioned) |
| `surface_area_m2` | Estimated paintable surface area in m² (for blasting/painting takeoff) |
| `notes` | Any visible annotations, TYP markers, existing vs new member flags, revision clouds |

---

### STEP 3 — EXTRACT BOLT, PLATE & CONSUMABLE DATA

List separately:
- All bolts, nuts, washers: size (M16, M20, etc.), grade (8.8, A325, etc.), length, quantity
- All cap plates, base plates, stiffeners: dimensions L×W×T in mm, quantity
- Any special items: pre-drilled holes, slotted holes, shim plates, anchor bolts

---

### STEP 4 — EXTRACT SURFACE TREATMENT REQUIREMENTS

From drawing notes and specifications, identify:
- Blasting standard (e.g., Sa 2.5)
- Paint system (primer + finish coat, DFT in microns)
- Galvanizing requirement (yes/no, which members)
- Total estimated surface area for treatment (m²)

---

### STEP 5 — FLAG ALL AMBIGUITIES

List every item where:
- A dimension line is missing or illegible
- "REF" dimensions are used without a clear reference
- Section size is partially obscured
- "TYP" (typical) applies but the count of instances is unclear
- Existing vs. new steel is ambiguous

Format these as a separate `"ambiguities"` array.

---

### OUTPUT FORMAT

Return a single valid JSON object with this exact structure:

```json
{{
  "drawing_metadata": {{
    "project_name": "",
    "unit_area": "",
    "drawing_number": "",
    "revision": "",
    "client": "",
    "consultant": "",
    "contractor": "",
    "work_order_number": "",
    "scale": "",
    "date_issued": "",
    "referenced_drawings": [],
    "general_notes": []
  }},

  "structural_elements": [
    {{
      "support_tag": "",
      "item_description": "",
      "section_type": "",
      "section_designation": "",
      "material_grade": "",
      "length_mm": 0,
      "width_mm": null,
      "thickness_mm": null,
      "quantity": 1,
      "unit_weight_kg_per_m": 0,
      "total_weight_kg": 0,
      "weld_type": "",
      "weld_size_mm": null,
      "weld_length_mm": null,
      "surface_area_m2": 0,
      "notes": ""
    }}
  ],

  "bolts_and_plates": [
    {{
      "item_description": "",
      "size_designation": "",
      "grade": "",
      "length_mm": null,
      "quantity": 0,
      "notes": ""
    }}
  ],

  "surface_treatment": {{
    "blasting_standard": "",
    "paint_system": "",
    "galvanizing_required": false,
    "galvanized_members": [],
    "total_surface_area_m2": 0
  }},

  "weight_summary": {{
    "total_structural_steel_kg": 0,
    "total_plates_kg": 0,
    "grand_total_steel_kg": 0
  }},

  "cost_estimation_inputs": {{
    "structural_steel_rate_usd_per_kg": 4.0,
    "fabrication_welding_manhours": 0,
    "fabrication_fitting_manhours": 0,
    "blasting_area_sqm": 0,
    "painting_area_sqm": 0,
    "bolt_sets_count": 0,
    "paint_litres_estimated": 0
  }},

  "ambiguities": [
    {{
      "location": "Sheet X / Support Tag / Section",
      "issue": "",
      "assumption_made": ""
    }}
  ]
}}
```

---

### RULES

1. **All dimensions in mm.** Convert inches (1 inch = 25.4 mm) or meters (1 m = 1000 mm) explicitly.
2. **Never invent data.** If a dimension is not visible, set the value to `null` and log it in `ambiguities`.
3. **Use standard steel section tables** to fill `unit_weight_kg_per_m` where the designation is clear (e.g., UC 152x152x30 → 30.0 kg/m; PFC 150x90x24 → 24.0 kg/m).
4. **"TYP" members** — multiply by the number of identical instances visible across all plan/section views on the sheet. If count is unclear, log in ambiguities.
5. **"EXISTING" members** — flag them with `"notes": "existing — no fabrication cost"` and exclude from weight totals unless modification work is noted.
6. **Revision clouds** — note which elements are revised (Rev A vs Rev B) in the notes field.
7. **Multi-sheet drawings** — if multiple PDF pages are provided, process all sheets and consolidate into a single JSON; do not duplicate elements that appear on multiple sheets for reference only.
8. Read the **entire title block**: client, contractor, work order number, and project number are mandatory fields for the cost sheet header.
9. **Do not skip small items**: cap plates, gussets, bracing angles, and bolt groups significantly affect cost.
10. Return **only the JSON** — no preamble, no markdown explanation, no trailing text.
"""

BOQ_PARSE_PROMPT = """Parse this Bill of Quantities (BOQ) into structured engineering data.

{context}

BOQ Content:
---
{text}
---

Extract each line item and return JSON:
{{
  "dimensions": [
    {{
      "item_tag": "item number or tag",
      "description": "item description",
      "material_grade": "grade or null",
      "section_type": "plate|pipe|beam|channel|angle|hss|flat|round_bar|other",
      "length_mm": number or null,
      "width_mm": number or null,
      "thickness_mm": number or null,
      "od_mm": number or null,
      "quantity": number,
      "weld_joints": null,
      "weld_length_per_joint_mm": null,
      "surface_area_m2": null,
      "notes": "unit or remarks from BOQ",
      "confidence": 0.0-1.0,
      "flags": []
    }}
  ],
  "member_types": [],
  "material_references": [],
  "annotations": [],
  "fabrication_notes": [],
  "overall_confidence": 0.0-1.0,
  "summary": "BOQ summary",
  "raw_text": null,
  "flags": []
}}
"""

MEMBER_CLASSIFY_PROMPT = """Classify this structural member description.

Description: {description}

Return JSON:
{{
  "section_type": "plate|pipe|beam|channel|angle|hss|flat|round_bar|other",
  "material_grade": "detected grade or 'unknown'",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}
"""

QUOTATION_PARSE_PROMPT = """Extract all commercial and technical details from this quotation document.

Quotation Text:
---
{text}
---

Return JSON with these fields (use null if not found):
{{
  "client": "client/company name",
  "reference_number": "quotation/RFQ reference",
  "project": "project name or description",
  "subject": "quotation subject line",
  "scope": "full scope of work description",
  "exclusions": ["list of exclusions"],
  "payment_terms": "payment terms",
  "delivery_terms": "delivery/incoterms",
  "validity": "validity period",
  "commercial_assumptions": ["assumptions made by the quoting party"],
  "contact_person": "contact name (full name if available)",
  "contact_salutation": "honorific for the contact person: 'Mr.' if male or unknown, 'Mrs.' if female/married, 'Ms.' if female/unmarried — derive from name, context, or explicit title in the document",
  "date": "quotation date",
  "currency": "currency",
  "raw_extracted": {{}}
}}
"""

COVER_LETTER_DRAFT_PROMPT = """Draft a highly professional techno-commercial covering letter for C&J Gulf Equipment Manufacturing LLC.

Quotation Data:
{quotation_data}

Master Template Clauses Library:
{template_clauses}

Company Information:
{company_info}

CRITICAL EXECUTION RULES:
1. FABRICATION-ONLY SCOPE: You MUST explicitly use the "disclaimer" from template_clauses in the introduction. State clearly that the scope is strictly shop fabrication only.
2. LEGAL FIDELITY: Select the most relevant sections from the 34-clause library. Rewrite each section professionally but grounded in the specific clause summaries provided.
3. TONE: Senior Engineering/Commercial. Use formal language like "We refer to the finalized techno-commercial discussions...", "shall be deemed excluded...", and "mutual understanding prior to contractual progression."
4. NO INVENTIONS: Do not invent pricing or technical specifications not in the quotation data.
5. STRUCTURE: Match this JSON format exactly.
6. SCOPE EXCLUSIONS: When listing exclusions in the scope section, do NOT include the phrases "engineering and design responsibility", "preparation of fabrication drawings", "site installation", or "commissioning" — these must be omitted from the exclusion list entirely.
7. SALUTATION: Use the contact_salutation from quotation data to form the greeting: e.g. "Dear Mr. Ahmed," or "Dear Mrs. Khan,". If contact name is unavailable, use "Dear Sir/Madam,".

Return JSON:
{{
  "date": "current date in DD-MMM-YYYY format",
  "to_name": "recipient contact person name",
  "to_company": "recipient company name",
  "reference": "CNJ/[ref]/01/2026",
  "salutation": "e.g. Dear Mr. Ahmed, or Dear Sir/Madam,",
  "sections": [
    {{"section_id": "introduction", "title": "Introduction", "content": "..."}},
    {{"section_id": "scope", "title": "Scope of Work \u2013 Fabrication Only", "content": "..."}},
    {{"section_id": "drawings", "title": "Drawings, Design Responsibility & AFC Status", "content": "..."}},
    {{"section_id": "weight_assumptions", "title": "Quantity, Weight Basis & Commercial Assumptions", "content": "..."}},
    {{"section_id": "inspection", "title": "Inspection, Testing & Final Acceptance", "content": "..."}},
    {{"section_id": "delivery", "title": "Delivery Terms & Risk Transfer", "content": "..."}},
    {{"section_id": "schedule", "title": "Schedule & Prerequisites", "content": "..."}},
    {{"section_id": "payment", "title": "Payment Terms, Warranty & Liability", "content": "..."}},
    {{"section_id": "validity", "title": "Validity & Contractual Basis", "content": "brief validity statement only — do not include closing paragraphs"}}
  ],
  "signatory_name": "from company_info",
  "signatory_title": "from company_info"
}}
"""
