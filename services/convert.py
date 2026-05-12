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
    # Use a title and content layout for the main slide
    slide_layout = prs.slide_layouts[1] # Typically Title and Content layout
    slide = prs.slides.add_slide(slide_layout)

    # Set the title
    title_shape = slide.shapes.title
    title_shape.text = title

    # Add all text to the content placeholder
    body_shape = slide.placeholders[1]
    tf = body_shape.text_frame
    tf.clear() # Clear any default text
    for i, ln in enumerate((text or "").splitlines()):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = ln.strip()
        p.font.size = Pt(18) # Adjust font size if needed

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
