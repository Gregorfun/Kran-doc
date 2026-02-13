"""
Logging-Konfiguration für PDFDoc / Kran-Tools

Zentrales Logging-Modul für konsistente Logging-Ausgaben im gesamten Projekt.

Unterstützt:
- Farbige Konsole (für Entwicklung)
- JSON-Logging (für Produktion/Monitoring)
- Datei-Logging mit strukturiertem Format

Verwendung:
    from scripts.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Verarbeite Datei...")
    logger.error("Fehler aufgetreten")

Umgebungsvariablen:
    LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
    LOG_FILE: Pfad zur Log-Datei (optional)
    LOG_FORMAT: "colored" (Konsole) oder "json" (Datei)
    NO_COLOR: Disable Farbig Output (https://no-color.org/)
    FORCE_COLOR: Erzwinge Farbig Output
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# Farben für Console-Output
class Colors:
    """ANSI-Farbcodes für Terminal-Ausgabe."""

    RESET = "\033[0m"
    BOLD = "\033[1m"

    # Standard Farben
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Hell-Varianten
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"


class ColoredFormatter(logging.Formatter):
    """Formatter mit Farb-Support für unterschiedliche Log-Level."""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.CYAN,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BOLD + Colors.RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Formatiert Log-Record mit Farben."""
        # Farbe für Level
        level_color = self.LEVEL_COLORS.get(record.levelno, "")
        record.levelname = f"{level_color}{record.levelname}{Colors.RESET}"

        # Modul-Name in Cyan
        record.name = f"{Colors.BRIGHT_CYAN}{record.name}{Colors.RESET}"

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """Formatter für strukturiertes JSON-Logging (Production)."""

    def format(self, record: logging.LogRecord) -> str:
        """Konvertiert Log-Record zu JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Zusätzliche Context-Daten
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Zusätzliche Fields aus extra dict
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)  # type: ignore

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    level: int = logging.INFO, log_file: Optional[Path] = None, enable_colors: bool = True, format_type: str = "colored"
) -> None:
    """
    Konfiguriert das globale Logging-System.

    Args:
        level: Log-Level (z.B. logging.INFO, logging.DEBUG)
        log_file: Optional: Pfad zur Log-Datei
        enable_colors: Farbige Console-Ausgabe
        format_type: "colored" (Entwicklung) oder "json" (Produktion)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Existierende Handler entfernen
    root_logger.handlers = []

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if format_type == "json":
        console_format = JSONFormatter()
    elif enable_colors and sys.stdout.isatty():
        console_format = ColoredFormatter(fmt="%(levelname)-8s | %(name)s | %(message)s", datefmt="%H:%M:%S")
    else:
        console_format = logging.Formatter(fmt="%(levelname)-8s | %(name)s | %(message)s", datefmt="%H:%M:%S")

    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File Handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)

        # Datei-Logging immer als JSON (für Parsing/Monitoring)
        file_format = JSONFormatter()
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Gibt einen konfiguriert Logger zurück.

    Args:
        name: Name des Loggers (meist __name__)

    Returns:
        Konfigurierter Logger

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Verarbeitung gestartet")
    """
    return logging.getLogger(name)


# Default-Konfiguration beim Import
def _init_default_logging() -> None:
    """Initialisiert Default-Logging beim ersten Import."""
    # Log-Level aus Umgebung oder INFO
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    # Log-Datei aus Umgebung (optional)
    log_file_str = os.getenv("LOG_FILE", "")
    log_file = Path(log_file_str) if log_file_str else None

    # Format aus Umgebung
    format_type = os.getenv("LOG_FORMAT", "colored")

    # Farben aus Umgebung prüfen
    # NO_COLOR standard: https://no-color.org/
    no_color = os.getenv("NO_COLOR", "") != ""
    force_color = os.getenv("FORCE_COLOR", "") != ""

    # Farben aktivieren wenn:
    # - FORCE_COLOR gesetzt, oder
    # - NO_COLOR nicht gesetzt UND Terminal ist TTY
    colors_enabled = force_color or (not no_color and sys.stdout.isatty())

    setup_logging(level=level, log_file=log_file, enable_colors=colors_enabled, format_type=format_type)


# Automatische Initialisierung
_init_default_logging()


if __name__ == "__main__":
    # Demo der verschiedenen Log-Level
    logger = get_logger("demo")

    logger.debug("Debug-Nachricht - Details für Entwickler")
    logger.info("Info-Nachricht - Normale Programm-Ausgabe")
    logger.warning("Warning-Nachricht - Potenzielle Probleme")
    logger.error("Error-Nachricht - Fehler aufgetreten")
    logger.critical("Critical-Nachricht - Kritischer Fehler")
