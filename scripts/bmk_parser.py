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

WICHTIG (Stabilitäts-Regel):
- BMK-Einträge werden IMMER mit "lang" versehen (de/en/fr/es/it).
- Default-Filter (Webapp): nur "de".
- Parser bleibt kompatibel: bestehende Felder bleiben unverändert, "lang" kommt hinzu.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Lauf aus repo-root oder direkt aus scripts/ ermöglichen
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pypdf import PdfReader  # pip install pypdf

# OCR-Fallback (optional, abhängig von config.yaml)
import pypdfium2 as pdfium   # pip install pypdfium2
from PIL import Image        # pip install pillow
import pytesseract           # pip install pytesseract

try:
    from scripts.model_detection import detect_model as detect_model_generic
except Exception:
    from model_detection import detect_model as detect_model_generic

try:
    from scripts.config_loader import get_config
except Exception:
    # falls config_loader.py nicht in scripts liegt:
    from config_loader import get_config


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

_models_dir = Path(CONFIG.models_dir)
if not _models_dir.is_absolute():
    OUTPUT_MODELS_DIR = BASE_DIR / _models_dir
else:
    OUTPUT_MODELS_DIR = _models_dir

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
# Text-Cleaner (wichtig für "umgeschlüsselt"/PDF-Extraktions-Artefakte)
# --------------------------------------------------------------------
_BAD_CHARS_RE = re.compile(r"[\uFFFC\uFFFD\uFEFF]")  # OBJ-REPL / replacement / BOM

def _clean_line(s: str) -> str:
    # In Liebherr-PDFs taucht manchmal ein "￾" als Trennzeichen im Wort auf
    # (z.B. Rundumkenn￾leuchte). Das entfernen wir.
    s = (s or "").replace("￾", "")
    s = _BAD_CHARS_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# --------------------------------------------------------------------
# Sprach-Erkennung (für BMK: de/en/fr/es/it)
# --------------------------------------------------------------------
_LANG_MARKERS = {
    "de": [
        "oberwagen", "unterwagen", "krankabine", "steuerstand", "beleuchtung",
        "warnleuchte", "rundumkennleuchte", "widerstand", "winkelgeber", "kanal",
        "hinweis", "ersteller", "ausgabe", "schmier", "druck", "geber", "modul",
    ],
    "en": [
        "superstructure", "chassis", "crane cabin", "control stand", "lighting",
        "warning", "resistor", "module", "angle sensor", "channel", "note", "issue",
        "originator", "pressure", "central greasing",
    ],
    "fr": [
        "tourelle", "porteur", "cabine", "poste de commande", "eclairage",
        "avertisseur", "module", "résistance", "capteur", "canal", "consigne",
        "rédacteur", "édition", "pression",
    ],
    "es": [
        "superstructura", "chasis", "cabina", "puesto de mando", "iluminación",
        "advertencia", "módulo", "modulo", "resistencias", "codificador", "ángulo",
        "angulo", "canal", "nota", "edición", "presión", "presion",
    ],
    "it": [
        "torretta", "carro", "cabina", "banco di comando", "illuminazione",
        "avviso", "modulo", "resistenza", "sensore", "canale", "nota", "edizione",
        "pressione",
    ],
}

def _detect_lang(text: str) -> str:
    t = (text or "").lower()
    if not t.strip():
        return "de"

    scores = {k: 0 for k in _LANG_MARKERS.keys()}
    for lang, markers in _LANG_MARKERS.items():
        for m in markers:
            if m in t:
                scores[lang] += 1

    best_lang, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_lang if best_score > 0 else "de"

# --------------------------------------------------------------------
# Hilfsfunktionen: Zeilenbereinigung
# --------------------------------------------------------------------
def _normalize_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in (text or "").splitlines():
        line = _clean_line(raw)
        if not line:
            continue

        # Header/Fuß-Zeugs (mehrsprachig)
        if line.startswith("Copyright by"):
            continue
        if "LWE - Customer Service" in line:
            continue
        if line.lower().startswith("kundendienst-technische dokumentation"):
            continue
        if line.lower().startswith("service department-technical documentation"):
            continue
        if line.lower().startswith("service après-vente"):
            continue
        if line.lower().startswith("documentación técnica"):
            continue
        if line.lower().startswith("servizio di assistenza"):
            continue

        # typisches Meta
        if line.lower().startswith("ersteller:") or line.lower().startswith("originator:") or line.lower().startswith("rédacteur"):
            continue

        lines.append(line)
    return lines

# --------------------------------------------------------------------
# OCR-Fallback (optional)
# --------------------------------------------------------------------
def ocr_pdf_page(pdf_path: Path, page_index: int) -> str:
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf.get_page(page_index)

    bitmap = page.render(scale=200 / 72)  # ca. 200 DPI
    pil_image: Image.Image = bitmap.to_pil()

    page.close()
    pdf.close()

    return pytesseract.image_to_string(pil_image, lang=OCR_LANG)

