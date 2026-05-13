import os
import subprocess
import zipfile
import shutil
from PIL import Image

def compress_pdf(gs_path: str, input_path: str, output_path: str):
    """PDF faylni Ghostscript orqali siqadi."""
    if gs_path != "gs" and not os.path.exists(gs_path):
        # Agar .env dagi yo'l xato bo'lsa, tizimdan qidirib ko'radi
        gs_path = "gs" 
        
    cmd = [
        gs_path,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/ebook",  # 150 dpi - sifat va hajm o'rtasidagi ideal balans
        "-dColorImageDownsampleType=/Bicubic",
        "-dColorImageResolution=150",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dGrayImageResolution=150",
        "-dMonoImageDownsampleType=/Bicubic",
        "-dMonoImageResolution=150",
        "-dOptimize=true",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={output_path}", input_path
    ]
    subprocess.check_call(cmd)
    return output_path

def compress_office_file(input_path: str, output_path: str):
    """DOCX yoki PPTX ichidagi rasmlarni siqish orqali hajmni kamaytiradi."""
    tmp_extract = input_path + "_extracted"
    if os.path.exists(tmp_extract):
        shutil.rmtree(tmp_extract)
    
    with zipfile.ZipFile(input_path, 'r') as zip_ref:
        zip_ref.extractall(tmp_extract)

    for root, dirs, files in os.walk(tmp_extract):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                img_path = os.path.join(root, file)
                try:
                    with Image.open(img_path) as img:
                        # Agar rasm juda katta bo'lsa, uni o'lchamini optimallashtiramiz
                        if img.width > 1600 or img.height > 1600:
                            img.thumbnail((1600, 1600), Image.LANCZOS)

                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        # Sifatni saqlagan holda MB dan KB ga tushirish uchun eng samarali sozlamalar
                        img.save(img_path, "JPEG", quality=50, optimize=True, progressive=True)
                except Exception:
                    continue

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
        for root, dirs, files in os.walk(tmp_extract):
            for file in files:
                full_p = os.path.join(root, file)
                rel_p = os.path.relpath(full_p, tmp_extract)
                zip_out.write(full_p, rel_p)
    
    shutil.rmtree(tmp_extract)
    return output_path