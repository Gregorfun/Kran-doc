# PDFDoc / Kran-Tools

## Aktuelle Version
**v0.2.0**

## Letzte Änderungen
- Feat: Webapp UI/Antworten verbessert
- Feat: Semantischer Index/Embedding-Build �berarbeitet

## Ordnerstruktur

Typische Struktur (Windows/OneDrive):

```text
C:\Users\Gregor sein\OneDrive\PDFDoc\PDFDoc\kran-tools\
├─ scripts\          # Python-Skripte (Parser, Pipeline, Report)
├─ webapp\           # Flask-Weboberfläche
├─ config\           # Zentrale Konfiguration (config.yaml)
├─ input\
│  ├─ pdf\           # Eingabe-PDFs (BAL, LEC, SPL, BMK ...)
├─ output\
│  ├─ models\        # JSON-Wissensmodule pro Kranmodell
│  ├─ reports\       # Markdown-Reports und globale Indizes
├─ pdfdoc.bat        # Doppelklick-Starter für das CLI-Menü
├─ requirements.txt  # Python-Abhängigkeiten
└─ README.md         # Dieses Dokument
