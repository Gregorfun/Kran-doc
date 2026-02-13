# Kran-Doc System Architektur

**Version:** 2.0  
**Datum:** 16. Januar 2026  
**Status:** Produktion mit Offline-First Ansatz

---

## 📋 Executive Summary

Kran-Doc ist eine **vollständig lokale, KI-gestützte Informationsplattform** für Servicetechniker, Monteure und Werkstätten im Mobilkran-Bereich. Das System verarbeitet technische PDF-Dokumente (LEC-Fehlercodes, SPL-Stromlaufpläne, BMK-Bauteillisten, Handbücher) und macht sie intelligent durchsuchbar.

### Kernprinzipien

✔ **Vollständig lokal** – Keine Cloud-Abhängigkeit  
✔ **Offline-fähig** – Funktioniert in Werkstatt und Baustelle  
✔ **Modular** – Austauschbare Komponenten  
✔ **Skalierbar** – Wächst mit Datenbestand  
✔ **Open Source** – Transparente Entwicklung

### Deployment-Modi

1. **Online Server** (kran-doc.de) - Zentrale Instanz mit Redis Queue, Rate Limiting
2. **Offline Werkstatt Kit** - Lokales Setup mit Bundle-Sync
3. **Hybrid** - Lokale Instanz mit gelegentlichem Bundle-Import

---

## 🏗️ System-Übersicht

### High-Level Architektur (V2.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                      KRAN-DOC PLATFORM V2.0                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   PDF/TIFF  │───▶│   JOB QUEUE  │───▶│   PIPELINE   │      │
│  │   Import    │    │  (RQ/Redis)  │    │   WORKER     │      │
│  └─────────────┘    └──────────────┘    └──────────────┘      │
│         │                                        │              │
│         ▼                                        ▼              │
│  ┌─────────────┐                       ┌──────────────┐        │
│  │ DOCLING     │                       │ NORMALIZER   │        │
│  │ + OCR       │                       │ + PROVENANCE │        │
│  └─────────────┘                       └──────────────┘        │
│                                                │                │
│                                                ▼                │
│                                       ┌──────────────┐          │
│                                       │  CHUNKER     │          │
│                                       │ + Embeddings │          │
│                                       └──────────────┘          │
│                                                │                │
│                                                ▼                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           QDRANT VECTOR DATABASE (Optional)              │  │
│  │  Collections: lec | bmk | spl | manuals | community     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                │                │
│                                                ▼                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            FUSION SEARCH ENGINE                          │  │
│  │  Exact (Regex) + Fuzzy (RapidFuzz) + Semantic (Vector)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                │                │
│                                                ▼                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  FLASK WEB-APP + API                     │  │
│  │  /search | /api/import | /api/jobs | /api/bundles      │  │
│  │  Rate Limiting | API Key Auth | Upload Protection      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Neue Architektur-Komponenten (V2.0)

### 1. Core/Adapter Separation

**Struktur:**
```
kran-tools/
├── core/                    # Business Logic (framework-unabhängig)
│   ├── search/             # Fusion Search Service
│   └── ...
├── adapters/               # Framework-spezifische Adapter
│   ├── security.py         # Rate Limiting, Auth
│   └── ...
├── scripts/                # CLI Tools & Jobs
│   ├── jobs/              # RQ Worker & Tasks
│   └── bundles/           # Export/Import
└── webapp/                # Flask UI/API
```

**Vorteile:**
- Core kann in anderen Frameworks wiederverwendet werden
- Einfacheres Testing
- Klare Abhängigkeiten

### 2. Job Queue System

**Implementierung:** Redis Queue (RQ)

**Job State Machine:**
```
uploaded → textlayer_check → ocr → parse → normalize →
extract → chunk → embed → index → done/failed
```

**Persistenz:** JSON files in `output/jobs/<job_id>.json`

**API Endpoints:**
- `POST /api/import` - Start import job
- `GET /api/jobs/<id>` - Get job status
- `GET /api/jobs/<id>/log` - Get job log

### 3. Provenance/Quellen

