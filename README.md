# Kran-Doc 🏗️

**KI-gestützte Informationsplattform für Mobilkran-Servicetechniker**

## Aktuelle Version
**v2.0.0-beta** 🚀 *Major AI Upgrade*

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.1+-green.svg)](https://flask.palletsprojects.com/)
[![Docling](https://img.shields.io/badge/docling-2.22-orange.svg)](https://github.com/docling-project/docling)
[![Qdrant](https://img.shields.io/badge/qdrant-1.14-red.svg)](https://qdrant.tech/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## 🌟 Was ist Kran-Doc?

Kran-Doc ist eine **vollständig lokale, KI-gestützte Dokumentenplattform** für Servicetechniker, Monteure und Werkstätten im Mobilkran-Bereich. Das System verarbeitet PDF-Dokumente (LEC-Fehlercodes, SPL-Stromlaufpläne, BMK-Bauteillisten, Bedienungsanleitungen) **automatisch** und macht sie **semantisch durchsuchbar**.

### ✨ Neue Features in v2.0

🤖 **Fortgeschrittene KI-Verarbeitung**
- Docling für Layout & Tabellen-Erkennung
- PaddleOCR für State-of-the-Art Texterkennung
- Automatische Dokumentstrukturierung

🔍 **Semantische Vektorsuche**
- Qdrant Vector Database Integration
- Embedding-basierte Suche mit Sentence-Transformers
- Findet relevante Infos auch ohne exakte Stichwörter

📊 **Strukturierte Datenmodelle**
- Pydantic-basierte Validierung
- Typsichere APIs
- Einheitliche Datenformate

🐳 **Production-Ready Deployment**
- Docker Compose Stack
- Monitoring mit Grafana + Prometheus
- Skalierbar & wartbar

🌍 **Vollständig Offline-fähig**
- Keine Cloud-Abhängigkeit
- Alle Modelle lokal
- Funktioniert in Werkstatt & Baustelle

---

## 🚀 Quick Start

### Option 1: Docker (Empfohlen)
### Option 1: Docker (Empfohlen)

```bash
# Klonen
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc/kran-tools

# Starten
docker-compose -f docker-compose.production.yml up -d

# Öffne Browser
# http://localhost:5002
```

### Option 2: Lokale Installation

```bash
# Klonen
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc/kran-tools

# Virtuelle Umgebung
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Dependencies
pip install -r requirements-full.txt

# Starten
python webapp/app.py
```

**👉 Detaillierte Anleitungen:** [docs/INSTALLATION.md](docs/INSTALLATION.md)

---

## 🏗️ Architektur

```
┌─────────────────────────────────────────────────┐
│              KRAN-DOC PLATFORM                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  PDF/TIFF → OCR → Docling → Chunks → Qdrant   │
│                     ↓                           │
│              Haystack RAG                       │
│                     ↓                           │
│              Flask Web-App                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Technologie-Stack:**
- **Document Processing:** Docling, Unstructured, PaddleOCR
- **Vector Database:** Qdrant (lokal oder Server)
- **Embeddings:** Sentence-Transformers
- **RAG:** Haystack (Q2 2026)
- **Web:** Flask + Bootstrap
- **Deployment:** Docker + Docker Compose

**👉 Details:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## 📚 Dokumentation

| Dokument | Beschreibung |
|----------|--------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System-Design & Pipeline |
| [INSTALLATION.md](docs/INSTALLATION.md) | Installation für alle Szenarien |
| [ROADMAP.md](docs/ROADMAP.md) | Entwicklungs-Roadmap 2026-2027 |
| [IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md) | v2.0 Feature-Übersicht |
| [CHANGELOG.md](CHANGELOG.md) | Versionshistorie |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution Guidelines |

---

## 🎯 Use Cases

### Für Servicetechniker

**Problem:** "LEC-12345 wird angezeigt - was ist das?"

```
🔍 Kran-Doc Suche: "LEC-12345"

📋 Ergebnis:
   Code: LEC-12345
   Beschreibung: Hydraulikdrucksensor defekt
   System: Hydraulik
   Severity: ⚠️ Critical

   🔧 Lösungen:
   1. Sensor-Verkabelung prüfen
   2. Kontakte reinigen
   3. Sensor tauschen (Teil: 12345-ABC)

   📄 Quellen: Manual_LTM1070_v3.pdf S. 42
```

### Für Werkstätten

**Problem:** "Wo ist Komponente B1-M1?"

```
🔍 Kran-Doc Suche: "B1-M1 Ort"

📍 Ergebnis:
   BMK: B1-M1
   Typ: Motor (Hauptantrieb)
   Ort: Hauptschaltschrank, Reihe 1, Position 3
   Spannung: 400V AC

   🗺️ Schaltplan: SPL-001, Seite 15
   📷 [Bild des Schaltschranks]
```

### Für Monteure

**Problem:** "Welche Lösungen gibt es für Hydraulik-Druckprobleme?"

```
🔍 Kran-Doc Suche: "Hydraulik Druck Problem Lösung"

💡 Community-Lösungen (Top 3):
   1. ⭐⭐⭐⭐⭐ (15 Votes)
      "Intermittierender Drucksensor-Fehler"
      Zeitaufwand: 45 Min | Schwierigkeit: Mittel

   2. ⭐⭐⭐⭐ (8 Votes)  
      "Hydrauliköl-Verschmutzung durch Filter"
      ...
```

---

## 🚀 Neue Features in v2.0

### 1. Docling Integration

```python
from scripts.docling_processor import DoclingProcessor

processor = DoclingProcessor()
result = processor.process_pdf("manual.pdf")

# Layout-Erkennung, Tabellen-Extraktion, Strukturierte Ausgabe
```

### 2. Advanced OCR

```python
from scripts.ocr_processor import OCRProcessor

ocr = OCRProcessor()
result = ocr.process_image("scan.jpg")

print(f"Text: {result.text}")
print(f"Confidence: {result.confidence:.2%}")
```

### 3. Vector Search

```python
from scripts.qdrant_manager import QdrantVectorDB, LECErrorManager

db = QdrantVectorDB()
lec_manager = LECErrorManager(db)

# Semantische Suche
results = lec_manager.search_error("Hydraulik Problem")
```

### 4. Structured Data Models

```python
from scripts.data_models import LECErrorCode, BMKComponent

lec = LECErrorCode(
    code="LEC-12345",
    description="Hydraulikdrucksensor defekt",
    severity="critical",
    solutions=["Sensor prüfen", "Verkabelung checken"]
)
```

---

## 🛠️ Entwicklung

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Abhängigkeiten installieren**
   ```bash
   pip install -r requirements.txt
   ```

4. **Umgebungsvariablen konfigurieren**
   ```bash
   cp .env.example .env
   # .env bearbeiten und Pfade anpassen
   ```

5. **Konfiguration anpassen**
   ```bash
   # config/config.yaml bearbeiten
   # Pfade für Tesseract, Input/Output-Verzeichnisse setzen
   ```

### Verwendung

#### CLI-Menü (Windows)

Doppelklick auf `pdfdoc.bat` oder:

```bash
python scripts/pdfdoc_cli.py
```

Das interaktive Menü bietet folgende Optionen:
1. Komplett-Pipeline (alle Schritte)
2. Nur Wissensmodule bauen
3. Nur LEC-Parser ausführen
4. Nur SPL-Parser ausführen
5. Nur BMK-Parser ausführen
6. Merge: FULL_KNOWLEDGE pro Modell erzeugen
7. Globale Indizes (Fehlercodes + BMKs) bauen
8. Embedding-Export (knowledge_chunks.jsonl)

#### Web-Interface

```bash
python webapp/app.py
```

Dann Browser öffnen: `http://localhost:5002`

#### Einzelne Skripte

```bash
# LEC-Fehlercodes parsen
python scripts/lec_parser.py

# Schaltpläne verarbeiten
python scripts/spl_parser.py

# BMK-Listen extrahieren
python scripts/bmk_parser.py

# Wissensmodule erstellen
python scripts/wissensmodul_builder.py

# Semantische Indizes erstellen
python scripts/build_local_embedding_index.py
```

## Ordnerstruktur

```text
kran-tools/
├─ config/                    # Konfigurationsdateien
│  ├─ config.yaml            # Hauptkonfiguration
│  ├─ explain_rules.json     # Regeln für Explain-Katalog
│  ├─ explain_templates.json # Templates für Erklärungen
│  └─ model_patterns.json    # Modellmuster für Erkennung
├─ scripts/                   # Python-Skripte
│  ├─ pdfdoc_cli.py          # Interaktives CLI-Menü
│  ├─ lec_parser.py          # Fehlercode-Parser
│  ├─ spl_parser.py          # Schaltplan-Parser
│  ├─ bmk_parser.py          # BMK-Listen-Parser
│  ├─ merge_knowledge.py     # Wissensmodul-Merge
│  ├─ build_explain_catalog.py # Explain-Katalog-Generator
│  └─ ...                    # Weitere Parser und Tools
├─ webapp/                    # Flask-Weboberfläche
│  ├─ app.py                 # Hauptanwendung
│  ├─ static/                # CSS, JS, Bilder
│  └─ templates/             # HTML-Templates
├─ input/                     # Eingabedaten (nicht versioniert)
│  ├─ lec/                   # LEC-PDFs (Fehlercodelisten)
│  ├─ bmk/                   # BMK-PDFs
│  ├─ spl/                   # SPL-PDFs (Schaltpläne)
│  └─ manuals/               # Handbücher
├─ output/                    # Generierte Daten (nicht versioniert)
│  ├─ models/                # JSON-Wissensmodule pro Kranmodell
│  ├─ reports/               # Markdown-Reports
│  └─ embeddings/            # Semantische Indizes
├─ community/                 # Community-Daten
│  ├─ solutions.json         # Lösungsvorschläge
│  └─ users.json             # Benutzerdaten
├─ docs/                      # Dokumentation
├─ tools/                     # Hilfsskripte
├─ requirements.txt           # Python-Abhängigkeiten
├─ .env.example              # Beispiel für Umgebungsvariablen
├─ pdfdoc.bat                # Windows-Starter
└─ README.md                 # Diese Datei
```

## Architektur

Das System folgt einer modularen Pipeline-Architektur:

1. **PDF-Extraktion**: Parser extrahieren strukturierte Daten aus verschiedenen PDF-Typen
2. **Wissensmodule**: Daten werden in JSON-Wissensmodule konsolidiert
3. **Indexierung**: Semantische Indizes für schnelle Suche werden erstellt
4. **Web-Interface**: Flask-App bietet Zugriff auf Wissensmodule

### Datenfluss

```
PDF-Dokumente → Parser → Roh-JSON → Merge → Wissensmodule → Embeddings → Suche
                                                           ↓
                                                    Web-Interface
```

## Konfiguration

### config/config.yaml

```yaml
# Eingabeverzeichnisse
lec_dir: "input/lec"
bmk_dir: "input/bmk"
spl_dir: "input/spl"
manuals_dir: "input/manuals"

# Ausgabeverzeichnisse
models_dir: "output/models"
reports_dir: "output/reports"
embeddings_dir: "output/embeddings"

# OCR-Einstellungen
tesseract_cmd: "/usr/bin/tesseract"  # Pfad zu Tesseract
ocr_enabled: true
ocr_lang: "deu+eng"

# SPL-Parser Optionen
spl_ocr_only_if_gibberish: true
spl_auto_ocr_threshold: 0.6
```

## Entwicklung

### Code-Stil

- Typ-Annotationen verwenden
- Docstrings im Google-Style
- PEP 8 konform
- Maximale Zeilenlänge: 120 Zeichen

### Projektstruktur erweitern

Neue Parser sollten folgendes Interface implementieren:

```python
def process_pdf(pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
    """
    Verarbeitet ein PDF und gibt strukturierte Daten zurück.

    Args:
        pdf_path: Pfad zum PDF
        output_dir: Ausgabeverzeichnis

    Returns:
        Strukturierte Daten als Dict
    """
    pass
```

## Fehlerbehebung

### Tesseract OCR nicht gefunden

```bash
# Linux
sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng

# macOS
brew install tesseract tesseract-lang

# Windows: Download von https://github.com/UB-Mannheim/tesseract/wiki
```

### Import-Fehler

```bash
# Stelle sicher, dass alle Abhängigkeiten installiert sind
pip install -r requirements.txt --upgrade
```

### Speicherprobleme bei Embeddings

```bash
# Reduziere Batch-Size in build_local_embedding_index.py
# oder verwende ein kleineres Modell
```

## Häufig gestellte Fragen (FAQ)

**F: Welche PDF-Formate werden unterstützt?**  
A: Alle Standard-PDFs. Text-PDFs funktionieren am besten, für Bild-PDFs ist Tesseract OCR erforderlich.

**F: Wie lange dauert die Verarbeitung?**  
A: Je nach PDF-Größe und Anzahl: LEC-Parser ~1-5 Min, SPL-Parser mit OCR ~5-30 Min pro Dokument.

**F: Kann ich eigene Parser hinzufügen?**  
A: Ja, siehe Abschnitt "Entwicklung" für das Parser-Interface.

**F: Werden die Original-PDFs geändert?**  
A: Nein, PDFs werden nur gelesen. Alle Ausgaben gehen nach `output/`.

## Performance-Tipps

1. **OCR nur bei Bedarf**: `spl_ocr_only_if_gibberish: true` in config.yaml
2. **Embedding-Model**: Kleinere Modelle für schnellere Suche
3. **Batch-Verarbeitung**: Nutze die Komplett-Pipeline für mehrere Dokumente
4. **SSD verwenden**: Deutlich schnellere I/O-Performance

## Lizenz

Siehe [LICENSE](LICENSE) für Details.

## Support & Beitragen

- **Issues**: [GitHub Issues](https://github.com/Gregorfun/Kran-doc/issues)
- **Dokumentation**: [Wiki](https://github.com/Gregorfun/Kran-doc/wiki)
- **Diskussionen**: [GitHub Discussions](https://github.com/Gregorfun/Kran-doc/discussions)

Bei Fragen oder Problemen bitte ein Issue erstellen.

## Danksagungen

Dieses Projekt nutzt die folgenden Open-Source-Bibliotheken:
- Flask - Web-Framework
- PyPDF - PDF-Verarbeitung
- Tesseract - OCR
- sentence-transformers - Semantische Suche
- PyTorch - Machine Learning
