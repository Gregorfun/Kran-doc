#!/usr/bin/env python3
"""
Setup-Skript für PDFDoc / Kran-Tools

Dieses Skript führt die initiale Einrichtung des Projekts durch:
- Erstellt notwendige Verzeichnisse
- Prüft Python-Version
- Installiert Abhängigkeiten
- Erstellt Konfigurationsdateien
- Führt grundlegende Tests durch
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Tuple

# Farben für Terminal-Ausgabe
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header() -> None:
    """Zeigt den Setup-Header an."""
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}  PDFDoc / Kran-Tools - Setup{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}\n")


def print_success(message: str) -> None:
    """Zeigt eine Erfolgsmeldung an."""
    print(f"{GREEN}✓{RESET} {message}")


def print_warning(message: str) -> None:
    """Zeigt eine Warnung an."""
    print(f"{YELLOW}⚠{RESET} {message}")


def print_error(message: str) -> None:
    """Zeigt eine Fehlermeldung an."""
    print(f"{RED}✗{RESET} {message}")


def print_info(message: str) -> None:
    """Zeigt eine Info-Meldung an."""
    print(f"{BLUE}ℹ{RESET} {message}")


def check_python_version() -> bool:
    """Prüft die Python-Version."""
    print_info("Prüfe Python-Version...")
    
    if sys.version_info < (3, 8):
        print_error(f"Python 3.8+ erforderlich, aber {sys.version} gefunden")
        return False
    
    print_success(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} gefunden")
    return True


def create_directories() -> List[Path]:
    """Erstellt notwendige Verzeichnisse."""
    print_info("Erstelle Verzeichnisstruktur...")
    
    directories = [
        Path("input/lec"),
        Path("input/bmk"),
        Path("input/spl"),
        Path("input/manuals"),
        Path("output/models"),
        Path("output/reports"),
        Path("output/embeddings"),
        Path("logs"),
    ]
    
    created = []
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created.append(directory)
    
    if created:
        for dir_path in created:
            print_success(f"Erstellt: {dir_path}")
    else:
        print_success("Alle Verzeichnisse existieren bereits")
    
    return created


def check_tesseract() -> bool:
    """Prüft ob Tesseract OCR installiert ist."""
    print_info("Prüfe Tesseract OCR Installation...")
    
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print_success(f"Tesseract gefunden: {version_line}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    print_warning("Tesseract OCR nicht gefunden (optional für OCR-Funktionen)")
    print_info("Installation: https://github.com/UB-Mannheim/tesseract/wiki")
    return False


def install_requirements() -> bool:
    """Installiert Python-Abhängigkeiten."""
    print_info("Installiere Python-Abhängigkeiten...")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print_error("requirements.txt nicht gefunden")
        return False
    
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
            capture_output=False
        )
        print_success("Abhängigkeiten erfolgreich installiert")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Installation fehlgeschlagen: {e}")
        return False


def create_env_file() -> bool:
    """Erstellt .env Datei wenn sie nicht existiert."""
    print_info("Prüfe Umgebungskonfiguration...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print_success(".env Datei existiert bereits")
        return True
    
    if not env_example.exists():
        print_warning(".env.example nicht gefunden - überspringe")
        return False
    
    try:
        # Kopiere statt umbenennen, um Template zu erhalten
        import shutil
        shutil.copy(env_example, env_file)
        print_success(".env Datei aus .env.example erstellt")
        print_warning("Bitte .env anpassen mit eigenen Einstellungen!")
        return True
    except (OSError, PermissionError, IOError) as e:
        print_error(f"Konnte .env nicht erstellen: {e}")
        return False


def verify_installation() -> bool:
    """Verifiziert die Installation durch Import-Tests."""
    print_info("Verifiziere Installation...")
    
    critical_imports = [
        "flask",
        "pypdf",
        "yaml",
        "numpy",
    ]
    
    optional_imports = [
        "pytesseract",
        "cv2",
        "sentence_transformers",
        "torch",
    ]
    
    all_ok = True
    
    for module in critical_imports:
        try:
            __import__(module)
            print_success(f"Modul '{module}' verfügbar")
        except ImportError:
            print_error(f"Kritisches Modul '{module}' nicht importierbar")
            all_ok = False
    
    for module in optional_imports:
        try:
            __import__(module)
            print_success(f"Optionales Modul '{module}' verfügbar")
        except ImportError:
            print_warning(f"Optionales Modul '{module}' nicht verfügbar")
    
    return all_ok


def print_next_steps() -> None:
    """Zeigt die nächsten Schritte an."""
    print(f"\n{BOLD}{GREEN}Setup abgeschlossen!{RESET}\n")
    print(f"{BOLD}Nächste Schritte:{RESET}\n")
    print(f"  1. {BOLD}Konfiguration anpassen:{RESET}")
    print(f"     - .env bearbeiten (Tesseract-Pfad, etc.)")
    print(f"     - config/config.yaml bearbeiten\n")
    print(f"  2. {BOLD}PDFs hinzufügen:{RESET}")
    print(f"     - LEC-PDFs nach input/lec/")
    print(f"     - BMK-PDFs nach input/bmk/")
    print(f"     - SPL-PDFs nach input/spl/")
    print(f"     - Handbücher nach input/manuals/\n")
    print(f"  3. {BOLD}Anwendung starten:{RESET}")
    print(f"     - CLI: python scripts/pdfdoc_cli.py")
    print(f"     - Web: python webapp/app.py\n")
    print(f"  4. {BOLD}Dokumentation:{RESET}")
    print(f"     - README.md lesen")
    print(f"     - CONTRIBUTING.md für Entwickler\n")


def main() -> int:
    """Hauptfunktion des Setup-Skripts."""
    print_header()
    
    # Schritt 1: Python-Version prüfen
    if not check_python_version():
        return 1
    
    print()
    
    # Schritt 2: Verzeichnisse erstellen
    create_directories()
    print()
    
    # Schritt 3: Tesseract prüfen
    check_tesseract()
    print()
    
    # Schritt 4: Abhängigkeiten installieren
    if not install_requirements():
        print_error("Setup konnte nicht abgeschlossen werden")
        return 1
    print()
    
    # Schritt 5: .env erstellen
    create_env_file()
    print()
    
    # Schritt 6: Installation verifizieren
    if not verify_installation():
        print_warning("Setup abgeschlossen, aber einige Module fehlen")
    print()
    
    # Nächste Schritte anzeigen
    print_next_steps()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Setup abgebrochen.{RESET}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unerwarteter Fehler: {e}")
        sys.exit(1)
