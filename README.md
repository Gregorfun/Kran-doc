# 🏗️ Kran-Doc

**Open-source platform for parsing, structuring and semantically searching crane documentation.**

Kran-Doc hilft Monteuren, Werkstätten und Entwicklern dabei, technische Kran-Dokumente wie **LEC-Fehlerlisten, BMK-Listen, SPL-Schaltpläne und Manuals** schneller auszuwerten und intelligent miteinander zu verknüpfen.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.1+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## Warum Kran-Doc?

Technische PDF-Dokumentation ist oft unübersichtlich, verteilt und schwer durchsuchbar. Kran-Doc baut daraus eine strukturierte Wissensbasis:

- 📄 **PDF-Parsing** für LEC, BMK, SPL und Manuals
- 🧠 **Wissensmodule** als strukturierte JSON-Daten pro Kranmodell
- 🔍 **Semantische Suche** über Embeddings
- 🔗 **Verknüpfung** zwischen Fehlercodes, Baugruppen und Hinweisen
- 🌐 **Flask-Weboberfläche** für Werkstatt- und Monteur-Einsatz
- 🤝 **Community-Lösungen** mit Review-Workflow

---

## Projektstatus

**Aktuelle Version:** `v0.5.0`

### Parser-Status

| Bereich | Status | Hinweis |
|---|---|---|
| LEC | stabil | Fehlercodes und Basis-Metadaten |
| BMK | stabil | Komponenten- und LSB-Zuordnung |
| SPL | in Arbeit | OCR-/Layout-Qualität stark PDF-abhängig |
| Manuals | experimentell | für Wissensaufbau und semantische Suche |

---

## Quickstart

### Docker (empfohlen)

```bash
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc
docker compose up --build
```

Danach im Browser öffnen:

```text
http://localhost:5000
```

### Lokal

Voraussetzungen:

- Python 3.11 oder höher
- Tesseract OCR optional für Bild-/Scan-PDFs
- 4 GB RAM, empfohlen 8 GB bei Embeddings

```bash
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc
python -m venv .venv
```

**Windows**

```bash
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

Dann:

```bash
pip install -r requirements.txt
python webapp/app.py
```

Danach im Browser öffnen:

```text
http://localhost:5000
```

---

## Typischer Workflow

1. PDFs in die passenden `input/`-Ordner legen
2. Parser oder Komplett-Pipeline ausführen
3. JSON-Wissensmodule unter `output/models/` erzeugen
4. Embeddings / Indizes bauen
5. Über die Weboberfläche suchen und Beziehungen nutzen

### Beispielbefehle

```bash
python scripts/lec_parser.py
python scripts/bmk_parser.py
python scripts/spl_parser.py
python scripts/wissensmodul_builder.py
python scripts/build_local_embedding_index.py
python webapp/app.py
```

---

## Projektstruktur

```text
Kran-doc/
├─ config/                    # Konfigurationsdateien
├─ scripts/                   # Parser, Builder, CLI, Doctor, Reports
├─ webapp/                    # Flask UI
├─ input/                     # Eingabe-PDFs (nicht versioniert)
├─ output/                    # Generierte JSONs, Reports, Embeddings
├─ community/                 # Community-Daten
├─ docs/                      # Zusatzdokumentation
├─ tools/                     # Hilfsskripte
├─ requirements.txt
├─ docker-compose.yml
├─ Dockerfile
└─ README.md
```

---

## Architektur

Kran-Doc folgt einer modularen Pipeline:

```text
PDF-Dokumente
    ↓
Parser (LEC / BMK / SPL / Manual)
    ↓
Roh-JSON / strukturierte Daten
    ↓
Merge zu Wissensmodulen
    ↓
Embedding-Export / semantischer Index
    ↓
Weboberfläche / Suche / Diagnosehilfe
```

---

## Konfiguration

Die wichtigste Konfiguration liegt in `config/config.yaml`.

Beispiele:

```yaml
lec_dir: "input/lec"
bmk_dir: "input/bmk"
spl_dir: "input/spl"
manuals_dir: "input/manuals"
models_dir: "output/models"
reports_dir: "output/reports"
embeddings_dir: "output/embeddings"
tesseract_cmd: "/usr/bin/tesseract"
ocr_enabled: true
ocr_lang: "deu+eng"
```

Zusätzlich kannst du Umgebungsvariablen nutzen, z. B. für Secrets oder OCR-Pfade.

Siehe auch: `.env.example`

---

## Development

### Qualität & Checks

- CI prüft Syntax, Linting und Basistests
- `tests/` enthält erste Smoke-Tests
- `CONTRIBUTING.md` beschreibt den Beitragsprozess

### Lokale Checks

```bash
python -m compileall -q .
pytest -q
```

---

## Sicherheit

Bitte **keine echten Kundendaten, Geheimnisse oder produktiven `.env`-Dateien** committen.

Weitere Hinweise stehen in [SECURITY.md](SECURITY.md).

---

## Roadmap

- [ ] robustere SPL-/OCR-Auswertung
- [ ] bessere automatische LEC ↔ BMK-Verknüpfung
- [ ] Ausbau der Community-Lösungen mit Review und Voting
- [ ] mehrsprachige Ausgabe mit Deutsch als Primärsprache
- [ ] mobile / feldtaugliche Oberfläche für Monteure
- [ ] weitergehende RAG- und Diagnosefunktionen

---

## FAQ

### Welche PDFs werden unterstützt?
Alle Standard-PDFs. Text-PDFs funktionieren am besten. Für Scan-/Bild-PDFs ist OCR sinnvoll.

### Werden Original-PDFs verändert?
Nein. Die PDFs werden nur gelesen. Ergebnisse landen unter `output/`.

### Kann ich eigene Parser ergänzen?
Ja. Neue Parser können modular in `scripts/` ergänzt werden.

---

## Contributing

Beiträge sind willkommen.

1. Repository forken
2. Feature-Branch anlegen
3. Änderungen testen
4. Pull Request öffnen

Vor dem Beitrag bitte `CONTRIBUTING.md` lesen.

---

## Lizenz

Dieses Projekt steht unter der [MIT License](LICENSE).

---

## Support

- Issues: [GitHub Issues](https://github.com/Gregorfun/Kran-doc/issues)
- Pull Requests: willkommen
- Security-Meldungen: siehe [SECURITY.md](SECURITY.md)
