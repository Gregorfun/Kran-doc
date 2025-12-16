# Datei: scripts/bmk_parser.py
"""
BMK-Parser für LTM-/LTC-/LTF-Schaltgerätebeschreibungen (shb_..._uw/ow_...pdf)
mit Modellerkennung, zentraler Konfiguration und optionalem OCR-Fallback.

Neue Input-Struktur:
    input/<MODEL>/bmk/*.pdf

Ziel:
- BMK-Listen für Unterwagen / Oberwagen einlesen
- strukturierte Komponentenlisten erzeugen
- pro Datei ein JSON im Modell-Ordner schreiben:

  <models_dir>/<Modell>/<Modell>_BMK_UW.json
  <models_dir>/<Modell>/<Modell>_BMK_OW.json

Die Struktur passt auf die aktuelle export_for_embeddings.py-Logik:
  bmk_lists[wagen]["components"] -> bmk_component-Chunks
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from pypdf import PdfReader  # pip install pypdf

# OCR-Fallback (optional, abhängig von config.yaml)
import pypdfium2 as pdfium   # pip install pypdfium2
from PIL import Image        # pip install pillow
import pytesseract           # pip install pytesseract

from scripts.model_detection import detect_model as detect_model_generic
from scripts.config_loader import get_config

# --------------------------------------------------------------------
# Basis-Pfade & Konfiguration
# --------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = get_config()

_input_dir = Path(CONFIG.input_pdf_dir)
if not _input_dir.is_absolute():
    INPUT_ROOT = BASE_DIR / _input_dir
else:
    INPUT_ROOT = _input_dir

# INPUT_ROOT ist jetzt z.B. .../input
INPUT_ROOT.mkdir(parents=True, exist_ok=True)

_models_dir = Path(CONFIG.models_dir)
if not _models_dir.is_absolute():
    OUTPUT_MODELS_DIR = BASE_DIR / _models_dir
else:
    OUTPUT_MODELS_DIR = _models_dir

OUTPUT_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Tesseract-Pfad + OCR-Einstellungen aus config.yaml
TESSERACT_CMD: Optional[str] = getattr(CONFIG, "tesseract_cmd", None)
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

OCR_ENABLED: bool = bool(getattr(CONFIG, "ocr_enabled", False))
OCR_LANG: str = getattr(CONFIG, "ocr_lang", "deu+eng")

# --------------------------------------------------------------------
# BMK-Erkennung
# --------------------------------------------------------------------
# BMK-Codes in den BMK-Listen haben viele Formen, z.B.:
#   S302, A371, B305, B307*, WVM1, Y520_DBD1, A659.B549, ZDU659XL, A700.X1, Y9.Xa, ...
# Heuristik:
#   - beginnt mit Buchstabe
#   - enthält mindestens eine Ziffer
#   - besteht nur aus Buchstaben/Ziffern/Unterstrich
#   - optional: Punkt + weiterer Token
#   - optional: Sternchen am Ende
BMK_CODE_RE = re.compile(
    r"^(?=.*\d)[A-Za-z][A-Za-z0-9_]{0,10}(?:\.[A-Za-z0-9_]{1,10})?\*?$"
)


# --------------------------------------------------------------------
# Hilfsfunktionen: Sprachschnitt + Zeilenbereinigung
# --------------------------------------------------------------------
def _extract_german_part(page_text: str) -> str:
    """
    Schneidet (wo möglich) nach dem deutschen Teil ab, bevor die
    englische/französische/spanische Version beginnt.

    Bei OW-Dokumenten findet man z.B. "LTM 1110-5.1 from 043250 ...".
    Bei UW ist die Heuristik nicht immer gegeben, daher fällt der
    Schnitt dann einfach weg.
    """
    markers = [
        "LTM 1110-5.1 from",
        "LTM 1090-4.2 from",
        "LTM 1250-5.1 from",
        "LTC 1050-3.1 from",
        "LTF 1045-4.1 from",
        "from 0",  # sehr generisch, aber in diesen PDFs typisch
    ]
    idxs = [page_text.find(m) for m in markers if m in page_text]
    if idxs:
        cut = min(idxs)
        return page_text[:cut]
    return page_text


def _normalize_lines(text: str) -> List[str]:
    """
    Entfernt offensichtliche Kopf-/Fußzeilen und leere Zeilen.
    """
    lines: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Copyright by"):
            continue
        # deutsche BMK-Kopfzeilen
        if "BMK" in line and "Bauteileübersicht" in line:
            continue
        # andere Sprachvarianten können bleiben, stören aber nicht massiv
        if "LWE - Customer Service" in line:
            continue
        lines.append(line)
    return lines


# --------------------------------------------------------------------
# OCR-Fallback (optional)
# --------------------------------------------------------------------
def ocr_pdf_page(pdf_path: Path, page_index: int) -> str:
    """
    Rendert eine Seite des PDFs als Bild und führt Tesseract-OCR aus.
    page_index ist 0-basiert.
    """
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf.get_page(page_index)

    # ca. 200 DPI
    bitmap = page.render(scale=200 / 72)
    pil_image: Image.Image = bitmap.to_pil()

    page.close()
    pdf.close()

    text = pytesseract.image_to_string(pil_image, lang=OCR_LANG)
    return text


# --------------------------------------------------------------------
# Parser für eine BMK-PDF (Unterwagen / Oberwagen)
# --------------------------------------------------------------------
def parse_bmk_pdf(pdf_path: Path, model_name: str, wagon: str) -> Dict[str, Any]:
    """
    Liest eine BMK-PDF und extrahiert eine Komponentenliste.

    Struktur des Rückgabe-Objekts:
    {
        "type": "BMK_LIST",
        "model": "...",
        "wagon": "unterwagen" | "oberwagen",
        "source_file": "...pdf",
        "component_count": N,
        "components": [
            {
                "bmk": "S302",
                "model": "LTM1110-5.1",
                "wagon": "unterwagen",
                "area": "Krankabine",
                "group": "Steuerstand",
                "title": "LICCON-Monitor, Pedale",
                "description": "Zündstartschalter\nOberwagen\n...",
                "lsb_address": "2 10"
            },
            ...
        ]
    }
    """
    reader = PdfReader(str(pdf_path))
    components: List[Dict[str, Any]] = []

    current_area: Optional[str] = None
    current_group: Optional[str] = None
    current_title: Optional[str] = None
    current_entry: Optional[Dict[str, Any]] = None
    awaiting_lsb_addr = False

    for page_index, page in enumerate(reader.pages):
        page_no = page_index + 1

        # 1) Normaler pypdf-Text
        raw_text = page.extract_text() or ""

        # 2) Optionaler OCR-Fallback, falls kein Text und OCR aktiviert
        if OCR_ENABLED and not raw_text.strip():
            print(
                f"  [Seite {page_no}] BMK: Fallback auf OCR "
                f"(leer, Länge={len(raw_text)})"
            )
            try:
                raw_text = ocr_pdf_page(pdf_path, page_index)
            except Exception as e:
                print(f"  [Seite {page_no}] BMK OCR FEHLER: {e}")
                raw_text = ""

        if not raw_text.strip():
            continue

        # nur den deutschen Abschnitt verwenden, soweit erkennbar
        de_text = _extract_german_part(raw_text)
        lines = _normalize_lines(de_text)

        for line in lines:
            # 1) Bereichsüberschrift (z.B. "Krankabine:")
            if line.endswith(":") and not BMK_CODE_RE.match(line):
                current_area = line.rstrip(":").strip()
                current_group = None
                current_title = None
                awaiting_lsb_addr = False
                continue

            # 2) Innerhalb eines Bereichs: Gruppe + "Titel"
            #    Beispiel:
            #       Krankabine:
            #       Steuerstand           -> group
            #       LICCON-Monitor, ...  -> title
            if current_area and not BMK_CODE_RE.match(line):
                if current_group is None and len(line) <= 40:
                    current_group = line.strip()
                    continue
                if current_title is None and len(line) <= 80:
                    current_title = line.strip()
                    continue

            # 3) BMK-Zeile: neue Komponente starten
            if BMK_CODE_RE.match(line):
                # Vorherigen Eintrag abschließen
                if current_entry is not None:
                    current_entry["description"] = "\n".join(
                        current_entry.get("description_lines", [])
                    ).strip()
                    current_entry.pop("description_lines", None)
                    components.append(current_entry)

                current_entry = {
                    "bmk": line.strip(),
                    "model": model_name,
                    "wagon": wagon,
                    "area": current_area,
                    "group": current_group,
                    "title": current_title,
                    "description_lines": [],
                    "lsb_address": None,
                }
                awaiting_lsb_addr = False
                continue

            # 4) Zeilen, die zu einem aktuellen BMK gehören
            if current_entry is not None:
                # LSB-Adresse: Muster "LSB Adr" (z.B. "LSB Adr" / nächste Zeile "2 10")
                if line.startswith("LSB Adr"):
                    current_entry["description_lines"].append(line)
                    awaiting_lsb_addr = True
                    continue

                if awaiting_lsb_addr:
                    current_entry["lsb_address"] = line.strip()
                    current_entry["description_lines"].append(line)
                    awaiting_lsb_addr = False
                    continue

                # alle anderen Zeilen als Beschreibungszeilen anhängen
                current_entry["description_lines"].append(line)

    # Letzten Eintrag abschließen
    if current_entry is not None:
        current_entry["description"] = "\n".join(
            current_entry.get("description_lines", [])
        ).strip()
        current_entry.pop("description_lines", None)
        components.append(current_entry)

    return {
        "type": "BMK_LIST",
        "model": model_name,
        "wagon": wagon,
        "source_file": pdf_path.name,
        "component_count": len(components),
        "components": components,
    }


# --------------------------------------------------------------------
# Modell- & Wagen-Erkennung aus Dateinamen
# --------------------------------------------------------------------
def detect_model_and_wagon_from_path(pdf_path: Path) -> tuple[str, str]:
    """
    Ermittelt (Modell, Wagen) aus Dateinamen + Inhalt.

    In der neuen Struktur wird das Modell primär aus dem Ordnernamen
    gezogen, diese Funktion bleibt aber als Fallback und für OW/UW-Erkennung.
    """
    name = pdf_path.name.lower()

    if "_uw_" in name:
        wagon = "unterwagen"
    elif "_ow_" in name:
        wagon = "oberwagen"
    else:
        wagon = "unknown"

    model = detect_model_generic(pdf_path)

    if not model:
        # Fallback: z.B. shb_ltm_1110_5-1_uw_02_1000_043250_de_en_fr_es.pdf
        m = re.search(r"(ltm|ltc|ltf)[ _]?(\d{3,4})[_-](\d)-(\d)", name)
        if m:
            prefix, num4, a, b = m.groups()
            model = f"{prefix.upper()}{num4}-{a}.{b}"
        else:
            model = pdf_path.stem

    return model, wagon


# --------------------------------------------------------------------
# Input-Discovery: neue Struktur input/<MODEL>/bmk/*.pdf
# --------------------------------------------------------------------
def discover_bmk_pdfs() -> List[Tuple[str, Path]]:
    """
    Sucht BMK-PDFs in der neuen Struktur:

        input/<MODEL>/bmk/*.pdf

    und gibt (model_name, pdf_path) zurück.
    """
    pairs: List[Tuple[str, Path]] = []
    for model_dir in sorted(INPUT_ROOT.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        bmk_dir = model_dir / "bmk"
        if not bmk_dir.exists():
            continue
        for pdf in sorted(bmk_dir.glob("*.pdf")):
            pairs.append((model_name, pdf))
    return pairs


# --------------------------------------------------------------------
# Verarbeitung aller BMK-PDFs
# --------------------------------------------------------------------
def process_all_bmk_pdfs() -> None:
    if not INPUT_ROOT.exists():
        print(f"Eingabeordner existiert nicht: {INPUT_ROOT}")
        return

    pairs = discover_bmk_pdfs()
    if not pairs:
        print(f"Keine BMK-PDFs in input/<MODEL>/bmk unter {INPUT_ROOT} gefunden.")
        return

    for folder_model, pdf_path in pairs:
        print(f"Verarbeite BMK-PDF: {pdf_path.name}")

        # OW/UW aus Dateinamen ermitteln, Modell aus Ordnername
        detected_model, wagon = detect_model_and_wagon_from_path(pdf_path)
        model = folder_model

        if detected_model and detected_model != model:
            print(
                f"  -> Hinweis: detect_model_generic() meldet '{detected_model}', "
                f"Ordnername ist aber '{model}'. Ordnername wird verwendet."
            )

        print(f"  -> Modell: {model}, Wagen: {wagon}")

        data = parse_bmk_pdf(pdf_path, model, wagon)
        print(f"  -> Komponenten gefunden: {data['component_count']}")

        model_dir = OUTPUT_MODELS_DIR / model
        model_dir.mkdir(parents=True, exist_ok=True)

        suffix = "BMK"
        if wagon == "unterwagen":
            suffix = "BMK_UW"
        elif wagon == "oberwagen":
            suffix = "BMK_OW"

        output_file = model_dir / f"{model}_{suffix}.json"

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  -> JSON gespeichert: {output_file}")


def main() -> None:
    print("=== BMK-PARSER (mit Modellerkennung, Config & OCR-Fallback) ===")
    process_all_bmk_pdfs()
    print("=== FERTIG ===")


if __name__ == "__main__":
    main()