**Pflichtfelder in allen Datenmodellen:**
- `source_document` - PDF Dateiname
- `page_number` - Seitennummer
- `extraction_method` - docling|unstructured|ocr
- `confidence` - 0.0 - 1.0
- `bbox` - Optional: {x, y, w, h}

**UI Integration:**
- "Quelle öffnen" Link bei jedem Treffer
- PDF Viewer mit Sprung zur Seite: `/docs/<file>?page=<n>`

### 4. Fusion Search

**Kombiniert drei Suchstrategien:**

1. **Exact Match** (Score: 1.0)
   - Regex für LEC-\d+, BMK Codes, Klemmen
   - Direkt auf Payload-Fields in Qdrant

2. **Fuzzy Match** (Score: 0.5-0.9)
   - RapidFuzz für Tippfehler
   - Nur auf relevanten Feldern (code, title)

3. **Semantic** (Score: 0.0-1.0)
   - Vektor-Suche via Qdrant
   - sentence-transformers

**API:**
```
GET /api/search?q=LEC-1234&mode=auto&limit=20
Modes: auto (fusion) | exact | fuzzy | semantic
```

### 5. Bundle Export/Import (Offline-Sync)

**Export:**
```bash
python scripts/bundles/export_bundle.py --model LTM1070 --out bundle.zip
```

**Bundle Struktur:**
```
model_bundle.zip
├── manifest.json          # Version, checksums, metadata
└── data/
    ├── FULL_KNOWLEDGE.json
    ├── embeddings/
    └── ...
```

**Import:**
```bash
python scripts/bundles/import_bundle.py --bundle bundle.zip
```

**API:**
- `POST /api/bundles/import` - Upload & import bundle
- `GET /api/bundles/list` - List available bundles

### 6. Security

**Rate Limiting:**
- `/api/search`: 60 req/min
- `/api/import`: 10 req/min
- In-Memory Limiter (kein Redis nötig)

**Upload Protection:**
- Max 50MB file size
- PDF MIME type check
- Filename sanitization
- Path traversal protection

**API Key Auth:**
- Optional: `KRANDOC_API_KEY` in .env
- Header: `X-API-Key` oder Query: `?api_key=...`

---

## 📦 Komponenten-Stack

### 1. Dokumenten-Verstehen & KI-Parsing

| Tool | Zweck | Integration |
|------|-------|-------------|
| **Docling** | Hauptparser für PDF Layout/Tabellen/Text | `docling_processor.py` |
| **Docling-Core** | Low-level Parsing-Engine | Dependency von Docling |
| **Docling-Serve** | REST API für Docling (optional) | Docker-Container |
| **Docling-Agent** | Auto-Chunking & Strukturerkennung | `chunking_agent.py` |
| **Unstructured** | Fallback für exotische Formate | `unstructured_parser.py` |

**Implementierung:**
- Docling primär für strukturierte PDF (LEC, SPL, BMK)
- Unstructured für gescannte oder komplexe Handbücher
- Normalisierung in einheitliches JSON-Format

### 2. OCR (Optical Character Recognition)

| Tool | Zweck | Priorität |
|------|-------|-----------|
| **PaddleOCR** | State-of-the-art OCR für technische Dokumente | Primär |
| **OCRmyPDF** | Fügt PDFs Searchable Text Layer hinzu | Vorverarbeitung |
| **EasyOCR** | Leichtgewicht für kleinere Module | Optional |
| **SURYA** | Vision-Transformer OCR | Optional (High-End) |

**OCR-Pipeline:**
```
PDF ohne Textlayer
    ↓
OCRmyPDF (erzeugt searchable PDF)
    ↓
PaddleOCR (extrahiert Text mit Bounding Boxes)
    ↓
Confidence-Filter (>80%)
    ↓
Strukturierter Text
```

### 3. Semantische Suche & Vektorspeicherung

| Tool | Rolle | Verwendung |
|------|-------|------------|
| **Qdrant** | Primäre Vektor-DB (Rust, sehr schnell) | Produktiv-System |
| **Chroma** | Lightweight DB für Tests | Entwicklung/Tests |
| **Weaviate** | Alternative mit Modulen | Optional/Zukunft |

