# Makefile für PDFDoc / Kran-Tools
# Vereinfacht häufige Entwicklungs- und Build-Aufgaben

.PHONY: help install setup test lint format clean run-cli run-webapp dev-install check tools health perf docs

# Default target
help:
	@echo "PDFDoc / Kran-Tools - Verfügbare Befehle:"
	@echo ""
	@echo "  make install      - Installiert Abhängigkeiten"
	@echo "  make setup        - Führt Setup-Skript aus"
	@echo "  make dev-install  - Installiert Dev-Dependencies"
	@echo "  make test         - Führt Tests aus"
	@echo "  make lint         - Prüft Code-Qualität (flake8)"
	@echo "  make format       - Formatiert Code (black, isort)"
	@echo "  make check        - Führt alle Checks aus (lint + format-check)"
	@echo "  make clean        - Löscht generierte Dateien"
	@echo "  make run-cli      - Startet CLI-Menü"
	@echo "  make run-webapp   - Startet Web-Interface"
	@echo "  make health       - System Health Check"
	@echo "  make perf         - Performance-Profiling"
	@echo "  make docs         - Generiert Dokumentation"
	@echo "  make tools        - Zeigt verfügbare Tools"
	@echo ""

# Installation
install:
	pip install -r requirements.txt

# Setup durchführen
setup:
	python setup.py

# Dev-Dependencies installieren
dev-install: install
	pip install -r requirements-dev.txt
	pre-commit install

# Tests ausführen (wenn vorhanden)
test:
	@echo "Führe Tests aus..."
	python -m pytest tests/ -v --tb=short || python -m py_compile scripts/*.py webapp/app.py

# Code-Qualität prüfen
lint:
	@echo "Prüfe Code mit flake8..."
	flake8 scripts/ webapp/ --max-line-length=120 --extend-ignore=E203,W503 --exclude=venv,env,.venv,__pycache__

# Code formatieren
format:
	@echo "Formatiere Code mit black..."
	black scripts/ webapp/ --line-length=120 --exclude='/(venv|env|\.venv|__pycache__)/'
	@echo "Sortiere Imports mit isort..."
	isort scripts/ webapp/ --profile=black --line-length=120 --skip=venv --skip=env --skip=.venv

# Format-Check (ohne Änderungen)
format-check:
	@echo "Prüfe Code-Formatierung..."
	black scripts/ webapp/ --check --line-length=120 --exclude='/(venv|env|\.venv|__pycache__)/'
	isort scripts/ webapp/ --check-only --profile=black --line-length=120 --skip=venv --skip=env --skip=.venv

# Alle Checks
check: lint format-check test
	@echo "Alle Checks erfolgreich! ✓"

# Aufräumen
clean:
	@echo "Lösche generierte Dateien..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Aufräumen abgeschlossen."

# CLI starten
run-cli:
	python scripts/pdfdoc_cli.py

# Webapp starten
run-webapp:
	python webapp/app.py

# Pre-commit auf allen Dateien ausführen
precommit-all:
	pre-commit run --all-files

# System Health Check
health:
	@echo "Führe System Health Check aus..."
	python tools/health_check.py

# Performance-Profiling Demo
perf:
	@echo "Performance-Monitoring verfügbar unter tools/performance_monitor.py"
	@echo "Integration in eigene Skripte möglich mit: @profile decorator"

# Dokumentation generieren
docs:
	@echo "Generiere API-Dokumentation..."
	python tools/doc_generator.py scripts -o docs/api-scripts.md
	python tools/doc_generator.py webapp -o docs/api-webapp.md
	python tools/doc_generator.py tools -o docs/api-tools.md
	@echo "Dokumentation generiert in docs/"

# Zeige verfügbare Tools
tools:
	@echo ""
	@echo "Verfügbare Tools in tools/:"
	@echo "  - performance_monitor.py  - Performance-Profiling"
	@echo "  - parallel_processor.py   - Parallele Verarbeitung"
	@echo "  - cache_manager.py        - Erweitertes Caching"
	@echo "  - health_check.py         - System Health Check"
	@echo "  - doc_generator.py        - Dokumentations-Generator"
	@echo "  - test_runner.py          - Test-Runner"
	@echo ""
	@echo "Siehe docs/ für Details zur Verwendung"
	@echo ""
