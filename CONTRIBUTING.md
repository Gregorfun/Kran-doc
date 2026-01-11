# Beitragen zu PDFDoc / Kran-Tools

Vielen Dank für Ihr Interesse, zu PDFDoc / Kran-Tools beizutragen! Dieses Dokument enthält Richtlinien und Best Practices für Beiträge.

## Inhaltsverzeichnis

- [Code of Conduct](#code-of-conduct)
- [Wie kann ich beitragen?](#wie-kann-ich-beitragen)
- [Entwicklungssetup](#entwicklungssetup)
- [Code-Richtlinien](#code-richtlinien)
- [Commit-Richtlinien](#commit-richtlinien)
- [Pull Request Prozess](#pull-request-prozess)

## Code of Conduct

Wir erwarten, dass alle Beitragenden respektvoll und konstruktiv miteinander umgehen. Belästigung und respektloses Verhalten werden nicht toleriert.

## Wie kann ich beitragen?

### Fehler melden

Wenn Sie einen Fehler gefunden haben:

1. Prüfen Sie, ob der Fehler bereits [gemeldet](https://github.com/Gregorfun/Kran-doc/issues) wurde
2. Erstellen Sie ein neues Issue mit:
   - Beschreibung des Fehlers
   - Schritte zur Reproduktion
   - Erwartetes vs. tatsächliches Verhalten
   - Python-Version und Betriebssystem
   - Relevante Logs oder Screenshots

### Feature vorschlagen

Für neue Features:

1. Prüfen Sie bestehende [Feature Requests](https://github.com/Gregorfun/Kran-doc/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)
2. Erstellen Sie ein Issue mit:
   - Beschreibung des Features
   - Use Case / Anwendungsfall
   - Mögliche Implementierungsideen

### Code beitragen

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch (`git checkout -b feature/AmazingFeature`)
3. Committen Sie Ihre Änderungen (siehe [Commit-Richtlinien](#commit-richtlinien))
4. Pushen Sie zum Branch (`git push origin feature/AmazingFeature`)
5. Öffnen Sie einen Pull Request

## Entwicklungssetup

### Voraussetzungen

- Python 3.8+
- Git
- Tesseract OCR (optional)

### Setup

```bash
# Repository klonen
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc

# Virtuelle Umgebung erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt

# Umgebung konfigurieren
cp .env.example .env
# .env anpassen
```

### Tests ausführen

```bash
# Syntax-Check
python -m py_compile scripts/*.py

# Manuelle Tests der Hauptfunktionen
python scripts/pdfdoc_cli.py
```

## Code-Richtlinien

### Python-Stil

- Folgen Sie [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Verwenden Sie Typ-Annotationen (Python 3.8+ kompatibel)
- Maximale Zeilenlänge: 120 Zeichen
- Verwenden Sie aussagekräftige Variablennamen

### Docstrings

Verwenden Sie Google-Style Docstrings:

```python
def parse_pdf(pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
    """
    Parst ein PDF und extrahiert strukturierte Daten.
    
    Args:
        pdf_path: Pfad zur PDF-Datei
        output_dir: Verzeichnis für Ausgabedateien
        
    Returns:
        Dictionary mit extrahierten Daten
        
    Raises:
        FileNotFoundError: Wenn PDF nicht existiert
        ValueError: Wenn PDF-Format ungültig ist
        
    Example:
        >>> result = parse_pdf(Path("input.pdf"), Path("output"))
        >>> print(result["error_codes"])
    """
    # Implementation
```

### Typ-Annotationen

```python
from typing import Dict, List, Optional, Any
from pathlib import Path

def process_data(
    input_path: Path,
    config: Dict[str, Any],
    filters: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Process data with type hints."""
    pass
```

### Error Handling

```python
import logging

logger = logging.getLogger(__name__)

def safe_operation():
    """Handle errors gracefully."""
    try:
        # risky operation
        result = process_data()
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise
    return result
```

### Imports

Organisieren Sie Imports in drei Gruppen:

```python
# Standard-Bibliothek
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Externe Pakete
import flask
import numpy as np
from pypdf import PdfReader

# Lokale Imports
from scripts.config_loader import get_config
from scripts.utils import parse_date
```

## Commit-Richtlinien

Verwenden Sie [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: Neues Feature
- `fix`: Bugfix
- `docs`: Dokumentation
- `style`: Formatierung (keine Code-Änderung)
- `refactor`: Code-Refactoring
- `test`: Tests hinzufügen/ändern
- `chore`: Build/Tooling-Änderungen

### Beispiele

```
feat(parser): Add BMK-Parser für neue PDF-Formate

- Unterstützung für Format v2.0
- Verbesserte OCR-Erkennung
- Tests hinzugefügt

Closes #123
```

```
fix(webapp): Behebe Encoding-Problem bei Umlauten

Umlaute wurden nicht korrekt angezeigt.
UTF-8 Encoding jetzt explizit gesetzt.

Fixes #456
```

## Pull Request Prozess

1. **Branch erstellen**: Feature-Branch vom `main` abzweigen
2. **Code schreiben**: Implementierung mit Tests
3. **Self-Review**: Code selbst überprüfen
4. **PR erstellen**: Aussagekräftige Beschreibung
5. **Review abwarten**: Auf Feedback reagieren
6. **Merge**: Nach Genehmigung wird gemerged

### PR-Beschreibung Template

```markdown
## Beschreibung
Was macht dieser PR?

## Motivation und Kontext
Warum ist diese Änderung notwendig?

## Art der Änderung
- [ ] Bugfix
- [ ] Neues Feature
- [ ] Breaking Change
- [ ] Dokumentation

## Wie wurde getestet?
- [ ] Lokale Tests durchgeführt
- [ ] Manuelle Tests
- [ ] Betroffene Module: ...

## Checklist
- [ ] Code folgt dem Projektstil
- [ ] Docstrings hinzugefügt/aktualisiert
- [ ] Dokumentation aktualisiert
- [ ] CHANGELOG.md aktualisiert
```

## Code Review Checkliste

Als Reviewer:

- [ ] Code ist verständlich und gut dokumentiert
- [ ] Typ-Annotationen vorhanden
- [ ] Error Handling angemessen
- [ ] Keine hardcodierten Pfade/Secrets
- [ ] Performance-Implikationen berücksichtigt
- [ ] Kompatibilität mit bestehenden Features

## Fragen?

Bei Fragen erstellen Sie ein [Issue](https://github.com/Gregorfun/Kran-doc/issues) oder starten eine [Discussion](https://github.com/Gregorfun/Kran-doc/discussions).

Vielen Dank für Ihren Beitrag! 🎉
