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

# einfache BMK-Codes wie A81, S304, A104, X221, F12, K15, M3
BMK_SIMPLE_PATTERN = re.compile(r"\b(?:[A-Z]{1,3}\d{1,4})(?:\*)?\b")

X_PATTERN = re.compile(r"\bX\d{1,4}\b")
F_PATTERN = re.compile(r"\bF\d{1,3}\b")
S_PATTERN = re.compile(r"\bS\d{1,4}\b")
A_PATTERN = re.compile(r"\bA\d{1,4}\b")
LSB_PATTERN = re.compile(r"\bLSB\d{1,2}\b")
CAN_PATTERN = re.compile(r"\bCAN(?:-H|-L)?\b")

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
def extract_pages_text(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Lies alle Seiten des SPL-PDFs ein.
    Wenn der Text nach Gibberish aussieht, wird OCR verwendet.
    """
    reader = PdfReader(str(pdf_path))
    pages: List[Dict[str, Any]] = []

    for page_index, page in enumerate(reader.pages):
        raw = page.extract_text() or ""

        if is_gibberish(raw):
            print(f"  -> Seite {page_index+1}: Gibberish erkannt, OCR-Fallback")
            raw = ocr_pdf_page(pdf_path, page_index)

        pages.append({"page": page_index, "text": raw})

    return pages


def extract_toc_index(pages_text: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    toc_index: List[Dict[str, Any]] = []
    toc_pattern = re.compile(r"^(?P<title>.+?)\s*/\s*(?P<ref>\d{1,4})\s*$")

    for page in pages_text[:5]:
        for line in page.get("text", "").splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue
            match = toc_pattern.match(line_stripped)
            if not match:
                continue
            title = match.group("title").strip()
            ref = match.group("ref").strip()
            if not title:
                continue
            toc_index.append({"title": title, "ref": ref, "page_hint": int(ref)})

    return toc_index


def parse_spl_text(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extrahiert BMK-Referenzen und Blatt-Referenzen aus dem SPL-Text.
    Ergebnis:
        {
          "bmk_refs": [...],
          "sheet_refs": [...],
          "spl_pages": [...]
        }
    """
    bmk_tokens: set[str] = set()
    sheet_refs: List[Dict[str, Any]] = []
    spl_pages: List[Dict[str, Any]] = []
    global_line_no = 0
    toc_index = extract_toc_index(pages)
    toc_by_page = {entry["page_hint"]: entry["title"] for entry in toc_index}

    for page in pages:
        page_text = page.get("text", "")
        lines = page_text.splitlines()
        tokens: set[str] = set()
        page_sheet_refs: List[Dict[str, Any]] = []
        cleaned_lines: List[str] = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if is_page_footer(line_stripped):
                continue

            global_line_no += 1
            cleaned_lines.append(line_stripped)

            # BMK-Referenzen
            for m in BMK_PATTERN.finditer(line_stripped):
                token = m.group(1)
                tokens.add(token)
                bmk_tokens.add(token)

            for m in BMK_SIMPLE_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)

            for m in X_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)

            for m in F_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)

            for m in S_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)

            for m in A_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)

            for m in LSB_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)

            for m in CAN_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)

            # Blatt/Koordinate
            for m in SHEET_REF_PATTERN.finditer(line_stripped):
                ref = {
                    "sheet_raw": m.group(0),
                    "ref": m.group(1),
                    "sheet": m.group(2),
                    "coord": m.group(3),
                    "line": global_line_no,
                    "context": line_stripped,
                }
                page_sheet_refs.append(ref)
                sheet_refs.append(ref)

        cleaned_text = "\n".join(cleaned_lines)
        title = ""
        if len(cleaned_text) < 40:
            title = toc_by_page.get(page.get("page", 0) + 1, "")

        spl_pages.append(
            {
                "page": page.get("page"),
                "text": cleaned_text,
                "tokens": sorted(tokens),
                "sheet_refs": page_sheet_refs,
                "title": title,
            }
        )

    return {
        "bmk_refs": sorted(bmk_tokens),
        "sheet_refs": sheet_refs,
        "spl_pages": spl_pages,
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

    pages = extract_pages_text(pdf_path)
    full_text = "\n".join(page["text"] for page in pages)

    if not full_text.strip():
        print("  -> WARNUNG: Kein Text erkannt, breche für diese Datei ab.")
        return

    parsed = parse_spl_text(pages)
    bmk_refs = parsed["bmk_refs"]
    sheet_refs = parsed["sheet_refs"]
    spl_pages = parsed["spl_pages"]

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
        "spl_pages": spl_pages,
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