**Qdrant Collections:**
- `lec_errors` – Fehlercodes mit Severity/Beschreibung
- `bmk_components` – Bauteile mit Ort/Signal/Funktion
- `spl_circuits` – Schaltplan-Klemmen und Verbindungen
- `manuals_chunks` – RAG-fähige Handbuch-Chunks
- `community_solutions` – Techniker-Lösungen (reviewed)

### 4. RAG-Framework (Retrieval-Augmented Generation)

| Framework | Zweck | Integration |
|-----------|-------|-------------|
| **Haystack** | Haupt-RAG-System (Deutsch optimiert) | `rag_pipeline.py` |
| **LlamaIndex** | Alternative für Index-basiertes QA | Optional |
| **LangChain** | Tool-Orchestrierung, Agenten | Optional |

**Haystack-Pipeline:**
```python
DocumentStore (Qdrant)
    ↓
EmbeddingRetriever (sentence-transformers)
    ↓
Reader (optional: lokales LLM)
    ↓
AnswerGenerator
```

### 5. ML-Lifecycle & Monitoring

| Tool | Zweck | Phase |
|------|-------|-------|
| **Label Studio** | Annotation von Ground Truth | Datenaufbereitung |
| **MLflow** | Modelltracking, Metriken, Registry | Training/Evaluation |
| **Streamlit** | Debug-UI für Entwickler | Entwicklung |
| **Grafana + Prometheus** | System-Monitoring | Produktion |

---

## 🔄 Neue Pipeline-Architektur

### Phase 1: Import & OCR

```python
# Datei: scripts/document_processor.py

class DocumentProcessor:
    """Orchestriert PDF Import, OCR und Parsing"""

    def process_document(self, pdf_path):
        # 1. Prüfe Textlayer
        has_text = self.check_text_layer(pdf_path)

        # 2. OCR falls nötig
        if not has_text:
            pdf_path = self.ocr_pipeline(pdf_path)

        # 3. Docling Parsing
        docling_result = self.parse_with_docling(pdf_path)

        # 4. Fallback zu Unstructured
        if docling_result.confidence < 0.7:
            fallback = self.parse_with_unstructured(pdf_path)

        # 5. Normalisierung
        normalized = self.normalize_output(docling_result)

        return normalized
```

### Phase 2: Strukturextraktion

```python
# Datei: scripts/structure_extractor.py

class StructureExtractor:
    """Extrahiert domänen-spezifische Strukturen"""

    def extract_lec(self, normalized_doc):
        """LEC Fehlercode Extraktion"""
        return {
            "code": "LEC-12345",
            "description": "Drucksensor defekt",
            "severity": "critical",
            "affected_systems": ["Hydraulik"],
            "source_page": 42
        }

    def extract_bmk(self, normalized_doc):
        """BMK Komponenten Extraktion"""
        return {
            "bmk_code": "B1-M1",
            "component_type": "Motor",
            "location": "Hauptschaltschrank",
            "signals": ["24V", "GND"],
            "function": "Hauptantrieb"
        }
```

### Phase 3: Embedding & Indexierung

```python
# Datei: scripts/vector_indexer.py

class VectorIndexer:
    """Erzeugt Embeddings und speichert in Qdrant"""

    def __init__(self):
        self.qdrant = QdrantClient(path="./data/qdrant")
        self.embedder = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")

    def index_documents(self, documents, collection_name):
        # Embeddings erzeugen
        embeddings = self.embedder.encode([doc["text"] for doc in documents])

        # In Qdrant speichern
        self.qdrant.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=doc["id"],
                    vector=embedding.tolist(),
                    payload=doc["metadata"]
                )
                for doc, embedding in zip(documents, embeddings)
            ]
        )
```

### Phase 4: RAG-Abfrage

```python
# Datei: scripts/rag_query.py

class RAGQueryEngine:
    """Beantwortet Fragen über Dokumente"""

    def query(self, question: str, collection: str):
        # 1. Embedding für Frage
        query_embedding = self.embedder.encode([question])[0]

        # 2. Suche in Qdrant
        results = self.qdrant.search(
            collection_name=collection,
            query_vector=query_embedding,
            limit=5
        )

        # 3. Haystack Reader (optional)
        if self.use_llm:
            answer = self.haystack_pipeline.run(
                query=question,
                documents=results
            )

        return {
            "answer": answer or "Siehe Dokumente",
            "sources": [r.payload for r in results],
            "confidence": max(r.score for r in results)
        }
```

