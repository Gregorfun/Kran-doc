# Datei: scripts/spl_parser.py
"""
SPL-Parser mit OCR-Fallback für Schaltpläne.

Neue Input-Struktur:
    input/<MODEL>/spl/*.pdf

- Normale SPL-PDFs: Text wird über pypdf gelesen.
- SPL-PDFs mit sonderkodierter Schrift:
    -> Text von pypdf ist Kauderwelsch
    -> Erkennung als „Gibberish“
    -> Seite wird als Bild gerendert (pypdfium2)
    -> OCR mit Tesseract (deu+eng)
    -> auf dem erkannten Text laufen die BMK-Pattern.

Modell-Erkennung:
- Primär über den Ordnernamen (LTM1110-5.1, LTC1050-3.1, ...)
- Fallback über PDF-Inhalt / Dateinamen (Alt-Layout)
"""

from __future__ import annotations

import json
import re
import string
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from pypdf import PdfReader  # pip install pypdf
import pypdfium2 as pdfium   # pip install pypdfium2
from PIL import Image        # pip install pillow
import pytesseract           # pip install pytesseract
from scripts.config_loader import get_config
from scripts.model_detection import detect_model as detect_model_generic

BASE_DIR = Path(__file__).resolve().parents[1]

# Konfiguration laden
CONFIG = get_config()

# Eingabe-/Ausgabe-Verzeichnisse ggf. relativ zu BASE_DIR auflösen
input_dir = Path(CONFIG.input_pdf_dir)
if not input_dir.is_absolute():
    INPUT_ROOT = BASE_DIR / input_dir
else:
    INPUT_ROOT = input_dir

# INPUT_ROOT ist jetzt z.B. .../input
INPUT_ROOT.mkdir(parents=True, exist_ok=True)

models_dir = Path(CONFIG.models_dir)
if not models_dir.is_absolute():
    MODELS_DIR = BASE_DIR / models_dir
else:
    MODELS_DIR = models_dir

MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Tesseract-Pfad aus Konfiguration übernehmen (falls gesetzt)
TESSERACT_CMD: Optional[str] = CONFIG.tesseract_cmd
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


# ---------------------------------------------------------
# Patterns für BMK- und Blatt-Referenzen
# ---------------------------------------------------------

# BMK/Stecker usw.
BMK_PATTERN = re.compile(
    r"\b("
    r"[A-Z][A-Z0-9]{0,3}\d{0,3}"     # z.B. A330, XM400, W300, A21
    r"\."                            # Punkt
    r"[A-Z0-9]*[A-Z][A-Z0-9]*"       # z.B. KL30, X4, WL007, GND
    r"(?:\:\d+)?"                    # optional :9
    r")\b"
)

# Blatt-/Koordinaten-Referenzen: X2/40.E3, 173/38.D6, PWM/46.C2
SHEET_REF_PATTERN = re.compile(
    r"\b([A-Z0-9\+\-]+)\/(\d{1,3})\.([A-Z]\d)\b"
)

# erlaubte Zeichen zur „Gibberish“-Erkennung
PRINTABLE_CHARS = set(
    string.ascii_letters
    + string.digits
    + " .,:;+-_()/\\[]{}<>!?%&=#'\""
    + "äöüÄÖÜß"
)


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------
def is_page_footer(line: str) -> bool:
    """Erkennt Seitennummern-Fußzeilen wie 'Seite 3 von 418'."""
    return "Seite" in line and "von" in line


def is_gibberish(text: str) -> bool:
    """
    Prüft, ob der Text überwiegend aus „komischen“ Zeichen besteht.
    Bei den Problem-SPLs kommen z.B. fast nur Steuer-/Sonderzeichen.
    """
    if not text:
        return True

    sample = text.strip()
    if not sample:
        return True

    total = len(sample)
    if total < 50:
        # kurzer Text ist ok, auch wenn der Anteil klein ist
        return False

    printable = sum(1 for ch in sample if ch in PRINTABLE_CHARS)
    ratio = printable / total

    # Heuristik:
    # - normale PDFs haben ratio typischerweise > 0.7
    # - „kaputte“ SPLs liegen oft bei < 0.3
    return ratio < 0.4


def ocr_pdf_page(pdf_path: Path, page_index: int) -> str:
    """
    Rendert eine Seite des PDFs als Bild und führt Tesseract-OCR aus.
    page_index ist 0-basiert.
    """
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf.get_page(page_index)

    # mit Scale ~200 DPI rendern
    bitmap = page.render(scale=200 / 72)
    pil_image: Image.Image = bitmap.to_pil()

    # Ressourcen sauber schließen
    page.close()
    pdf.close()

    # OCR (Deutsch + Englisch)
    text = pytesseract.image_to_string(pil_image, lang="deu+eng")
    return text


# ---------------------------------------------------------
# Parsing
# ---------------------------------------------------------
def extract_text_safely(pdf_path: Path) -> str:
    """
    Lies alle Seiten des SPL-PDFs ein.
    Wenn der Text nach Gibberish aussieht, wird OCR verwendet.
    """
    reader = PdfReader(str(pdf_path))
    texts: List[str] = []

    for page_index, page in enumerate(reader.pages):
        raw = page.extract_text() or ""

        if is_gibberish(raw):
            print(f"  -> Seite {page_index+1}: Gibberish erkannt, OCR-Fallback")
            ocr_text = ocr_pdf_page(pdf_path, page_index)
            texts.append(ocr_text)
        else:
            texts.append(raw)

    return "\n".join(texts)


