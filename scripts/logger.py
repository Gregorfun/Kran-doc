"""
Logging-Konfiguration für PDFDoc / Kran-Tools

Zentrales Logging-Modul für konsistente Logging-Ausgaben im gesamten Projekt.

Verwendung:
    from scripts.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("Verarbeite Datei...")
    logger.error("Fehler aufgetreten")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

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


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    enable_colors: bool = True
) -> None:
    """
    Konfiguriert das globale Logging-System.
    
    Args:
        level: Log-Level (z.B. logging.INFO, logging.DEBUG)
        log_file: Optional: Pfad zur Log-Datei
        enable_colors: Ob Farben in Console aktiviert werden sollen
            (wird von NO_COLOR/FORCE_COLOR Umgebungsvariablen überschrieben)
    """
    import os
    
    # Umgebungsvariablen haben Priorität
    no_color = os.getenv("NO_COLOR", "") != ""
    force_color = os.getenv("FORCE_COLOR", "") != ""
    
    if force_color:
        enable_colors = True
    elif no_color:
        enable_colors = False
    
    # Root Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Entferne existierende Handler
    root_logger.handlers.clear()
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if enable_colors and sys.stdout.isatty():
        console_format = ColoredFormatter(
            fmt="%(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )
    else:
        console_format = logging.Formatter(
            fmt="%(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )
    
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # File Handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        
        file_format = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Gibt einen Logger mit dem angegebenen Namen zurück.
    
    Args:
        name: Name des Loggers (üblicherweise __name__ des Moduls)
        
    Returns:
        Konfigurierter Logger
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Verarbeitung gestartet")
    """
    return logging.getLogger(name)


# Default-Konfiguration beim Import
# Kann später mit setup_logging() überschrieben werden
def _init_default_logging() -> None:
    """Initialisiert Default-Logging beim ersten Import."""
    import os
    
    # Log-Level aus Umgebung oder INFO
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    
    # Log-Datei aus Umgebung (optional)
    log_file_str = os.getenv("LOG_FILE", "")
    log_file = Path(log_file_str) if log_file_str else None
    
    # Farben aus Umgebung prüfen
    # NO_COLOR standard: https://no-color.org/
    no_color = os.getenv("NO_COLOR", "") != ""
    force_color = os.getenv("FORCE_COLOR", "") != ""
    
    # Farben aktivieren wenn:
    # - FORCE_COLOR gesetzt, oder
    # - NO_COLOR nicht gesetzt UND Terminal ist TTY
    colors_enabled = force_color or (not no_color and sys.stdout.isatty())
    
    setup_logging(level=level, log_file=log_file, enable_colors=colors_enabled)


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
