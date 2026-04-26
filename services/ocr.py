import os
import pytesseract
from PIL import Image

def configure_tesseract(tesseract_path: str):
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

def _tess_lang(ui_lang: str) -> str:
    return {"uz":"uzb", "ru":"rus", "en":"eng"}.get(ui_lang, "eng")

def ocr_image(image_path: str, ui_lang: str) -> str:
    if not os.path.exists(image_path):
        raise RuntimeError("Rasm topilmadi.")
    img = Image.open(image_path)
    return pytesseract.image_to_string(img, lang=_tess_lang(ui_lang))
