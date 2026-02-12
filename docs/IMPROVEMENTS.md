# Verbesserungen für Kran-Tools

Dieses Dokument beschreibt alle neuen Tools und Verbesserungen für das Kran-Tools Projekt.

## Übersicht der Verbesserungen

### 1. Performance-Monitoring (`tools/performance_monitor.py`)

**Zweck:** Profiling und Performance-Tracking für zeitkritische Operationen.

**Features:**
- Funktions-Profiling mit Decorator
- Execution-Zeit-Messung
- Memory-Tracking
- Automatische Statistiken
- Performance-Reports

**Verwendung:**

```python
from tools.performance_monitor import profile, print_performance_report

@profile
def parse_pdf(pdf_path):
    # Your PDF parsing code
    pass

# Am Ende des Skripts
print_performance_report()
```

**Standalone-Nutzung:**

```bash
python tools/performance_monitor.py
```

### 2. Parallele Verarbeitung (`tools/parallel_processor.py`)

**Zweck:** Beschleunigung der PDF-Verarbeitung durch Multiprocessing/Threading.

**Features:**
- Multiprocessing für CPU-intensive Aufgaben
- Thread-Pool für I/O-intensive Operationen
- Progress-Tracking
- Error-Handling mit Retry
- Batch-Verarbeitung

**Verwendung:**

```python
from tools.parallel_processor import process_pdfs_parallel

# Parallele Verarbeitung mehrerer PDFs
results, failed = process_pdfs_parallel(
    pdf_files=list_of_pdfs,
    parser_func=your_parser_function,
    max_workers=4
)
```

**Integration in existierende Parser:**

```python
from tools.parallel_processor import ParallelProcessor

processor = ParallelProcessor(max_workers=4)
results = processor.process_files(
    files=pdf_files,
    process_func=parse_single_pdf,
    use_processes=True  # True für CPU-intensiv
)
```

### 3. Erweitertes Caching (`tools/cache_manager.py`)

**Zweck:** Intelligentes Caching zur Vermeidung redundanter Berechnungen.

**Features:**
- Datei-basiertes Caching
- Memory-Cache (LRU)
- TTL (Time-To-Live) Support
- Cache-Invalidierung
- Cache-Statistiken

**Verwendung:**

```python
from tools.cache_manager import cached

@cached(ttl=3600)  # Cache für 1 Stunde
def expensive_embedding_calculation(text):
    # Rechenintensive Operation
    return embeddings

# Cache-Statistiken anzeigen
from tools.cache_manager import get_cache_manager
cache = get_cache_manager()
cache.print_stats()
```

**Cache invalidieren:**

```python
cache.invalidate()  # Alle Caches löschen
cache.invalidate("embedding_")  # Nur bestimmte Pattern
```

### 4. System Health Check (`tools/health_check.py`)

**Zweck:** Überwachung der System-Gesundheit und Dependencies.

**Features:**
- Python-Version Check
- Dependency-Checks
- Disk-Space Monitoring
- Memory-Check
- Tesseract OCR Check
- JSON/Textuelle Reports

**Verwendung:**

```bash
# Einfacher Check
python tools/health_check.py

# Mit JSON-Output
python tools/health_check.py --json

# Report speichern
python tools/health_check.py -o health_report.json

# Via Makefile
make health
```

**In Python:**

```python
from tools.health_check import HealthChecker

checker = HealthChecker()
results = checker.run_all_checks()
checker.print_report()
```

### 5. Dokumentations-Generator (`tools/doc_generator.py`)

**Zweck:** Automatische API-Dokumentation aus Docstrings.

**Features:**
- AST-basierte Docstring-Extraktion
- Markdown-Dokumentation
- Funktions- und Klassen-Übersicht
- Hierarchische Struktur
- Automatische Inhaltsverzeichnisse

**Verwendung:**

```bash
# Dokumentation für scripts/ generieren
python tools/doc_generator.py scripts -o docs/api-scripts.md

# Modul-Übersicht
python tools/doc_generator.py scripts --overview

# Via Makefile (generiert alle)
make docs
```

### 6. Test-Framework (`tests/`, `tools/test_runner.py`)

**Zweck:** Automatisiertes Testing mit pytest.

**Features:**
- Pytest-Integration
- Test-Discovery
- Coverage-Reports
- Unit- und Integration-Tests
- Performance-Tests

**Verwendung:**

```bash
# Alle Tests ausführen
pytest tests/ -v

# Mit Coverage
pytest tests/ --cov=scripts --cov=webapp --cov-report=html

# Via Makefile
make test

# Test-Runner
python tools/test_runner.py -v --coverage
```

**Eigene Tests schreiben:**

```python
# tests/test_my_module.py
import pytest

@pytest.mark.unit
def test_my_function():
    from scripts.my_module import my_function
    result = my_function(5)
    assert result == 25
```

## Integration in existierende Skripte

### Beispiel: LEC-Parser mit Performance-Monitoring und Parallel Processing

```python
# In scripts/lec_parser.py

from tools.performance_monitor import profile
from tools.parallel_processor import ParallelProcessor

@profile
def parse_single_lec_pdf(pdf_path):
    # Existing parsing logic
    pass

def process_all_lec_pdfs():
    pdf_files = list(INPUT_DIR.glob("**/*.pdf"))
    
    # Parallele Verarbeitung
    processor = ParallelProcessor(max_workers=4)
    results = processor.process_files(
        files=pdf_files,
        process_func=parse_single_lec_pdf,
        use_processes=True
    )
    
    # Performance-Report am Ende
    from tools.performance_monitor import print_performance_report
    print_performance_report()
```

