# Tools für Kran-Doc

Dieses Verzeichnis enthält fortgeschrittene Werkzeuge zur Verbesserung von Performance, Testing und Dokumentation.

## Verfügbare Tools

### 1. Performance Monitor (`performance_monitor.py`)
Performance-Profiling und Monitoring für zeitkritische Operationen.

```python
from tools import profile

@profile
def my_function():
    pass
```

### 2. Parallel Processor (`parallel_processor.py`)
Parallele Verarbeitung von PDFs mit Multiprocessing.

```python
from tools.parallel_processor import process_pdfs_parallel

results, failed = process_pdfs_parallel(pdf_files, parser_func)
```

### 3. Cache Manager (`cache_manager.py`)
Intelligentes Caching-System mit TTL-Support.

```python
from tools import cached

@cached(ttl=3600)
def expensive_function():
    pass
```

### 4. Health Check (`health_check.py`)
System-Gesundheitsüberwachung.

```bash
python tools/health_check.py
```

### 5. Documentation Generator (`doc_generator.py`)
Automatische API-Dokumentation.

```bash
python tools/doc_generator.py scripts -o docs/api.md
```

### 6. Test Runner (`test_runner.py`)
Test-Ausführung und Coverage-Reports.

```bash
python tools/test_runner.py -v --coverage
```

## Schnellstart

```bash
# Via Makefile
make tools      # Zeigt verfügbare Tools
make health     # Health Check
make docs       # Dokumentation generieren
make perf       # Performance-Info

# Direkt
python tools/health_check.py
python tools/doc_generator.py scripts
```

## Weitere Informationen

Siehe [IMPROVEMENTS.md](../docs/IMPROVEMENTS.md) für detaillierte Dokumentation.
