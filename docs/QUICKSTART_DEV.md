# Schnellstart für Entwickler

Dieser Guide hilft neuen Entwicklern, schnell mit dem Kran-Doc Projekt zu starten.

## Setup (5 Minuten)

### 1. Repository klonen

```bash
git clone https://github.com/Gregorfun/Kran-doc.git
cd Kran-doc
```

### 2. Virtuelle Umgebung erstellen

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Dependencies installieren

```bash
# Production-Dependencies
make install

# Für Entwicklung (inkl. Testing)
make dev-install
```

### 4. System-Check

```bash
make health
```

## Täglicher Workflow

### Vor dem Programmieren

```bash
# System-Check
make health

# Neueste Änderungen holen
git pull
```

### Während des Programmierens

```bash
# Code formatieren
make format

# Tests ausführen
make test

# Code-Qualität prüfen
make lint
```

### Nach Änderungen

```bash
# Alle Checks
make check

# Dokumentation aktualisieren
make docs
```

## Performance-Optimierung

### 1. Profiling hinzufügen

```python
from tools import profile

@profile
def my_slow_function():
    # Code
    pass
```

### 2. Caching verwenden

```python
from tools import cached

@cached(ttl=3600)  # 1 Stunde Cache
def expensive_calculation():
    # Code
    pass
```

### 3. Parallele Verarbeitung

```python
from tools.parallel_processor import process_pdfs_parallel

results, failed = process_pdfs_parallel(
    pdf_files=my_pdfs,
    parser_func=my_parser,
    max_workers=4
)
```

## Testing

### Tests schreiben

```python
# tests/test_my_feature.py
import pytest

@pytest.mark.unit
def test_my_feature():
    from scripts.my_module import my_function
    result = my_function(42)
    assert result == 1764
```

### Tests ausführen

```bash
# Alle Tests
pytest tests/ -v

# Einzelner Test
pytest tests/test_my_feature.py::test_my_feature -v

# Mit Coverage
pytest tests/ --cov=scripts --cov-report=html
```

## Dokumentation

### API-Docs generieren

```bash
make docs
```

Ergebnis in `docs/api-*.md`

### Eigenen Code dokumentieren

```python
def my_function(x: int, y: int) -> int:
    """
    Berechnet die Summe zweier Zahlen.
    
    Args:
        x: Erste Zahl
        y: Zweite Zahl
        
    Returns:
        Summe von x und y
    """
    return x + y
```

## Häufige Aufgaben

### Neue Funktion hinzufügen

1. Code schreiben
2. `@profile` und `@cached` wo sinnvoll
3. Tests schreiben
4. `make test` ausführen
5. `make docs` für Dokumentation

### Performance-Problem fixen

1. `@profile` zum Code hinzufügen
2. Skript ausführen
3. Performance-Report analysieren
4. Bottleneck optimieren
5. Erneut profilen

### Bug fixen

1. Test schreiben der Bug reproduziert
2. Test sollte fehlschlagen
3. Bug fixen
4. Test sollte passen
5. Alle Tests ausführen

## Nützliche Befehle

```bash
# Übersicht aller Befehle
make help

# System-Status
make health

# Tools-Übersicht
make tools

# Web-Interface starten
make run-webapp

# CLI-Menü starten
make run-cli
```

## Troubleshooting

### Import-Fehler

```bash
# Python-Path prüfen
python -c "import sys; print(sys.path)"

# Dependencies neu installieren
pip install -r requirements.txt --upgrade
```

### Tests schlagen fehl

```bash
# Dev-Dependencies installieren
pip install -r requirements-dev.txt

# Einzelnen Test debuggen
pytest tests/test_failing.py -v -s
```

### Performance-Probleme

```bash
# Health-Check
make health

# Performance-Report
python tools/performance_monitor.py
```

## Weitere Ressourcen

- **Umfassende Dokumentation:** [docs/IMPROVEMENTS.md](IMPROVEMENTS.md)
- **Tools-Übersicht:** [tools/README.md](../tools/README.md)
- **Verbesserungs-Summary:** [docs/IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md)
- **GitHub Issues:** [github.com/Gregorfun/Kran-doc/issues](https://github.com/Gregorfun/Kran-doc/issues)

## Best Practices

1. ✅ Immer Tests schreiben
2. ✅ Code dokumentieren (Docstrings)
3. ✅ Performance-kritische Funktionen profilen
4. ✅ Teure Berechnungen cachen
5. ✅ Viele Dateien parallel verarbeiten
6. ✅ `make check` vor jedem Commit
7. ✅ Regelmäßig `make health` ausführen

## Support

Bei Fragen:
1. Dokumentation durchsuchen
2. `make health` ausführen
3. GitHub Issue erstellen
