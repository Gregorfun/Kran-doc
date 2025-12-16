# Datei: scripts/model_detection.py
"""
Hilfsfunktionen zur Modellerkennung aus PDF-Inhalt + Dateiname.

Strategie:
1) Versuche, das Kranmodell aus dem PDF-Text zu erkennen
   (z.B. "LTM 1110-5.1", "LTM1090-4.2").
2) Wenn das nicht klappt, Fallback auf Dateinamen-Muster.

Ergebnis-Format der Modellkennung:
    "LTM1110-5.1"
    "LTM1090-4.2"
    etc.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pypdf import PdfReader


# Regex für Modell im Text, z.B.:
#   "LTM 1110-5.1"
#   "LTM1110-5.1"
#   "LTM 1090-4.2"
MODEL_IN_TEXT_RE = re.compile(
    r"\b"
    r"(LTM|LTC|LTF)"          # Modellprefix
    r"\s*"
    r"([0-9]{3,4})"           # Zahl, z.B. 1110
    r"[-_ ]?"
    r"([0-9])"
    r"[-\.]"
    r"([0-9])"
    r"\b"
)


# Fallback-Regex für Dateinamen im Stil:
#   "LTM1110-5.1lec_043563.pdf"
#   "LTM1110-5.1 spl_043563.pdf"
MODEL_IN_FILENAME_RE = re.compile(
    r"(LTM|LTC|LTF)\s*([0-9]{3,4})[-_ ]?([0-9])\.([0-9])",
    re.IGNORECASE,
)


def detect_model_from_pdf_text(pdf_path: Path, max_pages: int = 3) -> Optional[str]:
    """
    Versucht, das Modell aus dem Text der ersten max_pages Seiten
    zu erkennen. Gibt z.B. "LTM1110-5.1" zurück oder None.
    """
    reader = PdfReader(str(pdf_path))
    text_chunks = []

    for page in reader.pages[:max_pages]:
        t = page.extract_text() or ""
        text_chunks.append(t)

    full_sample = "\n".join(text_chunks)
    if not full_sample.strip():
        return None

    m = MODEL_IN_TEXT_RE.search(full_sample)
    if not m:
        return None

    prefix, num, a, b = m.groups()
    return f"{prefix.upper()}{num}-{a}.{b}"


def detect_model_from_filename(filename: str) -> Optional[str]:
    """
    Versucht, das Modell aus dem Dateinamen zu erkennen.
    """
    m = MODEL_IN_FILENAME_RE.search(filename)
    if not m:
        return None
    prefix, num, a, b = m.groups()
    return f"{prefix.upper()}{num}-{a}.{b}"


def detect_model(pdf_path: Path) -> Optional[str]:
    """
    Kombiniert beide Methoden:
      1) PDF-Text durchsuchen
      2) Fallback Dateiname
    """
    # 1) Inhalt
    model = detect_model_from_pdf_text(pdf_path)
    if model:
        return model

    # 2) Dateiname
    return detect_model_from_filename(pdf_path.name)
