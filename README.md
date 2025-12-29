# PDFDoc / Kran-Tools

## Aktuelle Version
**v0.1.0**

## Letzte Änderungen
- Initialer Stand
> Vollständige Historie: siehe `CHANGELOG.md`

**Ziel:**  
PDF- und Schaltplan-Dokumente von Liebherr-Mobilkranen (z. B. LTM1110-5.1) automatisch in **strukturierte JSON-Wissensmodule** umwandeln, die später von einem Kran-GPT oder anderen Tools genutzt werden können.

Das System:

- erkennt das **Kranmodell automatisch** aus dem PDF-Inhalt (z. B. `LTM1110-5.1`),
- parst verschiedene Dokumenttypen:
  - **Wissensmodule** aus allgemeinen PDFs (BAL, Bedienungsanleitung usw.),
  - **LEC-Fehlercodelisten**,
  - **SPL-Schaltpläne** (mit OCR-Fallback),
  - **BMK-Listen** (Unterwagen/Oberwagen),
- erzeugt pro Modell ein gemeinsames `*_GPT51_FULL_KNOWLEDGE.json`,
- baut **globale Indizes** (Fehlercodes/BMKs),
- bietet eine **CLI mit Menü** und eine **Weboberfläche**.

---

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
