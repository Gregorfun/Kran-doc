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
import argparse
from typing import Dict, Any, List, Optional, Tuple

from pypdf import PdfReader  # pip install pypdf
import pypdfium2 as pdfium   # pip install pypdfium2
from PIL import Image, ImageOps, ImageFilter        # pip install pillow
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

models_root = Path(CONFIG.models_root)
if not models_root.is_absolute():
    MODELS_ROOT = BASE_DIR / models_root
else:
    MODELS_ROOT = models_root

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
WIRE_PATTERN = re.compile(r"\bW\d{1,5}\b")
TERMINAL_PATTERN = re.compile(r"\bX\d{1,4}(?:[.:/]\d{1,3})\b")
CONTACT_PATTERN = re.compile(r"\b([A-Z]{1,3}\d{1,4})[/:](\d{1,3})-(\d{1,3})\b")
XREF_PATTERN = re.compile(r"\b(?:Blatt|Seite)\s+\d{1,3}\b", re.IGNORECASE)

# Blatt-/Koordinaten-Referenzen: X2/40.E3, 173/38.D6, PWM/46.C2, X2/40 E3
SHEET_REF_PATTERN = re.compile(
    r"\b([A-Z0-9\+\-]+)\/(\d{1,3})\s*\.?\s*([A-Z]\d)\b"
)
SHEET_REF_SHORT_PATTERN = re.compile(r"\b(?:Blatt|Seite|S\.|Bl\.|Sheet)\s*(\d{1,3})\b", re.IGNORECASE)

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

    alnum = sum(1 for ch in sample if ch.isalnum())
    alnum_ratio = alnum / total
    if total >= 50 and alnum_ratio < 0.15:
        return True

    control = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
    control_ratio = control / total
    if total >= 50 and control_ratio > 0.02:
        return True

    tokens = [t for t in sample.split() if t]
    if tokens:
        non_alnum_tokens = sum(1 for t in tokens if not any(ch.isalnum() for ch in t))
        if total >= 50 and (non_alnum_tokens / len(tokens)) > 0.8:
            return True

    # Heuristik:
    # - normale PDFs haben ratio typischerweise > 0.7
    # - „kaputte“ SPLs liegen oft bei < 0.3
    return ratio < 0.4


