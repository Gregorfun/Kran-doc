# Datei: scripts/lec_parser.py
"""
LEC-Parser für Fehlercodelisten mit Modellerkennung und
zentraler Konfiguration.

Neue Input-Struktur:
    input/<MODEL>/lec/*.pdf

Aufgabe:
- LEC-PDFs einlesen (z.B. "lec_044006.pdf", "LTM1110-5.1 Fehlercode.pdf")
- Alle Fehlercodes mit zugehörigen Textblöcken extrahieren
- Modell wird primär aus dem Ordnernamen abgeleitet (LTM1110-5.1, LTC1050-3.1, ...)
- Ergebnis pro Modell als JSON ablegen:

  <models_dir>/<Modell>/<Modell>_LEC_ERRORS.json

Wichtig in dieser Version:
- Fehlercodes werden als 6-stellige HEX-Codes erkannt ([0-9A-F]{6}),
  z.B. 1A0050, 1A006A usw. – so wie in der Liebherr-Liste.
- Mehrzeilige Block-Erkennung (Fehlertext + Reaktion + Behebung)
- LSB-Adressen im Fehlerblock erkennen (z.B. "LSB A Adr. 3")
  -> lsb_address (Rohtext)
  -> lsb_key (normalisiert, z.B. "LSB_A_3")
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader  # pip install pypdf

from scripts.model_detection import detect_model as detect_model_generic
from scripts.config_loader import get_config

# --------------------------------------------------------------------
# Basis-Pfade aus Config
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

# --------------------------------------------------------------------
# Regex-Definitionen
# --------------------------------------------------------------------

# Fehlerblock-Erkennung:
# - Code: 6-stellige HEX-Zeichen (0-9, A-F), z.B. 1A0050
# - steht am Zeilenanfang (ggf. mit Leerzeichen)
# - danach Kurztext bis Zeilenende
# - anschließend beliebiger Body bis zum nächsten Code oder Dateiende
ERROR_BLOCK_RE = re.compile(
    r"(^|\n)\s*(?P<code>[0-9A-F]{6})\s+(?P<header>[^\n]*)(?P<body>.*?)(?=(?:\n\s*[0-9A-F]{6}\s+)|\Z)",
    re.DOTALL | re.IGNORECASE,
)

STECKER_RE = re.compile(r"Stecker\s+([A-Za-z0-9\.\:\-_/ ]+)")
BLATT_RE = re.compile(r"Blatt\s+(\d{1,3})")
K_RE = re.compile(r"\bK\s+([A-Z]\d)\b")
W_RE = re.compile(r"\bW\s+([A-Z]\d)\b")

# LSB-Zeilen wie: "LSB A Adr. 3"
LSB_ADDR_RE = re.compile(r"(LSB\s+[A-Z]\s+Adr\.?\s*\d+)", re.IGNORECASE)


# --------------------------------------------------------------------
# Helfer für LSB-Normalisierung
# --------------------------------------------------------------------
def normalize_lsb(lsb: str | None) -> Optional[str]:
    """
    Normalisiert LSB-Angaben in eine einheitliche Form.

    Beispiele:
        "LSB A Adr. 3"  -> "LSB_A_3"
        "lsb   b adr 7" -> "LSB_B_7"
    """
    if not lsb:
        return None

    s = lsb.strip().upper()
    # Mehrfache Leerzeichen vereinheitlichen
    s = re.sub(r"\s+", " ", s)
    # "ADR." -> "ADR"
    s = s.replace("ADR.", "ADR")

    parts = s.split()
    # Erwartet: ["LSB", "A", "ADR", "3"]
    if len(parts) >= 4 and parts[0] == "LSB" and parts[2].startswith("ADR"):
        letter = parts[1]
        try:
            number = int(parts[3])
        except Exception:
            number = parts[3]
        return f"LSB_{letter}_{number}"

    # Fallback: generische Normalisierung
    return s.replace(" ", "_")


def extract_lsb_from_text(text: str | None) -> Optional[str]:
    """
    Sucht im Text nach einer LSB-Angabe (z.B. 'LSB A Adr. 3')
    und gibt den Rohtext zurück.
    """
    if not text:
        return None
    m = LSB_ADDR_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


# --------------------------------------------------------------------
# Helfer: Modellbestimmung (Fallback)
# --------------------------------------------------------------------
def fallback_model_from_filename(filename: str) -> str:
    """
    Fallback, wenn die generische Modellerkennung nichts findet.
    Wird nur noch für Alt-Layout (PDFs direkt unter input/) verwendet.
    """
    name = Path(filename).name
    lower = name.lower()

    if "lec_" in lower:
        idx = lower.index("lec_")
        return name[:idx]

    if "fehlercode" in lower:
        idx = lower.index("fehlercode")
        return name[:idx].rstrip(" -_")

    return name.rsplit(".", 1)[0]


# --------------------------------------------------------------------
# Parsing eines einzelnen LEC-PDFs
# --------------------------------------------------------------------
def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    texts: List[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        texts.append(t)
    return "\n".join(texts)


def split_into_error_blocks(full_text: str) -> List[str]:
    """
    Verwendet eine mehrzeilige Regex, um Fehlerblöcke zu finden.

    Jeder Block besteht aus:
      code + header (in der ersten Zeile)
      body (alle Folgezeilen bis zum nächsten Code oder Dateiende)
    """
    blocks: List[str] = []

    for m in ERROR_BLOCK_RE.finditer(full_text):
        code = m.group("code").strip()
        header = (m.group("header") or "").rstrip()
        body = (m.group("body") or "")

        # Blocktext rekonstruieren: erste Zeile = "code header"
        first_line = f"{code} {header}".rstrip()
        block_text = first_line
        if body:
            # Body ohne führende Zeilenumbrüche anhängen
            block_text += "\n" + body.lstrip("\n")
        blocks.append(block_text.strip())

    return blocks


def parse_error_block(block: str) -> Dict[str, Any]:
    """
    Zerlegt einen Fehlerblock in seine Bestandteile.
    """
    lines = block.splitlines()
    first_line = lines[0] if lines else ""

    # Seite-Fußzeilen wie "043563 Seite 3 von 1302 ..." ignorieren
    if "Seite" in first_line and "von" in first_line:
        return {
            "code": None,
            "short_text": first_line.strip() or None,
            "long_text": "\n".join(lines[1:]).strip() or None if len(lines) > 1 else None,
            "stecker": None,
            "blatt": None,
            "k": None,
            "w": None,
            "lsb_address": None,
            "lsb_key": None,
            "raw_block": block,
        }

    # Code + Kurztext aus erster Zeile herausziehen (HEX-Code mit 6 Stellen)
    m = re.match(r"^\s*([0-9A-F]{6})\s+(.*)$", first_line, re.IGNORECASE)
    if m:
        code = m.group(1).strip().upper()
        first_text = m.group(2).strip()
    else:
        code = None
        first_text = first_line.strip()

    stecker = None
    blatt = None
    k_coord = None
    w_coord = None

    # Volltext des Blocks für weitere Regex-Suchen nutzen
    full_block = block

    sm = STECKER_RE.search(full_block)
    if sm:
        stecker = sm.group(1).strip()

    bm = BLATT_RE.search(full_block)
    if bm:
        blatt = bm.group(1).strip()

    km = K_RE.search(full_block)
    if km:
        k_coord = km.group(1).strip()

    wm = W_RE.search(full_block)
    if wm:
        w_coord = wm.group(1).strip()

    # LSB-Adresse im gesamten Block suchen
    lsb_address: Optional[str] = extract_lsb_from_text(full_block)
    lsb_key: Optional[str] = normalize_lsb(lsb_address) if lsb_address else None

    long_lines = lines[1:] if len(lines) > 1 else []
    long_text = "\n".join(long_lines).strip() if long_lines else ""

    return {
        "code": code,
        "short_text": first_text or None,
        "long_text": long_text or None,
        "stecker": stecker,
        "blatt": blatt,
        "k": k_coord,
        "w": w_coord,
        "lsb_address": lsb_address,
        "lsb_key": lsb_key,
        "raw_block": block,
    }


def parse_lec_pdf(pdf_path: Path, model: str) -> Dict[str, Any]:
    print(f"  -> lese Text aus: {pdf_path.name}")
    full_text = extract_text_from_pdf(pdf_path)

    if not full_text.strip():
        print("  -> WARNUNG: PDF-TEXT leer, keine Fehlercodes gefunden.")
        error_list: List[Dict[str, Any]] = []
    else:
        blocks = split_into_error_blocks(full_text)
        print(f"  -> erkannte Fehlercode-Blöcke (roh): {len(blocks)}")
        error_list = [parse_error_block(b) for b in blocks]
        # nur Einträge mit echtem Code behalten
        error_list = [e for e in error_list if e.get("code")]

    return {
        "type": "LEC_ERRORS",
        "model": model,
        "source_file": pdf_path.name,
        "error_count": len(error_list),
        "errors": error_list,
    }


# --------------------------------------------------------------------
# Input-Discovery: neue Struktur input/<MODEL>/lec/*.pdf
# --------------------------------------------------------------------
def discover_lec_pdfs() -> List[Tuple[Optional[str], Path]]:
    """
    Sucht LEC/Fehlercode-PDFs.

    1) Neue Struktur:
       input/<MODEL>/lec/*.pdf  -> (MODEL, pdf_path)
    2) Fallback (Alt-Layout):
       PDFs direkt unter INPUT_ROOT: *lec*.pdf, *Fehlercode*.pdf
       -> (None, pdf_path)  (Modell wird dann per Erkennung bestimmt)
    """
    pairs: List[Tuple[Optional[str], Path]] = []

    # 1) Neue Struktur
    for model_dir in sorted(INPUT_ROOT.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        lec_dir = model_dir / "lec"
        if not lec_dir.exists():
            continue
        for pdf in sorted(lec_dir.glob("*.pdf")):
            pairs.append((model_name, pdf))

    # 2) Fallback: Alt-Layout
    legacy_candidates = sorted(
        list(INPUT_ROOT.glob("*lec*.pdf")) + list(INPUT_ROOT.glob("*Fehlercode*.pdf"))
    )
    for pdf in legacy_candidates:
        pairs.append((None, pdf))

    return pairs


# --------------------------------------------------------------------
# Verarbeitung aller LEC-PDFs
# --------------------------------------------------------------------
def process_all_lec_pdfs() -> None:
    if not INPUT_ROOT.exists():
        print(f"Eingabeordner existiert nicht: {INPUT_ROOT}")
        return

    candidates = discover_lec_pdfs()
    if not candidates:
        print(f"Keine LEC/Fehlercode-PDFs unter {INPUT_ROOT} gefunden.")
        return

    for model_hint, pdf_path in candidates:
        print(f"Verarbeite LEC-PDF: {pdf_path.name}")

        if model_hint:
            # Modell aus Ordnername
            model = model_hint.strip()
            # optionaler Plausibilitäts-Check:
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
            print(f"  -> erkanntes Modell (Alt-Layout): {model}")

        print(f"  -> Modell: {model}")

        lec_data = parse_lec_pdf(pdf_path, model)

        model_dir = OUTPUT_MODELS_DIR / model
        model_dir.mkdir(parents=True, exist_ok=True)

        output_file = model_dir / f"{model}_LEC_ERRORS.json"

        with output_file.open("w", encoding="utf-8") as f:
            json.dump(lec_data, f, ensure_ascii=False, indent=2)

        print(
            f"  -> JSON gespeichert: {output_file} "
            f"(Fehlercodes: {lec_data['error_count']})"
        )


def main() -> None:
    print("=== LEC-PARSER (mit Modellerkennung & HEX-Fehlercodes) ===")
    process_all_lec_pdfs()
    print("=== FERTIG ===")


if __name__ == "__main__":
    main()
