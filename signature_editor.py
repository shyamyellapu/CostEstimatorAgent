"""
Live Signature Position Editor
Adjust sliders → click Generate → PDF opens with updated positions.
Once happy, click "Copy Values" to get the final numbers to paste into cover_letter_service.py
"""
import tkinter as tk
from tkinter import ttk
import io, os, subprocess
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage,
)
from reportlab.platypus.flowables import Flowable

PAGE_W, PAGE_H = A4
LEFT_M = 2 * cm
RIGHT_M = 2 * cm
FRAME_W = PAGE_W - LEFT_M - RIGHT_M

SIG_DIR = Path(__file__).parent / "ReferenceFiles"
OUT_PATH = Path(__file__).parent / "test_signature_layout.pdf"

# Load header/footer from DOCX
HF_DOCX = SIG_DIR / "Header and Footer.docx"
header_blob = footer_blob = None
header_w_pt = header_h_pt = footer_w_pt = footer_h_pt = 0
try:
    from docx import Document as DocxDocument
    from docx.oxml.ns import qn
    doc = DocxDocument(str(HF_DOCX))
    sec = doc.sections[0]
    EMU_PER_PT = 12700
    for rel in sec.header.part.rels.values():
        if 'image' in rel.reltype:
            header_blob = rel.target_part.blob; break
    for rel in sec.footer.part.rels.values():
        if 'image' in rel.reltype:
            footer_blob = rel.target_part.blob; break
    hdr_xml = sec.header._element
    for tag in ('wp:anchor', 'wp:inline'):
        for drawing in hdr_xml.iter(qn(tag)):
            ext = drawing.find(qn('wp:extent'))
            if ext is not None:
                header_w_pt = int(ext.get('cx', 0)) / EMU_PER_PT
                header_h_pt = int(ext.get('cy', 0)) / EMU_PER_PT
    ftr_xml = sec.footer._element
    for tag in ('wp:anchor', 'wp:inline'):
        for drawing in ftr_xml.iter(qn(tag)):
            ext = drawing.find(qn('wp:extent'))
            if ext is not None:
                footer_w_pt = int(ext.get('cx', 0)) / EMU_PER_PT
                footer_h_pt = int(ext.get('cy', 0)) / EMU_PER_PT
except Exception as e:
    print(f"Header/footer load failed: {e}")


def generate_pdf(bilal_x, bilal_y, datta_x, datta_y, arjun_x, sig_height):
    """Generate PDF with signatures at specified positions (in points from left margin)."""
    styles = getSampleStyleSheet()
    body = ParagraphStyle("B", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=4)
    bold = ParagraphStyle("Bo", parent=styles["Normal"], fontSize=10, leading=14, fontName="Helvetica-Bold")

    header_reader = footer_reader = None
    h_draw_w = h_h = f_draw_w = f_h = 0
    h_x = f_x = 0
    if header_blob:
        header_reader = ImageReader(io.BytesIO(header_blob))
        h_draw_w = header_w_pt or PAGE_W
        h_h = header_h_pt or PAGE_W * (header_reader.getSize()[1] / header_reader.getSize()[0])
        h_x = (PAGE_W - h_draw_w) / 2
    if footer_blob:
        footer_reader = ImageReader(io.BytesIO(footer_blob))
        f_draw_w = footer_w_pt or PAGE_W
        f_h = footer_h_pt or PAGE_W * (footer_reader.getSize()[1] / footer_reader.getSize()[0])
        f_x = (PAGE_W - f_draw_w) / 2

    top_m = h_h + 0.6 * cm
    bot_m = max(2 * cm, f_h + 0.5 * cm)

    frame = Frame(LEFT_M, bot_m, FRAME_W, PAGE_H - top_m - bot_m,
                  id='main', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def draw_page(canvas, doc):
        if header_reader:
            canvas.drawImage(header_reader, h_x, PAGE_H - h_h, width=h_draw_w, height=h_h, mask='auto')
        if footer_reader:
            canvas.drawImage(footer_reader, f_x, 0, width=f_draw_w, height=f_h, mask='auto')

    tpl = PageTemplate(id='main', frames=[frame], onPage=draw_page)
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tpl],
                          leftMargin=LEFT_M, rightMargin=RIGHT_M,
                          topMargin=top_m, bottomMargin=bot_m)

    sig_h = sig_height

    class PositionedImg(Flowable):
        """Draws image at exact (x_offset, 0) from frame left edge."""
        def __init__(self, path, w, h, x_off):
            Flowable.__init__(self)
            self._path, self._w, self._h, self._x = str(path), w, h, x_off
        def wrap(self, aw, ah):
            return (aw, self._h)
        def draw(self):
            self.canv.drawImage(self._path, self._x, 0,
                                width=self._w, height=self._h, mask='auto')

    def make_img(filename, x_off):
        p = SIG_DIR / filename
        if not p.exists():
            return Spacer(1, sig_h)
        r = ImageReader(str(p))
        iw, ih = r.getSize()
        w = sig_h * (iw / ih)
        return PositionedImg(p, w, sig_h, x_off)

    story = []
    # Filler content
    story.append(Paragraph("... (letter content above) ...", body))
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("Yours faithfully,", body))
    story.append(Paragraph("For C&amp;J Gulf Equipment Manufacturing LLC.", body))

    # Bilal signature at exact x position
    story.append(Spacer(1, bilal_y))
    story.append(make_img("BilalAhmed Signature.jpg", bilal_x))
    story.append(Paragraph("<b>Bilal Ahmed</b>", bold))
    story.append(Paragraph("Cost &amp; Estimation Engineer.", body))

    # Gopakumar + Arjun — each at exact x positions, side by side in table
    story.append(Spacer(1, datta_y))  # gap before secondary sigs

    half = FRAME_W / 2
    d_img = make_img("Datta C.Sawant Signature.jpg", datta_x)
    s_img = make_img("arjun gopakumar Signature.jpg", arjun_x)

    sig_table = Table(
        [
            [d_img, s_img],
            [Paragraph("<b>Datta C. Sawant</b>", bold),
             Paragraph("<b>Arjun Gopakumar</b>", bold)],
            [Paragraph("Sr. Mechanical Engineer", body),
             Paragraph("Business Unit Head", body)],
        ],
        colWidths=[half, half],
    )
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(sig_table)

    doc.build(story)
    buf.seek(0)
    data = buf.read()
    with open(str(OUT_PATH), 'wb') as f:
        f.write(data)
    return len(data)