def ocr_pdf_page(pdf_path: Path, page_index: int) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Rendert eine Seite des PDFs als Bild und führt Tesseract-OCR aus.
    page_index ist 0-basiert.
    """
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf.get_page(page_index)

    # mit Scale ~200 DPI rendern
    bitmap = page.render(scale=200 / 72)
    pil_image: Image.Image = bitmap.to_pil()

    # leichte OCR-Vorverarbeitung fuer stabilere Ergebnisse
    pil_image = ImageOps.grayscale(pil_image)
    pil_image = ImageOps.autocontrast(pil_image)
    pil_image = pil_image.filter(ImageFilter.MedianFilter(size=3))

    # Ressourcen sauber schließen
    page.close()
    pdf.close()

    # OCR (Deutsch + Englisch)
    text = pytesseract.image_to_string(pil_image, lang="deu+eng")
    data = pytesseract.image_to_data(
        pil_image,
        lang="deu+eng",
        output_type=pytesseract.Output.DICT,
    )

    tokens: List[Dict[str, Any]] = []
    n = len(data.get("text", []))
    for i in range(n):
        t = data["text"][i].strip()
        if not t:
            continue
        conf = data.get("conf", ["-1"])[i]
        try:
            conf_val = float(conf)
        except (TypeError, ValueError):
            conf_val = -1.0
        tokens.append(
            {
                "text": t,
                "x": int(data.get("left", [0])[i]),
                "y": int(data.get("top", [0])[i]),
                "w": int(data.get("width", [0])[i]),
                "h": int(data.get("height", [0])[i]),
                "conf": conf_val,
            }
        )

    return text, tokens


# ---------------------------------------------------------
# Parsing
# ---------------------------------------------------------
def extract_pages_text(
    pdf_path: Path,
    page_start: int = 0,
    page_end: Optional[int] = None,
    ocr_only_if_gibberish: bool = True,
    max_ocr_pages: int = 0,
    auto_ocr_sample_pages: int = 0,
    auto_ocr_threshold: float = 0.0,
    ocr_pages: Optional[set[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Lies alle Seiten des SPL-PDFs ein.
    Wenn der Text nach Gibberish aussieht, wird OCR verwendet.
    """
    reader = PdfReader(str(pdf_path))
    pages: List[Dict[str, Any]] = []

    start = max(0, page_start)
    end = len(reader.pages) if page_end is None or page_end <= 0 else min(len(reader.pages), page_end)
    force_ocr_all = False
    if ocr_only_if_gibberish and auto_ocr_sample_pages > 0 and auto_ocr_threshold > 0:
        sample_end = min(len(reader.pages), auto_ocr_sample_pages)
        gib = 0
        for idx in range(sample_end):
            sample_text = reader.pages[idx].extract_text() or ""
            if is_gibberish(sample_text):
                gib += 1
        if sample_end > 0 and (gib / sample_end) >= auto_ocr_threshold:
            force_ocr_all = True
            print(f"  -> Auto-OCR aktiviert: {gib}/{sample_end} Seiten Gibberish")
    ocr_used = 0

    for page_index, page in enumerate(reader.pages):
        if page_index < start or page_index >= end:
            continue
        raw = page.extract_text() or ""
        source = "pdf"
        ocr_tokens: List[Dict[str, Any]] = []

        needs_ocr = is_gibberish(raw)
        effective_only_if_gibberish = ocr_only_if_gibberish and not force_ocr_all

        # Gezielt OCR für bestimmte Seiten erzwingen
        force_this_page = bool(ocr_pages) and (page_index in (ocr_pages or set()))

        if force_this_page or (not effective_only_if_gibberish) or needs_ocr:
            if max_ocr_pages and ocr_used >= max_ocr_pages:
                pages.append(
                    {
                        "page": page_index,
                        "text": raw,
                        "source": source,
                        "ocr_tokens": ocr_tokens,
                    }
                )
                continue
            if force_this_page:
                print(f"  -> Seite {page_index+1}: OCR fuer Seite erzwungen (ocr_pages)")
            elif needs_ocr:
                print(f"  -> Seite {page_index+1}: Gibberish erkannt, OCR-Fallback")
            else:
                print(f"  -> Seite {page_index+1}: OCR erzwungen")
            raw, ocr_tokens = ocr_pdf_page(pdf_path, page_index)
            source = "ocr"
            ocr_used += 1

        pages.append(
            {
                "page": page_index,
                "text": raw,
                "source": source,
                "ocr_tokens": ocr_tokens,
            }
        )

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
    bmk_tokens_norm: set[str] = set()
    sheet_refs: List[Dict[str, Any]] = []
    spl_pages: List[Dict[str, Any]] = []
    global_line_no = 0
    toc_index = extract_toc_index(pages)
    toc_by_page = {entry["page_hint"]: entry["title"] for entry in toc_index}

    def normalize_bmk_token(token: str) -> str:
        return token.strip().upper().replace(" ", "")

    def guess_page_title(lines: List[str]) -> str:
        for line in lines:
            candidate = line.strip()
            if len(candidate) < 3 or len(candidate) > 60:
                continue
            letters = sum(1 for ch in candidate if ch.isalpha())
            digits = sum(1 for ch in candidate if ch.isdigit())
            if letters >= 6 and letters > digits:
                return candidate
        return ""

    for page in pages:
        page_text = page.get("text", "")
        lines = page_text.splitlines()
        tokens: set[str] = set()
        tokens_norm: set[str] = set()
        page_sheet_refs: List[Dict[str, Any]] = []
        page_wire_refs: List[Dict[str, Any]] = []
        page_terminal_refs: List[Dict[str, Any]] = []
        page_contact_refs: List[Dict[str, Any]] = []
        page_xref_refs: List[Dict[str, Any]] = []
        cleaned_lines: List[str] = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if is_page_footer(line_stripped):
                continue

            global_line_no += 1
            cleaned_lines.append(line_stripped)
            line_tokens: List[str] = []
            line_tokens_norm: List[str] = []

            # BMK-Referenzen
            for m in BMK_PATTERN.finditer(line_stripped):
                token = m.group(1)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in BMK_SIMPLE_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in X_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in F_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in S_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in A_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in LSB_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in CAN_PATTERN.finditer(line_stripped):
                token = m.group(0)
                tokens.add(token)
                bmk_tokens.add(token)
                norm = normalize_bmk_token(token)
                tokens_norm.add(norm)
                bmk_tokens_norm.add(norm)
                line_tokens.append(token)
                line_tokens_norm.append(norm)

            for m in WIRE_PATTERN.finditer(line_stripped):
                ref = {
                    "wire": m.group(0),
                    "line": global_line_no,
                    "context": line_stripped,
                }
                page_wire_refs.append(ref)

            for m in TERMINAL_PATTERN.finditer(line_stripped):
                ref = {
                    "terminal": m.group(0),
                    "line": global_line_no,
                    "context": line_stripped,
                }
                page_terminal_refs.append(ref)

            for m in CONTACT_PATTERN.finditer(line_stripped):
                ref = {
                    "contact_raw": m.group(0),
                    "device": m.group(1),
                    "from": m.group(2),
                    "to": m.group(3),
                    "line": global_line_no,
                    "context": line_stripped,
                }
                page_contact_refs.append(ref)

            for m in XREF_PATTERN.finditer(line_stripped):
                ref = {
                    "xref": m.group(0),
                    "line": global_line_no,
                    "context": line_stripped,
                }
                page_xref_refs.append(ref)

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
                if line_tokens:
                    ref["bmk_tokens"] = sorted(set(line_tokens))
                if line_tokens_norm:
                    ref["bmk_tokens_norm"] = sorted(set(line_tokens_norm))
                page_sheet_refs.append(ref)
                sheet_refs.append(ref)

            for m in SHEET_REF_SHORT_PATTERN.finditer(line_stripped):
                ref = {
                    "sheet_raw": m.group(0),
                    "ref": None,
                    "sheet": m.group(1),
                    "coord": None,
                    "line": global_line_no,
                    "context": line_stripped,
                }
                if line_tokens:
                    ref["bmk_tokens"] = sorted(set(line_tokens))
                if line_tokens_norm:
                    ref["bmk_tokens_norm"] = sorted(set(line_tokens_norm))
                page_sheet_refs.append(ref)
                sheet_refs.append(ref)

        cleaned_text = "\n".join(cleaned_lines)
        title = ""
        if len(cleaned_text) < 40:
            title = toc_by_page.get(page.get("page", 0) + 1, "")
        if not title:
            title = guess_page_title(cleaned_lines)

        spl_pages.append(
            {
                "page": page.get("page"),
                "text": cleaned_text,
                "tokens": sorted(tokens),
                "tokens_norm": sorted(tokens_norm),
                "sheet_refs": page_sheet_refs,
                "wire_refs": page_wire_refs,
                "terminal_refs": page_terminal_refs,
                "contact_refs": page_contact_refs,
                "xref_refs": page_xref_refs,
                "title": title,
                "source": page.get("source"),
                "ocr_tokens": page.get("ocr_tokens", []),
            }
        )

    return {
        "bmk_refs": sorted(bmk_tokens),
        "bmk_refs_norm": sorted(bmk_tokens_norm),
        "sheet_refs": sheet_refs,
        "wire_refs": [r for p in spl_pages for r in p.get("wire_refs", [])],
        "terminal_refs": [r for p in spl_pages for r in p.get("terminal_refs", [])],
        "contact_refs": [r for p in spl_pages for r in p.get("contact_refs", [])],
        "xref_refs": [r for p in spl_pages for r in p.get("xref_refs", [])],
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


def process_spl_pdf(
    pdf_path: Path,
    model_hint: Optional[str] = None,
    page_start: int = 0,
    page_end: Optional[int] = None,
    ocr_only_if_gibberish: bool = True,
    max_ocr_pages: int = 0,
    auto_ocr_sample_pages: int = 0,
    auto_ocr_threshold: float = 0.0,
    ocr_pages: Optional[set[int]] = None,
) -> None:
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

    pages = extract_pages_text(
        pdf_path,
        page_start=page_start,
        page_end=page_end,
        ocr_only_if_gibberish=ocr_only_if_gibberish,
        max_ocr_pages=max_ocr_pages,
        auto_ocr_sample_pages=auto_ocr_sample_pages,
        auto_ocr_threshold=auto_ocr_threshold,
        ocr_pages=ocr_pages,
    )
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
    1b) Hersteller-Struktur:
       input/Liebherr/models/<MODEL>/spl/*.pdf -> (MODEL, pdf_path)
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

    # 1b) Hersteller-Struktur
    if MODELS_ROOT.exists():
        for model_dir in sorted(MODELS_ROOT.iterdir()):
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


def process_all_spl_pdfs(
    page_start: int = 0,
    page_end: Optional[int] = None,
    ocr_only_if_gibberish: bool = True,
    max_ocr_pages: int = 0,
    auto_ocr_sample_pages: int = 0,
    auto_ocr_threshold: float = 0.0,
    ocr_pages: Optional[set[int]] = None,
) -> None:
    if not INPUT_ROOT.exists():
        print(f"Eingabeverzeichnis existiert nicht: {INPUT_ROOT}")
        return

    pairs = discover_spl_pdfs()
    if not pairs:
        print(f"Keine SPL-PDFs unter {INPUT_ROOT} gefunden.")
        return

    for model_hint, pdf_path in pairs:
        process_spl_pdf(
            pdf_path,
            model_hint,
            page_start=page_start,
            page_end=page_end,
            ocr_only_if_gibberish=ocr_only_if_gibberish,
            max_ocr_pages=max_ocr_pages,
            auto_ocr_sample_pages=auto_ocr_sample_pages,
            auto_ocr_threshold=auto_ocr_threshold,
            ocr_pages=ocr_pages,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SPL-Parser mit OCR-Fallback.")
    parser.add_argument("--page-start", type=int, default=CONFIG.spl_page_start, help="Startseite (0-basiert)")
    parser.add_argument("--page-end", type=int, default=CONFIG.spl_page_end, help="Ende (exklusiv, 0-basiert)")
    parser.add_argument("--max-ocr-pages", type=int, default=CONFIG.spl_ocr_max_pages, help="Max. OCR-Seiten (0=unbegrenzt)")
    parser.add_argument("--auto-ocr-sample-pages", type=int, default=CONFIG.spl_auto_ocr_sample_pages, help="OCR auto-aktivieren: Sample-Seiten")
    parser.add_argument("--auto-ocr-threshold", type=float, default=CONFIG.spl_auto_ocr_threshold, help="OCR auto-aktivieren: Gibberish-Quote")
    parser.add_argument(
        "--ocr-only-if-gibberish",
        action="store_true",
        default=CONFIG.spl_ocr_only_if_gibberish,
        help="OCR nur bei Gibberish",
    )
    parser.add_argument(
        "--ocr-always",
        action="store_true",
        help="OCR fuer alle Seiten erzwingen",
    )
    parser.add_argument(
        "--ocr-pages",
        type=str,
        default="",
        help="Gezielt OCR fuer Seiten (0-basiert), z.B. '6,8,9,11'",
    )
    args = parser.parse_args()

    page_end = args.page_end if args.page_end > 0 else None
    ocr_only_if_gibberish = args.ocr_only_if_gibberish and not args.ocr_always

    ocr_pages: Optional[set[int]] = None
    if args.ocr_pages:
        parsed_pages: set[int] = set()
        for part in str(args.ocr_pages).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                parsed_pages.add(int(part))
            except Exception:
                continue
        if parsed_pages:
            ocr_pages = parsed_pages

    process_all_spl_pdfs(
        page_start=args.page_start,
        page_end=page_end,
        ocr_only_if_gibberish=ocr_only_if_gibberish,
        max_ocr_pages=args.max_ocr_pages,
        auto_ocr_sample_pages=args.auto_ocr_sample_pages,
        auto_ocr_threshold=args.auto_ocr_threshold,
        ocr_pages=ocr_pages,
    )
