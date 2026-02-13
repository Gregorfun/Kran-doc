# Kran-Doc V2.0 - Production Deployment Guide

## Neue Features (Januar 2026)

### 1. Job Queue System

Asynchrone Verarbeitung von PDF-Importen mit Status-Tracking.

**Setup:**
```bash
# Redis installieren (optional, aber empfohlen)
# Windows: https://github.com/tporadowski/redis/releases
# Linux: sudo apt install redis-server

# Environment Variable setzen
export KRANDOC_REDIS_ENABLED=true
export KRANDOC_REDIS_URL=redis://localhost:6379/0

# Worker starten
python scripts/jobs/worker.py
```

**API Verwendung:**
```bash
# PDF importieren
curl -X POST http://localhost:5002/api/import \
  -F "file=@manual.pdf" \
  -F "model=LTM1070"

# Job Status abrufen
curl http://localhost:5002/api/jobs/<job_id>
```

### 2. Fusion Search

Kombinierte Suche aus Exact, Fuzzy und Semantic.

**API:**
```bash
# Auto-Modus (Fusion)
curl "http://localhost:5002/api/search?q=LEC-1234&mode=auto&limit=20"

# Exact Match
curl "http://localhost:5002/api/search?q=A81&mode=exact"

# Fuzzy Search (Tippfehler)
curl "http://localhost:5002/api/search?q=LEC-123&mode=fuzzy"

# Semantic Search
curl "http://localhost:5002/api/search?q=Hydraulikpumpe+defekt&mode=semantic"
```

### 3. Bundle Export/Import

Offline-Sync für Werkstatt-Deployments ohne Internet.

**Export:**
```bash
# Bundle erstellen
python scripts/bundles/export_bundle.py --model LTM1070 --out bundle.zip

# Alle verfügbaren Modelle anzeigen
python scripts/bundles/export_bundle.py --list
```

**Import:**
```bash
# Bundle importieren
python scripts/bundles/import_bundle.py --bundle LTM1070_bundle.zip

# Via API
curl -X POST http://localhost:5002/api/bundles/import \
  -H "X-API-Key: your-api-key" \
  -F "bundle=@bundle.zip"
```

### 4. Provenance/Quellen

Alle Treffer zeigen jetzt Quellenangaben.

**JSON Response:**
```json
{
  "results": [
    {
      "content": "...",
      "source_document": "LEC_LTM1070.pdf",
      "page_number": 42,
      "confidence": 0.95,
      "extraction_method": "docling",
      "bbox": {"x": 100, "y": 200, "w": 300, "h": 50}
    }
  ]
}
```

**PDF Viewer:**
```
http://localhost:5002/docs/LEC_LTM1070.pdf?page=42
```

### 5. Security Features

**Rate Limiting:**
- Search: 60 Anfragen/Minute
- Import: 10 Anfragen/Minute

**API Key Protection:**
```bash
# .env
KRANDOC_API_KEY=your-secret-key-here

# Request mit API Key
curl -H "X-API-Key: your-secret-key-here" \
  http://localhost:5002/api/import
```

**Upload Protection:**
- Max 50MB Dateigröße
- Nur PDF erlaubt
- Filename Sanitization
- Path Traversal Prevention

## Deployment

### Online Server (kran-doc.de)

```bash
# .env konfigurieren
KRANDOC_SECRET_KEY=<random-secret>
KRANDOC_REDIS_ENABLED=true
KRANDOC_REDIS_URL=redis://localhost:6379/0
KRANDOC_API_KEY=<api-key>
KRANDOC_RATE_LIMIT_ENABLED=true
KRANDOC_MAX_UPLOAD_SIZE_MB=50

# Worker starten
python scripts/jobs/worker.py &

# App starten
python webapp/app.py
```

### Offline Werkstatt Kit

```bash
# Kein Redis nötig
KRANDOC_REDIS_ENABLED=false

# Bundles importieren
python scripts/bundles/import_bundle.py --bundle model_bundle.zip

# App starten
python webapp/app.py
```

## Tests

```bash
# Alle Tests
pytest tests/

# Mit Coverage
pytest tests/ --cov=core --cov=scripts --cov=adapters

# Einzelne Tests
pytest tests/test_search_fusion.py -v
pytest tests/test_bundle_manifest.py -v
```

## Logging

UTF-8 Encoding für Umlaute ist korrekt konfiguriert:
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
```

## Nächste Schritte

Siehe [ROADMAP.md](docs/ROADMAP.md) für geplante Features:
- Haystack RAG Integration (Q2 2026)
- Job Queue Enhancements (Retry, Priority)
- ML-basierte Klassifikation (Q3 2026)
- Knowledge Graph (Q3 2026)
