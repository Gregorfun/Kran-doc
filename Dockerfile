# Dockerfile für PDFDoc / Kran-Tools
# Multi-stage build für optimale Image-Größe

FROM python:3.11-slim as builder

# Arbeitsverzeichnis setzen
WORKDIR /app

# System-Dependencies für PDF-Verarbeitung und OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production Stage
FROM python:3.11-slim

# Arbeitsverzeichnis
WORKDIR /app

# System-Dependencies kopieren
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies von builder-Stage kopieren
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# App-Code kopieren
COPY . .

# Verzeichnisse für Daten erstellen
RUN mkdir -p input/lec input/bmk input/spl input/manuals \
             output/models output/reports output/embeddings \
             logs

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=webapp/app.py
ENV TESSERACT_CMD=/usr/bin/tesseract

# Port für Flask-App
EXPOSE 5000

# Standard-Command: Web-Interface starten
CMD ["python", "webapp/app.py"]

# Alternative Commands:
# CLI-Menü: docker run <image> python scripts/pdfdoc_cli.py
# Setup: docker run <image> python setup.py