---

## 🗂️ Datenmodelle

### LEC Fehlercode

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class LECErrorCode(BaseModel):
    """LEC Fehlercode Datenmodell"""
    code: str = Field(..., regex=r"LEC-\d+")
    description: str
    severity: Severity
    affected_systems: List[str]
    possible_causes: List[str]
    solutions: List[str]
    related_bmk: List[str] = []
    source_document: str
    page_number: int
    model_series: List[str]
```

### BMK Komponente

```python
class BMKComponent(BaseModel):
    """BMK Bauteilliste Komponente"""
    bmk_code: str = Field(..., regex=r"[A-Z]\d+-[A-Z]\d+")
    component_type: str
    manufacturer: Optional[str]
    part_number: Optional[str]
    location: str
    signals: List[str]
    voltage: Optional[str]
    function_description: str
    connected_to: List[str] = []
    used_in_spl: List[str] = []
    source_document: str
    coordinates: Optional[dict] = None  # {x, y} Position im Plan
```

### SPL Schaltplan

```python
class SPLCircuit(BaseModel):
    """SPL Stromlaufplan Datenmodell"""
    circuit_id: str
    circuit_name: str
    terminals: List[dict]  # [{terminal_id, voltage, signal_type}]
    components: List[str]  # BMK-Codes
    connections: List[dict]  # [{from, to, wire_color, wire_gauge}]
    power_supply: str
    protection_devices: List[str]
    source_document: str
    page_number: int
```

### Community Solution

```python
class CommunitySolution(BaseModel):
    """Techniker-Lösung aus der Community"""
    solution_id: str
    related_error_codes: List[str]
    problem_description: str
    solution_steps: List[str]
    required_parts: List[str]
    required_tools: List[str]
    estimated_time: int  # Minuten
    difficulty: str  # "easy" | "medium" | "hard"
    submitted_by: str
    reviewed_by: Optional[str]
    review_status: str  # "pending" | "approved" | "rejected"
    votes: int
    created_at: str
    updated_at: str
```

---

## 🔍 Semantische Query-Beispiele

### Query 1: Fehlercode Erklärung

```python
# Nutzer fragt: "Was bedeutet LEC-12345?"

result = rag_engine.query(
    question="Was bedeutet LEC-12345?",
    collection="lec_errors"
)

# Antwort:
{
    "answer": "LEC-12345 bedeutet 'Drucksensor defekt'.
               Dies ist ein kritischer Fehler im Hydrauliksystem.",
    "sources": [
        {
            "code": "LEC-12345",
            "severity": "critical",
            "solutions": ["Sensor prüfen", "Verkabelung checken", "Sensor tauschen"]
        }
    ],
    "related_bmk": ["B1-S4", "B2-M7"],
    "confidence": 0.95
}
```

### Query 2: Komponenten-Suche

```python
# Nutzer fragt: "Wo befindet sich Motor B1-M1?"

result = rag_engine.query(
    question="Wo befindet sich Motor B1-M1?",
    collection="bmk_components"
)

# Antwort:
{
    "component": "B1-M1",
    "location": "Hauptschaltschrank, Reihe 1, Position 3",
    "spl_reference": "SPL-001, Seite 15",
    "coordinates": {"x": 120, "y": 340}
}
```

### Query 3: Lösungssuche

```python
# Nutzer fragt: "Wie behebe ich Hydraulik-Druckprobleme?"

result = rag_engine.query(
    question="Wie behebe ich Hydraulik-Druckprobleme?",
    collection="community_solutions"
)

# Antwort: Top 3 Community-Lösungen mit Bewertungen
```

---

## 🏭 Deployment-Strategien

### 1. Lokales Setup (Windows/Linux)

```bash
# Installation
git clone https://github.com/Gregorfun/Kran-doc.git
cd kran-tools
python -m venv venv
source venv/bin/activate  # oder venv\Scripts\activate (Windows)
pip install -r requirements.txt

