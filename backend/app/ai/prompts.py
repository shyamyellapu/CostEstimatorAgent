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

IMAGE_EXTRACTION_PROMPT = """You are a senior structural/mechanical estimator at a UAE-based industrial fabrication company (C&J Gulf Equipment Manufacturing L.L.C.). You are highly experienced in reading ADNOC, Aramco, and EPC engineering drawings for structural steel, pipe supports, skid packages, and module work.

You will be given one or more engineering drawing images or PDF pages. Your task is to extract ALL quantifiable fabrication data visible in the drawings and return a structured JSON object that can be used to populate a Job Costing Sheet.

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
  "contact_person": "contact name",
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
2. LEGAL FIDELITY: Select the most relevant sections from the 34-clause library. For Each section ID (scope, exclusions, etc.), rewrite the content to be professional but grounded in the specific clause summaries provided.
3. TONE: Senior Engineering/Commercial. Use formal language like "We refer to the finalized techno-commercial discussions...", "shalt be deemed excluded...", and "mutual understanding prior to contractual progression."
4. NO INVENTIONS: Do not invent pricing or technical specifications not in the quotation data.
5. STRUCTURE: Match this JSON format exactly.

Return JSON:
{{
  "date": "current date in DD-MMM-YYYY format",
  "to_name": "recipient name",
  "to_company": "recipient company",
  "subject": "Re: Fabrication Quotation for [project name] - Ref: [quotation ref]",
  "reference": "CNJ/[ref]/01/2026",
  "sections": [
    {{"section_id": "introduction", "title": "Introduction", "content": "..."}},
    {{"section_id": "scope", "title": "Scope of Work – Fabrication Only", "content": "..."}},
    {{"section_id": "drawings", "title": "Drawings, Design Responsibility & AFC Status", "content": "..."}},
    {{"section_id": "weight_assumptions", "title": "Quantity, Weight Basis & Commercial Assumptions", "content": "..."}},
    {{"section_id": "inspection", "title": "Inspection, Testing & Final Acceptance", "content": "..."}},
    {{"section_id": "delivery", "title": "Delivery Terms & Risk Transfer", "content": "..."}},
    {{"section_id": "schedule", "title": "Schedule & Prerequisites", "content": "..."}},
    {{"section_id": "payment", "title": "Payment Terms, Warranty & Liability", "content": "..."}},
    {{"section_id": "validity", "title": "Validity & Contractual Basis", "content": "..."}}
  ],
  "closing": "Formal closing paragraph expressing appreciation for the opportunity.",
  "signatory_name": "from company_info",
  "signatory_title": "from company_info"
}}
"""
