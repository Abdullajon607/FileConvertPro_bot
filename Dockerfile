# Python base image
FROM python:3.11-slim

# Tizim dasturlarini o'rnatish (Ghostscript, LibreOffice, Tesseract)
RUN apt-get update && apt-get install -y \
    ghostscript \
    libreoffice \
    tesseract-ocr \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Ishchi papkani sozlash
WORKDIR /app

# Kutubxonalarni nusxalash va o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyihaning barcha fayllarini nusxalash
COPY . .

# Botni ishga tushirish
CMD ["python", "main.py"]