# Qdrant lokal starten
docker run -p 6333:6333 qdrant/qdrant

# App starten
python webapp/app.py
```

### 2. Docker Compose (Empfohlen)

```bash
docker-compose up -d
# Öffne http://localhost:5002
```

**Enthält:**
- Kran-Doc Web-App
- Qdrant Vektor-DB
- Docling-Serve (optional)
- Grafana + Prometheus (optional)

### 3. Netcup VPS Deployment

```bash
# VPS Requirements:
# - 4 GB RAM (min), 8 GB empfohlen
# - 50 GB SSD
# - Ubuntu 22.04 LTS

# 1. Docker installieren
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 2. Repository klonen
git clone https://github.com/Gregorfun/Kran-doc.git

# 3. Production Stack starten
cd kran-tools
docker-compose -f docker-compose.prod.yml up -d

# 4. Reverse Proxy (nginx)
# Siehe docs/deployment/nginx.conf
```

### 4. Memory-Optimierung

**Offline-Modelle:**
- `paraphrase-multilingual-mpnet-base-v2` (420 MB)
- `all-MiniLM-L6-v2` (80 MB, schneller aber weniger genau)
- PaddleOCR Modelle (~200 MB)

**Qdrant Memory:**
- Vektoren: ~1 GB pro 100.000 Dokumente
- HNSW Index: Zusätzlich ~30% der Vektorgröße

**Tipps:**
- Quantisierung für Embeddings (float32 → uint8)
- Lazy Loading von Modellen
- Batch Processing statt Echtzeit

---

## 🧰 Entwicklungs-Roadmap

### Phase 1: Foundation (Q1 2026) ✓ In Arbeit

- [x] Docling Integration
- [x] PaddleOCR Setup
- [x] Qdrant Collections
- [ ] Haystack RAG Pipeline
- [ ] Basis Web-UI

### Phase 2: Intelligence (Q2 2026)

- [ ] ML-basierte Fehlerklassifikation
- [ ] Automatische BMK ↔ LEC Verknüpfung
- [ ] OCR Confidence Ranking
- [ ] Label Studio für Ground Truth

### Phase 3: Community (Q3 2026)

- [ ] Community-Lösungen System
- [ ] Review-Workflow
- [ ] Voting & Reputation
- [ ] Automatische Index-Updates

### Phase 4: Advanced (Q4 2026)

- [ ] Mehrsprachigkeit (DE, EN, FR, ES)
- [ ] Vision-Transformer (SURYA)
- [ ] Offline-Optimierung für Baustellen
- [ ] Mobile App (PWA)

---

## 📊 Monitoring & Debugging

### Streamlit Debug-UI

```python
# streamlit_debug.py
import streamlit as st

st.title("Kran-Doc Debug Dashboard")

# OCR Confidence
st.metric("OCR Confidence", "87.3%", delta="+2.1%")

# Qdrant Status
st.metric("Indexed Documents", "12,345", delta="+234")

# Pipeline Status
st.dataframe(pipeline_status)
```

### Grafana Dashboards

**Metriken:**
- Query Latency (p50, p95, p99)
- Qdrant Vector Search Time
- OCR Processing Time
- Memory Usage
- API Request Rate

---

## 🔐 Sicherheit & Datenschutz

**Lokal first:**
- Keine Daten verlassen das System
- Keine Cloud-API-Calls
- Alle Modelle lokal

**Authentifizierung:**
- Flask-Login für Web-UI
- API-Keys für externe Tools
- RBAC für Community-Features

**Daten:**
- Verschlüsselte Logs
- DSGVO-konform
- Backup-Strategien

---

## 📚 Weitere Dokumentation

- [Installation Guide](INSTALLATION.md)
- [API Documentation](API.md)
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Deployment Guides](deployment/)
- [Developer Setup](DEVELOPMENT.md)

---

**Maintainer:** Gregor  
**Lizenz:** MIT  
**Repository:** https://github.com/Gregorfun/Kran-doc