# --------------------------------------------------------------------
# Parser für eine BMK-PDF (Unterwagen / Oberwagen)
# --------------------------------------------------------------------
def parse_bmk_pdf(pdf_path: Path, model_name: str, wagon: str) -> Dict[str, Any]:
    """
    NEU:
    - Sprachblock-Erkennung via Bereichsüberschriften:
      "Oberwagen allgemein:" -> de, "Superstructure general:" -> en, ...
    - Nur die "de"-Blöcke werden in components aufgenommen.
    - Jeder Eintrag bekommt component["lang"].
    """
    reader = PdfReader(str(pdf_path))
    components: List[Dict[str, Any]] = []

    current_area: Optional[str] = None
    current_group: Optional[str] = None
    current_title: Optional[str] = None
    current_entry: Optional[Dict[str, Any]] = None
    awaiting_lsb_addr = False

    current_lang = "de"
    seen_langs = set()

    for page_index, page in enumerate(reader.pages):
        page_no = page_index + 1
        raw_text = page.extract_text() or ""

        if OCR_ENABLED and not raw_text.strip():
            print(f"  [Seite {page_no}] BMK: Fallback auf OCR (leer)")
            try:
                raw_text = ocr_pdf_page(pdf_path, page_index)
            except Exception as e:
                print(f"  [Seite {page_no}] BMK OCR FEHLER: {e}")
                raw_text = ""

        if not raw_text.strip():
            continue

        lines = _normalize_lines(raw_text)

        for line in lines:
            # Bereichsüberschrift (…:)
            if line.endswith(":") and not BMK_CODE_RE.match(line):
                current_lang = _detect_lang(line)
                seen_langs.add(current_lang)

                # Bereichs-Kontext nur in DE weiterführen
                if current_lang == "de":
                    current_area = line.rstrip(":").strip()
                    current_group = None
                    current_title = None
                    awaiting_lsb_addr = False
                continue

            # ab hier: nur DE verarbeiten
            if current_lang != "de":
                continue

            # Gruppe / Titel (DE)
            if current_area and not BMK_CODE_RE.match(line):
                if current_group is None and len(line) <= 60:
                    current_group = line.strip()
                    continue
                if current_title is None and len(line) <= 120:
                    current_title = line.strip()
                    continue

            # BMK-Code (DE)
            if BMK_CODE_RE.match(line):
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
                    "lang": "de",
                }
                awaiting_lsb_addr = False
                continue

            # Beschreibung (DE)
            if current_entry is not None:
                if line.lower().startswith("lsb") and ("adr" in line.lower() or "adresse" in line.lower() or "addr" in line.lower()):
                    current_entry["description_lines"].append(line)
                    awaiting_lsb_addr = True
                    continue

                if awaiting_lsb_addr:
                    current_entry["lsb_address"] = line.strip()
                    current_entry["description_lines"].append(line)
                    awaiting_lsb_addr = False
                    continue

                current_entry["description_lines"].append(line)

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
        "languages_in_source": sorted(seen_langs) if seen_langs else ["de"],
    }

# --------------------------------------------------------------------
# Modell- & Wagen-Erkennung aus Dateinamen
# --------------------------------------------------------------------
def detect_model_and_wagon_from_path(pdf_path: Path) -> tuple[str, str]:
    """
    Verbesserte Wagen-Erkennung:
    - akzeptiert auch Dateinamen wie "BMK OW LTM 1090-4.2.pdf"
    - akzeptiert "oberwagen/unterwagen" im Namen
    """
    name = pdf_path.name.lower()

    wagon = "unknown"
    if re.search(r"(?<![a-z0-9])uw(?![a-z0-9])|unterwagen", name):
        wagon = "unterwagen"
    elif re.search(r"(?<![a-z0-9])ow(?![a-z0-9])|oberwagen", name):
        wagon = "oberwagen"

    model = detect_model_generic(pdf_path)

    if not model:
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

        detected_model, wagon = detect_model_and_wagon_from_path(pdf_path)
        model = folder_model

        if detected_model and detected_model != model:
            print(
                f"  -> Hinweis: detect_model_generic() meldet '{detected_model}', "
                f"Ordnername ist aber '{model}'. Ordnername wird verwendet."
            )

        print(f"  -> Modell: {model}, Wagen: {wagon}")

        data = parse_bmk_pdf(pdf_path, model, wagon)
        print(
            f"  -> Komponenten gefunden (DE): {data['component_count']} | "
            f"Sprachen im PDF: {data.get('languages_in_source')}"
        )

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
    print("=== BMK-PARSER (Config & OCR-Fallback) ===")
    process_all_bmk_pdfs()
    print("=== FERTIG ===")

if __name__ == "__main__":
    main()
