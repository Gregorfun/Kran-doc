# ==================================================================
# Dockerfile für Kran-Doc v2.0
# ==================================================================
# Multi-stage build für optimale Image-Größe
# Unterstützt: Docling, PaddleOCR, Qdrant, Haystack
# ==================================================================

FROM python:3.11-slim as builder

# Build Arguments
ARG INSTALL_PADDLE=true
ARG INSTALL_DOCLING=true
ARG INSTALL_DEV=false

# Arbeitsverzeichnis setzen
WORKDIR /app

# System-Dependencies für PDF-Verarbeitung und OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OCR
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    ghostscript \
    # Image Processing
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    # Build Tools
    gcc \
    g++ \
    make \
    # Network
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies kopieren und installieren
COPY requirements-full.txt requirements.txt ./

# Installiere Basis-Dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Optional: PaddleOCR (kann groß sein)
RUN if [ "$INSTALL_PADDLE" = "true" ]; then \
        pip install --no-cache-dir paddleocr paddlepaddle; \
    fi

# Optional: Docling
RUN if [ "$INSTALL_DOCLING" = "true" ]; then \
        pip install --no-cache-dir docling docling-core; \
    fi

# Dev-Dependencies (optional)
RUN if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir pytest black isort flake8; \
    fi


# ==================================================================
# Production Stage
# ==================================================================
FROM python:3.11-slim

# Metadata
LABEL maintainer="Gregor <gregorfun@users.noreply.github.com>"
LABEL description="Kran-Doc: KI-gestützte Dokumenten-Plattform für Mobilkrane"
LABEL version="2.0"

# Arbeitsverzeichnis
WORKDIR /app

# System-Dependencies kopieren (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    ghostscript \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies von builder-Stage kopieren
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# App-Code kopieren
COPY scripts/ ./scripts/
COPY webapp/ ./webapp/
COPY config/ ./config/
COPY community/ ./community/
COPY setup.py pyproject.toml VERSION README.md LICENSE ./

# Verzeichnisse für Daten erstellen
RUN mkdir -p \
    input/pdf input/Liebherr input/manufacturers \
    output/models output/reports output/embeddings output/general \
    logs \
    data/qdrant

# Non-root User erstellen (Sicherheit)
RUN useradd -m -u 1000 krandoc && \
    chown -R krandoc:krandoc /app

# Wechsel zu non-root user
USER krandoc

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV FLASK_APP=webapp/app.py
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV HF_HOME=/app/.cache/huggingface
ENV TORCH_HOME=/app/.cache/torch

# Port für Flask-App
EXPOSE 5002

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5002/api/status || exit 1

# Standard-Command: Web-Interface starten
CMD ["python", "webapp/app.py"]

# ==================================================================
# Alternative Commands
# ==================================================================
# CLI-Menü:
#   docker run <image> python scripts/pdfdoc_cli.py
#
# Pipeline ausführen:
#   docker run -v ./input:/app/input <image> python scripts/run_pdfdoc_pipeline.py
#
# Qdrant init:
#   docker run <image> python scripts/qdrant_manager.py
#
# ==================================================================
