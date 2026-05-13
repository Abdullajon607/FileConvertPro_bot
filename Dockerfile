FROM python:3.11-slim

# Tizim paketlarini o'rnatish (LibreOffice, Ghostscript va Tesseract OCR uchun)
RUN apt-get update && apt-get install -y \
    libreoffice \
    ghostscript \
    tesseract-ocr \
    tesseract-ocr-uzb \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    redis-server \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kutubxonalarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha fayllarini nusxalash
COPY . .

# Botni ishga tushirish
CMD service redis-server start && python main.py