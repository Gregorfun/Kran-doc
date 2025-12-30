# PDFDoc / Kran-Tools

## Aktuelle Version
**v0.3.0**

## Letzte Änderungen
- Feat: Community L�sungen + Review Flow
- Feat: Admin- und Account-Login/Register UI

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
