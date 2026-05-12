import os
import subprocess
from pdf2docx import Converter
from docx import Document
from docx.shared import Inches, Pt as DocxPt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Pt
from pptx.util import Inches as PptxInches
from pptx.enum.text import PP_ALIGN

def _require_file(path: str, name: str):
    if not path or not os.path.exists(path):
        raise RuntimeError(f"{name} topilmadi: {path}")

def pdf_to_docx(pdf_path: str, out_docx: str):
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"PDF topilmadi: {pdf_path}")
    cv = Converter(pdf_path)
    try:
        cv.convert(out_docx, start=0, end=None)
    finally:
        cv.close()

def docx_to_pdf(libreoffice_path: str, docx_path: str, out_dir: str) -> str:
    _require_file(libreoffice_path, "LibreOffice (soffice.exe)")
    if not os.path.exists(docx_path):
        raise RuntimeError(f"DOCX topilmadi: {docx_path}")
    os.makedirs(out_dir, exist_ok=True)

    cmd = [libreoffice_path, "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path]
    subprocess.check_call(cmd)

    base = os.path.splitext(os.path.basename(docx_path))[0]
    pdf_path = os.path.join(out_dir, base + ".pdf")
    if not os.path.exists(pdf_path):
        raise RuntimeError("LibreOffice PDF chiqarmadi.")
    return pdf_path

def text_to_docx(text: str, out_docx: str, title: str | None = None):
    doc = Document()
    if title:
        doc.add_heading(title, level=1)
    for line in (text or "").splitlines():
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(line)
        run.font.name = 'Times New Roman'
        run.font.size = DocxPt(14)
        # Word dasturi shriftni aniq tanishi uchun XML sozlamasi
        run._element.rPr.rFonts.set(qn('w:ascii'), 'Times New Roman')
        run._element.rPr.rFonts.set(qn('w:hAnsi'), 'Times New Roman')
    doc.save(out_docx)

def text_to_pptx(text: str, out_pptx: str, title: str = "Generated Slides"):
    prs = Presentation()
    # Matnni barcha qatorlarga bo'lib chiqamiz
    all_lines = (text or "").splitlines()
    if not all_lines:
        all_lines = [" "]

    # Bo'sh slayd layouti (index 6 odatda mutlaqo bo'sh slayd)
    blank_slide_layout = prs.slide_layouts[6] 
    
    # 20pt shrift uchun slaydga taxminan 11-12 qator sig'adi
    MAX_LINES = 11 
    current_slide = None
    current_text_frame = None
    line_idx = 0

    for line in all_lines:
        clean_line = line.strip()
        
        # Agar qator bo'sh bo'lsa, shunchaki bitta bo'sh joy tashlaymiz
        if not clean_line:
            if current_text_frame:
                current_text_frame.add_paragraph()
                line_idx += 1
            continue

        # Aqlli hisoblash: agar qator juda uzun bo'lsa, u slaydni avtomatik keyingi qatorga o'tkazadi (wrap)
        # 20pt Times New Roman uchun slayd kengligiga taxminan 70 ta belgi sig'adi
        needed_lines = max(1, len(clean_line) // 70)

        # Yangi slayd kerakmi yoki yo'qligini tekshiramiz
        if current_slide is None or (line_idx + needed_lines > MAX_LINES):
            current_slide = prs.slides.add_slide(blank_slide_layout)
            txBox = current_slide.shapes.add_textbox(PptxInches(0.5), PptxInches(0.5), PptxInches(9.0), PptxInches(6.5))
            current_text_frame = txBox.text_frame
            current_text_frame.word_wrap = True
            line_idx = 0

        # Matnni qo'shish
        p = current_text_frame.add_paragraph()
        p.alignment = PP_ALIGN.JUSTIFY
        run = p.add_run()
        run.text = clean_line
        run.font.name = 'Times New Roman'
        run.font.size = Pt(20)
        line_idx += needed_lines

    prs.save(out_pptx)

def images_to_docx_embed(image_paths: list[str], out_docx: str, title: str = "Scan"):
    if not image_paths:
        raise RuntimeError("Rasmlar yo'q.")
    doc = Document()
    doc.add_heading(title, level=1)
    for img_p in image_paths:
        if os.path.exists(img_p):
            doc.add_picture(img_p, width=Inches(6.0))
    doc.save(out_docx)
