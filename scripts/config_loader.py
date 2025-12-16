# Datei: scripts/config_loader.py
"""
Konfigurations-Loader für PDFDoc / Kran-Tools.

- Liest config/config.yaml (wenn vorhanden)
- Setzt sinnvolle Defaults, falls Datei fehlt oder PyYAML nicht installiert ist
- Liefert eine PDFDocConfig-Instanz mit allen wichtigen Feldern

Verwendung in anderen Skripten:
    from scripts.config_loader import get_config
    CONFIG = get_config()
    print(CONFIG.input_pdf_dir)
    print(CONFIG.tesseract_cmd)
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parents[1]   # ...\kran-tools
CONFIG_DIR = BASE_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class PDFDocConfig:
    # Pfade (relativ zu BASE_DIR, außer es ist ein absoluter Pfad)
    input_pdf_dir: str = "input/pdf"
    models_dir: str = "output/models"
    reports_dir: str = "output/reports"

    # OCR / Tesseract
    tesseract_cmd: Optional[str] = None
    ocr_enabled: bool = True
    ocr_lang: str = "deu+eng"

    # Text-Proben (Wissensmodul)
    max_sample_pages: int = 3
    max_sample_chars: int = 1000


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    """
    Versucht, eine YAML-Datei zu laden.
    Wenn PyYAML nicht installiert ist oder ein Fehler passiert,
    wird ein leeres Dict zurückgegeben.
    """
    if not path.exists():
        return {}

    try:
        import yaml  # type: ignore
    except ImportError:
        print("Hinweis: PyYAML ist nicht installiert. "
              "Konfiguration wird mit Defaults geladen.")
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                print("Hinweis: config.yaml hat kein Dict-Format. "
                      "Verwende Default-Konfiguration.")
                return {}
            return data
    except Exception as e:
        print(f"Hinweis: Fehler beim Lesen von {path}: {e}")
        return {}


_CONFIG_CACHE: Optional[PDFDocConfig] = None


def get_config() -> PDFDocConfig:
    """
    Liefert die globale PDFDocConfig-Instanz.
    Nutzt einen einfachen Cache, damit die Datei nur einmal gelesen wird.
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    base_config = PDFDocConfig()
    raw = _load_yaml_file(CONFIG_PATH)

    if raw:
        # Alle bekannten Felder ggf. überschreiben
        for f in fields(PDFDocConfig):
            if f.name in raw:
                value = raw[f.name]
                setattr(base_config, f.name, value)

    # leere Strings bei tesseract_cmd als "nicht gesetzt" behandeln
    if base_config.tesseract_cmd == "":
        base_config.tesseract_cmd = None

    _CONFIG_CACHE = base_config
    return base_config
