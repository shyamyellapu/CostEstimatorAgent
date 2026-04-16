"""
Cover Letter Service — orchestrates quotation parsing → AI draft → PDF render pipeline.
REQUIRES quotation upload. Cannot generate without parsed quotation data.
"""
import logging
from typing import Dict, Any, Optional

from app.config import settings
from app.ai import get_ai_provider
from app.services.document_parser import get_file_text

logger = logging.getLogger(__name__)

from app.services.contract_clauses import CLAUSES, FABRICATION_ONLY_DISCLAIMER

class CoverLetterService:

    async def parse_quotation(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Extract structured data from uploaded quotation PDF."""
        text = get_file_text(file_bytes, filename)
        if not text.strip():
            raise ValueError("Could not extract text from quotation file. Ensure it is a text-based PDF.")

        ai = get_ai_provider()
        parsed = await ai.parse_quotation(text)
        logger.info(f"Quotation parsed: client={parsed.get('client')}, ref={parsed.get('reference_number')}")
        return parsed

    async def generate_draft(
        self,
        quotation_data: Dict[str, Any],
        company_info: Optional[Dict[str, str]] = None
    ):
        """Generate cover letter draft from quotation data using AI."""
        if not company_info:
            company_info = {
                "name": settings.company_name,
                "address": settings.company_address,
                "phone": settings.company_phone,
                "email": settings.company_email,
                "website": settings.company_website,
                "signatory_name": settings.signatory_name,
                "signatory_title": settings.signatory_title,
            }

        ai = get_ai_provider()
        draft = await ai.draft_cover_letter(
            quotation_data=quotation_data,
            template_clauses={"clauses": CLAUSES, "disclaimer": FABRICATION_ONLY_DISCLAIMER},
            company_info=company_info
        )
        return draft

    def render_pdf(self, draft_data: Dict[str, Any], company_info: Dict[str, str]) -> bytes:
        """Render cover letter draft to branded PDF using WeasyPrint."""
        from jinja2 import Environment, FileSystemLoader
        from pathlib import Path

        template_dir = Path(__file__).parent.parent / "templates" / "cover_letter"
        env = Environment(loader=FileSystemLoader(str(template_dir)))

        try:
            template = env.get_template("template.html")
        except Exception:
            # Fallback inline template
            template_str = self._get_inline_template()
            from jinja2 import Template
            template = Template(template_str)

        html = template.render(draft=draft_data, company=company_info)

        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html).write_pdf()
            return pdf_bytes
        except ImportError:
            # Fallback to reportlab if weasyprint not available
            return self._render_with_reportlab(draft_data, company_info)

    def _render_with_reportlab(self, draft: Dict, company: Dict) -> bytes:
        """Fallback PDF renderer using reportlab."""
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        # Custom styles
        title_style = ParagraphStyle("Title",
            parent=styles["Heading1"],
            fontSize=16, textColor=colors.HexColor("#1F3864"),
            spaceAfter=6)
        heading_style = ParagraphStyle("SectionHeading",
            parent=styles["Heading2"],
            fontSize=11, textColor=colors.HexColor("#1F3864"),
            spaceAfter=4, spaceBefore=10)
        body_style = ParagraphStyle("Body",
            parent=styles["Normal"],
            fontSize=10, leading=14, spaceAfter=4)
        bold_style = ParagraphStyle("Bold",
            parent=styles["Normal"],
            fontSize=10, leading=14, fontName="Helvetica-Bold")

        story = []

        # Header
        story.append(Paragraph(company.get("name", ""), title_style))
        story.append(Paragraph(company.get("address", ""), body_style))
        story.append(Paragraph(f"Tel: {company.get('phone', '')} | Email: {company.get('email', '')}", body_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1F3864")))
        story.append(Spacer(1, 0.3*cm))

        # Date & recipient
        story.append(Paragraph(draft.get("date", ""), body_style))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(draft.get("to_name", ""), bold_style))
        story.append(Paragraph(draft.get("to_company", ""), body_style))
        story.append(Spacer(1, 0.4*cm))

        # Reference & subject
        story.append(Paragraph(f"<b>Our Ref:</b> {draft.get('reference', '')}", body_style))
        story.append(Paragraph(f"<b>Subject:</b> {draft.get('subject', '')}", body_style))
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("Dear Sir/Madam,", body_style))
        story.append(Spacer(1, 0.3*cm))

        # Sections
        for section in draft.get("sections", []):
            story.append(Paragraph(section.get("title", ""), heading_style))
            content = section.get("content", "")
            for para in content.split("\n"):
                if para.strip():
                    story.append(Paragraph(para.strip(), body_style))

        # Closing
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(draft.get("closing", ""), body_style))
        story.append(Spacer(1, 0.8*cm))
        story.append(Paragraph("Yours faithfully,", body_style))
        story.append(Spacer(1, 0.8*cm))
        story.append(HRFlowable(width="5cm", thickness=1, color=colors.black))
        story.append(Paragraph(f"<b>{draft.get('signatory_name', company.get('signatory_name', ''))}</b>", bold_style))
        story.append(Paragraph(draft.get("signatory_title", company.get("signatory_title", "")), body_style))
        story.append(Paragraph(company.get("name", ""), body_style))

        doc.build(story)
        buf.seek(0)
        return buf.read()

    def _get_inline_template(self) -> str:
        return """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body { font-family: 'Arial', sans-serif; font-size: 10pt; color: #333; margin: 0; padding: 0; }
  .header { background: #1F3864; color: white; padding: 20px 30px; }
  .header h1 { margin: 0; font-size: 18pt; }
  .header p { margin: 4px 0; font-size: 9pt; }
  .divider { border-top: 3px solid #1F3864; margin: 0; }
  .content { padding: 25px 35px; }
  .meta { margin: 15px 0; }
  .section-heading { color: #1F3864; font-size: 11pt; font-weight: bold;
                     border-bottom: 1px solid #D9E1F2; padding-bottom: 3px; margin-top: 15px; }
  .section-content { margin: 8px 0 0 0; line-height: 1.5; font-size: 10pt; }
  .closing { margin-top: 25px; }
  .signatory { margin-top: 40px; }
  .sig-line { border-top: 1px solid #333; width: 200px; margin: 5px 0; }
</style>
</head>
<body>
<div class="header">
  <h1>{{ company.name }}</h1>
  <p>{{ company.address }}</p>
  <p>Tel: {{ company.phone }} | Email: {{ company.email }}</p>
</div>
<div class="divider"></div>
<div class="content">
  <div class="meta">
    <p><strong>Date:</strong> {{ draft.date }}</p>
    <p><strong>To:</strong> {{ draft.to_name }}, {{ draft.to_company }}</p>
    <p><strong>Ref:</strong> {{ draft.reference }}</p>
    <p><strong>Subject:</strong> {{ draft.subject }}</p>
  </div>
  <p>Dear Sir/Madam,</p>
  {% for section in draft.sections %}
  <div class="section-heading">{{ section.title }}</div>
  <div class="section-content">{{ section.content | replace('\n', '<br>') }}</div>
  {% endfor %}
  <div class="closing">
    <p>{{ draft.closing }}</p>
    <p>Yours faithfully,</p>
  </div>
  <div class="signatory">
    <div class="sig-line"></div>
    <p><strong>{{ draft.signatory_name }}</strong></p>
    <p>{{ draft.signatory_title }}</p>
    <p>{{ company.name }}</p>
  </div>
</div>
</body>
</html>"""


cover_letter_service = CoverLetterService()