# ---- GUI ----
root = tk.Tk()
root.title("Signature Position Editor")
root.geometry("620x520")
root.configure(bg="#f0f0f0")

info = tk.Label(root, text=f"Frame width: {FRAME_W:.0f} pt  |  Sig images in: {SIG_DIR}",
                bg="#f0f0f0", font=("Consolas", 9))
info.pack(pady=5)

sliders = {}

def add_slider(parent, label, from_, to_, default, row):
    tk.Label(parent, text=label, bg="#f0f0f0", font=("Segoe UI", 10), anchor="w").grid(
        row=row, column=0, sticky="w", padx=5, pady=2)
    var = tk.DoubleVar(value=default)
    s = ttk.Scale(parent, from_=from_, to=to_, variable=var, length=320)
    s.grid(row=row, column=1, padx=5, pady=2)
    val_lbl = tk.Label(parent, text=f"{default:.0f}", bg="#f0f0f0", width=6,
                       font=("Consolas", 10))
    val_lbl.grid(row=row, column=2, padx=5)
    def update_label(*_): val_lbl.config(text=f"{var.get():.0f}")
    var.trace_add("write", update_label)
    sliders[label] = var
    return var

frame = tk.Frame(root, bg="#f0f0f0")
frame.pack(pady=10)

# Bilal sig: default centered = (FRAME_W - sig_w) / 2 ≈ 207 pt
add_slider(frame, "Bilal X (pt from left)", 0, FRAME_W, 207, 0)
add_slider(frame, "Bilal top gap (pt)", 0, 80, 10, 1)
add_slider(frame, "Datta X (pt from left)", 0, FRAME_W/2, 0, 2)
add_slider(frame, "Datta top gap (pt)", 0, 80, 14, 3)
add_slider(frame, "Arjun X (pt from left)", 0, FRAME_W/2, 0, 4)
add_slider(frame, "Sig height (pt)", 15, 60, 34, 5)

status = tk.Label(root, text="Adjust sliders and click Generate", bg="#f0f0f0",
                  font=("Segoe UI", 10), fg="gray")
status.pack(pady=5)

def on_generate():
    bx = sliders["Bilal X (pt from left)"].get()
    by = sliders["Bilal top gap (pt)"].get()
    dx = sliders["Datta X (pt from left)"].get()
    dy = sliders["Datta top gap (pt)"].get()
    sx = sliders["Arjun X (pt from left)"].get()
    sh = sliders["Sig height (pt)"].get()
    try:
        size = generate_pdf(bx, by, dx, dy, sx, sh)
        status.config(text=f"Generated {size:,} bytes → {OUT_PATH.name}", fg="green")
        subprocess.Popen(["cmd", "/c", "start", "", str(OUT_PATH)], shell=True)
    except Exception as e:
        status.config(text=f"Error: {e}", fg="red")

def on_copy():
    bx = sliders["Bilal X (pt from left)"].get()
    by = sliders["Bilal top gap (pt)"].get()
    dx = sliders["Datta X (pt from left)"].get()
    dy = sliders["Datta top gap (pt)"].get()
    sx = sliders["Arjun X (pt from left)"].get()
    sh = sliders["Sig height (pt)"].get()
    text = (
        f"# Signature positions (paste into cover_letter_service.py)\n"
        f"BILAL_X = {bx:.0f}   # pt from left margin\n"
        f"BILAL_GAP = {by:.0f}  # pt gap above Bilal sig\n"
        f"DATTA_X = {dx:.0f}   # pt from left edge of left column\n"
        f"DATTA_GAP = {dy:.0f}  # pt gap above secondary sigs\n"
        f"arjun_x = {sx:.0f}  # pt from left edge of right column\n"
        f"SIG_H = {sh:.0f}     # pt signature image height\n"
    )
    root.clipboard_clear()
    root.clipboard_append(text)
    status.config(text="Values copied to clipboard!", fg="blue")

btn_frame = tk.Frame(root, bg="#f0f0f0")
btn_frame.pack(pady=10)

ttk.Button(btn_frame, text="Generate PDF & Open", command=on_generate).pack(side="left", padx=10)
ttk.Button(btn_frame, text="Copy Values", command=on_copy).pack(side="left", padx=10)

root.mainloop()