### Beispiel: Webapp mit Caching

```python
# In webapp/app.py

from tools.cache_manager import cached

@app.route('/api/search/<query>')
@cached(ttl=300)  # 5 Minuten Cache
def search_knowledge(query):
    # Suche in Wissensmodulen
    results = expensive_search_operation(query)
    return jsonify(results)
```

## Makefile-Befehle

Alle neuen Tools sind über das Makefile verfügbar:

```bash
make help       # Zeigt alle Befehle
make install    # Installiert Dependencies
make dev-install # Installiert Dev-Dependencies + Testing
make test       # Führt Tests aus
make health     # System Health Check
make docs       # Generiert API-Dokumentation
make tools      # Zeigt verfügbare Tools
make perf       # Info zu Performance-Monitoring
```

## Performance-Tipps

### 1. Parallele PDF-Verarbeitung

```python
# Vorher: Sequenziell
for pdf in pdf_files:
    parse_pdf(pdf)

# Nachher: Parallel (4x schneller bei 4 Cores)
from tools.parallel_processor import process_pdfs_parallel
results, failed = process_pdfs_parallel(pdf_files, parse_pdf, max_workers=4)
```

### 2. Caching für teure Berechnungen

```python
# Vorher: Immer neu berechnen
def get_embeddings(text):
    return model.encode(text)  # Langsam!

# Nachher: Mit Cache
@cached(ttl=3600)
def get_embeddings(text):
    return model.encode(text)  # Nur beim ersten Mal langsam
```

### 3. Performance-Monitoring aktivieren

```python
# Am Anfang des Skripts
from tools.performance_monitor import get_monitor
monitor = get_monitor()
monitor.enable_memory_tracking()

# Kritische Funktionen markieren
@monitor.profile
def critical_function():
    pass

# Am Ende Report ausgeben
monitor.print_report()
```

## Development Workflow

1. **Setup:**
   ```bash
   make dev-install
   ```

2. **Entwicklung:**
   ```bash
   # Code schreiben
   # Tests schreiben in tests/
   ```

3. **Testing:**
   ```bash
   make test
   make health  # System-Check
   ```

4. **Code Quality:**
   ```bash
   make format  # Code formatieren
   make lint    # Code prüfen
   make check   # Alle Checks
   ```

5. **Dokumentation:**
   ```bash
   make docs  # API-Docs generieren
   ```

## Best Practices

### 1. Performance-kritische Funktionen profilen

```python
from tools.performance_monitor import profile

@profile
def parse_large_pdf(path):
    # Code
    pass
```

### 2. Viele Dateien parallel verarbeiten

```python
from tools.parallel_processor import ParallelProcessor

processor = ParallelProcessor()
results = processor.process_files(files, parse_func)
```

### 3. Teure Berechnungen cachen

```python
from tools.cache_manager import cached

@cached(ttl=3600)
def expensive_calculation(input):
    # Code
    pass
```

### 4. Regelmäßige Health-Checks

```bash
# Vor größeren Operations
make health

# In CI/CD Pipeline
python tools/health_check.py --json
```

### 5. Tests schreiben

```python
# tests/test_my_feature.py
@pytest.mark.unit
def test_my_feature():
    assert my_function() == expected_result
```

## Migration-Guide

### Schritt 1: Dependencies installieren

```bash
pip install -r requirements-dev.txt
```

### Schritt 2: Bestehende Parser updaten

Füge zu kritischen Funktionen hinzu:

```python
from tools.performance_monitor import profile

@profile
def existing_function():
    # existing code
    pass
```

### Schritt 3: Parallele Verarbeitung einbauen

Ersetze Loops durch:

```python
from tools.parallel_processor import process_pdfs_parallel
results, failed = process_pdfs_parallel(files, parser_func)
```

### Schritt 4: Caching hinzufügen

Für teure Funktionen:

```python
from tools.cache_manager import cached

@cached(ttl=3600)
def expensive_function():
    pass
```

### Schritt 5: Tests schreiben

Erstelle `tests/test_my_module.py` und führe aus:

```bash
make test
```

## Troubleshooting

### ImportError bei Tools

```bash
# Stelle sicher, dass du im Projekt-Root bist
cd /path/to/Kran-doc

# Python-Path prüfen
python -c "import sys; print(sys.path)"
```

### Tests schlagen fehl

```bash
# Dependencies neu installieren
pip install -r requirements-dev.txt

# Einzelnen Test ausführen
pytest tests/test_tools.py::test_cache_manager_basic -v
```

### Performance-Probleme

```bash
# Performance-Report erstellen
python tools/performance_monitor.py

# Health-Check ausführen
make health
```

## Weitere Informationen

- API-Dokumentation: `docs/api-*.md` (nach `make docs`)
- Test-Coverage: `htmlcov/index.html` (nach `pytest --cov`)
- Performance-Reports: `output/performance/`
- Health-Reports: `output/health/`

## Support

Bei Fragen oder Problemen:
1. Dokumentation prüfen: `make docs`
2. Health-Check: `make health`
3. Tests ausführen: `make test`
4. Issue erstellen auf GitHub
