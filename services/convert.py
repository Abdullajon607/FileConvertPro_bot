import os
import subprocess
from pdf2docx import Converter
from docx import Document
from docx.shared import Inches
from pptx import Presentation
from pptx.util import Pt

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
        doc.add_paragraph(line)
    doc.save(out_docx)

def text_to_pptx(text: str, out_pptx: str, title: str = "Generated Slides"):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    slide.placeholders[1].text = ""

    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    chunk, chunks = [], []
    for ln in lines:
        chunk.append(ln)
        if len(chunk) >= 8:
            chunks.append(chunk); chunk = []
    if chunk:
        chunks.append(chunk)

    for i, ch in enumerate(chunks, start=1):
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = f"Slide {i}"
        tf = s.shapes.placeholders[1].text_frame
        tf.clear()
        for j, ln in enumerate(ch):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.text = ln
            p.font.size = Pt(20)

    prs.save(out_pptx)

def image_to_docx_embed(image_path: str, out_docx: str, title: str = "Scan"):
    if not os.path.exists(image_path):
        raise RuntimeError("Rasm topilmadi.")
    doc = Document()
    doc.add_heading(title, level=1)
    doc.add_picture(image_path, width=Inches(6.0))
    doc.save(out_docx)
