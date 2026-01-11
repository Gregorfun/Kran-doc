# PDFDoc / Kran-Tools

**Automatisierte Extraktion und Verwaltung von Kranendokumentation aus PDF-Dateien**

## Aktuelle Version
**v0.5.0**

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.1+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Überblick

PDFDoc / Kran-Tools ist eine Python-basierte Anwendung zur automatischen Extraktion und Analyse von technischen Dokumentationen für Liebherr-Krane. Das System verarbeitet verschiedene PDF-Dokumenttypen (Fehlercodes, Schaltpläne, BMK-Listen, Handbücher) und erstellt strukturierte Wissensmodule.

### Hauptfunktionen

- 📄 **PDF-Parsing**: Automatische Extraktion von Fehlercodes (LEC), Schaltplänen (SPL), BMK-Listen
- 🧠 **Wissensmodule**: Strukturierte JSON-basierte Wissensrepräsentation pro Kranmodell
- 🔍 **Semantische Suche**: Embedding-basierte Suche in technischer Dokumentation
- 🌐 **Web-Interface**: Flask-basierte Weboberfläche für einfache Bedienung
- 📊 **Report-Generierung**: Automatische Erstellung von Übersichten und Indizes
- 🤖 **Community-Lösungen**: Verwaltung und Review von Lösungsvorschlägen

## Letzte Änderungen

Siehe [CHANGELOG.md](CHANGELOG.md) für eine vollständige Liste der Änderungen.

## Schnellstart

### Voraussetzungen

- Python 3.8 oder höher
- Tesseract OCR (optional, für OCR-Funktionalität)
- 4 GB RAM (empfohlen 8 GB für Embeddings)

### Installation

1. **Repository klonen**
   ```bash
   git clone https://github.com/Gregorfun/Kran-doc.git
   cd Kran-doc
   ```

2. **Virtuelle Umgebung erstellen**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
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

Dann Browser öffnen: `http://localhost:5000`

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
