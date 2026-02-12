"""Pytest-Konfiguration und Fixtures für Kran-Tools Tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Projekt-Root zum Path hinzufügen
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


@pytest.fixture
def base_dir():
    """Liefert das Projekt-Root-Verzeichnis."""
    return BASE_DIR


@pytest.fixture
def test_data_dir():
    """Liefert das Test-Daten-Verzeichnis."""
    data_dir = BASE_DIR / "tests" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def temp_output_dir(tmp_path):
    """Liefert ein temporäres Output-Verzeichnis für Tests."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def sample_config():
    """Liefert eine Test-Konfiguration."""
    return {
        "input_pdf_dir": "input",
        "models_dir": "output/models",
        "reports_dir": "output/reports",
        "embeddings_dir": "output/embeddings",
        "tesseract_cmd": None,
        "ocr_enabled": False,
        "ocr_lang": "deu+eng",
    }