def parse_spl_text(full_text: str) -> Dict[str, Any]:
    """
    Extrahiert BMK-Referenzen und Blatt-Referenzen aus dem SPL-Text.
    Ergebnis:
        {
          "bmk_refs": [...],
          "sheet_refs": [...]
        }
    """
    lines = full_text.splitlines()
    bmk_refs: List[Dict[str, Any]] = []
    sheet_refs: List[Dict[str, Any]] = []

    for line_no, line in enumerate(lines, start=1):
        line_stripped = line.strip()
        if not line_stripped:
            continue

        if is_page_footer(line_stripped):
            continue

        # BMK-Referenzen
        for m in BMK_PATTERN.finditer(line_stripped):
            bmk_refs.append(
                {
                    "bmk": m.group(1),
                    "line": line_no,
                    "context": line_stripped,
                }
            )

        # Blatt/Koordinate
        for m in SHEET_REF_PATTERN.finditer(line_stripped):
            sheet_refs.append(
                {
                    "sheet_raw": m.group(0),
                    "ref": m.group(1),
                    "sheet": m.group(2),
                    "coord": m.group(3),
                    "line": line_no,
                    "context": line_stripped,
                }
            )

    return {
        "bmk_refs": bmk_refs,
        "sheet_refs": sheet_refs,
    }


def fallback_model_from_filename(filename: str) -> str:
    """
    Fallback für die Modellerkennung über den Dateinamen.
    Beispiel:
      'spl_089010.pdf' -> 'spl_089010'
    """
    name = Path(filename).name
    lower = name.lower()

    if "spl_" in lower:
        # Bei SPL-Nummern ist der Dateiname oft selbst das "Modell"
        return name.split(".")[0]

    return name.rsplit(".", 1)[0]


def process_spl_pdf(pdf_path: Path, model_hint: Optional[str] = None) -> None:
    print(f"Verarbeite SPL-PDF: {pdf_path.name}")

    if model_hint:
        model = model_hint.strip()
        detected = detect_model_generic(pdf_path)
        if detected and detected.strip() != model:
            print(
                f"  -> Hinweis: detect_model_generic() meldet '{detected}', "
                f"Ordnername ist aber '{model}'. Ordnername wird verwendet."
            )
    else:
        # Alt-Layout: Modell aus PDF-Inhalt/Dateiname bestimmen
        detected = detect_model_generic(pdf_path)
        if detected:
            model = detected.strip()
        else:
            model = fallback_model_from_filename(pdf_path.name)
        print(f"  -> Modell (Alt-Layout): {model}")

    print(f"  -> Modell: {model}")

    full_text = extract_text_safely(pdf_path)

    if not full_text.strip():
        print("  -> WARNUNG: Kein Text erkannt, breche für diese Datei ab.")
        return

    parsed = parse_spl_text(full_text)
    bmk_refs = parsed["bmk_refs"]
    sheet_refs = parsed["sheet_refs"]

    print(f"  -> BMK-Referenzen:   {len(bmk_refs)}")
    print(f"  -> Blatt-Referenzen: {len(sheet_refs)}")

    model_dir = MODELS_DIR / model
    model_dir.mkdir(parents=True, exist_ok=True)

    output_file = model_dir / f"{model}_SPL_REFERENCES.json"

    output_dict = {
        "type": "SPL_REFERENCES",
        "model": model,
        "source_file": pdf_path.name,
        "bmk_ref_count": len(bmk_refs),
        "sheet_ref_count": len(sheet_refs),
        "bmk_refs": bmk_refs,
        "sheet_refs": sheet_refs,
    }

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(output_dict, f, ensure_ascii=False, indent=2)

    print(f"  -> JSON gespeichert: {output_file}")


# ---------------------------------------------------------
# Input-Discovery: neue Struktur input/<MODEL>/spl/*.pdf
# ---------------------------------------------------------
def discover_spl_pdfs() -> List[Tuple[Optional[str], Path]]:
    """
    Sucht SPL-PDFs.

    1) Neue Struktur:
       input/<MODEL>/spl/*.pdf -> (MODEL, pdf_path)
    2) Fallback Alt-Layout:
       PDFs direkt unter INPUT_ROOT: *spl*.pdf -> (None, pdf_path)
    """
    pairs: List[Tuple[Optional[str], Path]] = []

    # 1) Neue Struktur
    for model_dir in sorted(INPUT_ROOT.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        spl_dir = model_dir / "spl"
        if not spl_dir.exists():
            continue
        for pdf in sorted(spl_dir.glob("*.pdf")):
            pairs.append((model_name, pdf))

    # 2) Fallback Alt-Layout
    legacy_candidates = sorted(list(INPUT_ROOT.glob("*spl*.pdf")))
    for pdf in legacy_candidates:
        pairs.append((None, pdf))

    return pairs


def process_all_spl_pdfs() -> None:
    if not INPUT_ROOT.exists():
        print(f"Eingabeverzeichnis existiert nicht: {INPUT_ROOT}")
        return

    pairs = discover_spl_pdfs()
    if not pairs:
        print(f"Keine SPL-PDFs unter {INPUT_ROOT} gefunden.")
        return

    for model_hint, pdf_path in pairs:
        process_spl_pdf(pdf_path, model_hint)


if __name__ == "__main__":
    process_all_spl_pdfs()
