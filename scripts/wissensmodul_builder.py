# Datei: scripts/wissensmodul_builder.py
"""
WISSENSMODUL-BUILDER

Baut pro Kranmodell ein kompaktes Wissensmodul aus den Handbuch-PDFs.

Neue Input-Struktur:
    input/<MODEL>/manuals/*.pdf

Output:
    output/models/<MODEL>/<MODEL>_GPT51_WISSENSMODUL.json

Beispiel:
    input/LTM1110-5.1/manuals/bal_19700-10-01 LTM 1110-5.1.pdf
    ->
    output/models/LTM1110-5.1/LTM1110-5.1_GPT51_WISSENSMODUL.json

Konfiguration (config.yaml):
    input_pdf_dir     -> Wurzel-Ordner, z.B. "input"
    models_dir        -> Output-Basis, z.B. "output/models"
    max_sample_pages  -> wie viele Seiten pro PDF gesampelt werden
    max_sample_chars  -> maximal Zeichen pro Textprobe
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any

from pypdf import PdfReader  # pip install pypdf

from scripts.config_loader import get_config
from scripts.model_detection import detect_model as detect_model_generic

# --------------------------------------------------------------------
# Pfade & Konfiguration
# --------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = get_config()

_input_root = Path(CONFIG.input_pdf_dir)
if not _input_root.is_absolute():
    INPUT_ROOT = BASE_DIR / _input_root
else:
    INPUT_ROOT = _input_root
INPUT_ROOT.mkdir(parents=True, exist_ok=True)

_models_dir = Path(CONFIG.models_dir)
if not _models_dir.is_absolute():
    OUTPUT_MODELS_DIR = BASE_DIR / _models_dir
else:
    OUTPUT_MODELS_DIR = _models_dir
OUTPUT_MODELS_DIR.mkdir(parents=True, exist_ok=True)

MAX_SAMPLE_PAGES: int = int(getattr(CONFIG, "max_sample_pages", 3))
MAX_SAMPLE_CHARS: int = int(getattr(CONFIG, "max_sample_chars", 1000))


# --------------------------------------------------------------------
# Datentyp: einzelne Textprobe aus einem Handbuch
# --------------------------------------------------------------------

@dataclass
class WissenSample:
    id: str
    model: str
    source_file: str
    page_start: int
    page_end: int
    title: str
    text: str
    source_type: str = "base_document"
    meta: Dict[str, Any] | None = None


# --------------------------------------------------------------------
# Input-Discovery: Handbuch-PDFs finden
# --------------------------------------------------------------------

def discover_manual_pdfs() -> Dict[str, List[Path]]:
    """
    Sucht Handbuch-PDFs unter input/<MODEL>/manuals/*.pdf.

    Rückgabe:
        { "LTM1110-5.1": [Path(...), ...],
          "LTC1050-3.1": [Path(...), ...],
          ... }
    """
    model_to_pdfs: Dict[str, List[Path]] = {}

    for model_dir in sorted(INPUT_ROOT.iterdir()):
        if not model_dir.is_dir():
            continue

        model_name = model_dir.name
        manuals_dir = model_dir / "manuals"
        if not manuals_dir.exists():
            continue

        pdfs = sorted(p for p in manuals_dir.glob("*.pdf") if p.is_file())
        if not pdfs:
            continue

        model_to_pdfs[model_name] = pdfs

    return model_to_pdfs


# --------------------------------------------------------------------
# Text-Extraktion & Sampling
# --------------------------------------------------------------------

def extract_samples_from_pdf(model: str, pdf_path: Path) -> List[WissenSample]:
    """
    Liest bis zu MAX_SAMPLE_PAGES Seiten aus dem PDF und erzeugt
    Textproben (Samples), abgeschnitten bei MAX_SAMPLE_CHARS Zeichen.
    """
    samples: List[WissenSample] = []

    reader = PdfReader(str(pdf_path))
    num_pages = len(reader.pages)
    pages_to_read = min(MAX_SAMPLE_PAGES, num_pages)

    for page_index in range(pages_to_read):
        page = reader.pages[page_index]
        raw_text = page.extract_text() or ""
        text = raw_text.replace("\r", "\n").strip()
        if not text:
            continue

        if len(text) > MAX_SAMPLE_CHARS:
            text = text[:MAX_SAMPLE_CHARS].rstrip() + " …"

        page_num = page_index + 1
        sample_id = f"{pdf_path.stem}_p{page_num:03d}"

        title = f"{model} – {pdf_path.stem} – Seite {page_num}"
        meta = {
            "model": model,
            "page": page_num,
            "file_name": pdf_path.name,
            "source_type": "base_document",
        }

        samples.append(
            WissenSample(
                id=sample_id,
                model=model,
                source_file=pdf_path.name,
                page_start=page_num,
                page_end=page_num,
                title=title,
                text=text,
                source_type="base_document",
                meta=meta,
            )
        )

    return samples


def build_wissensmodul_for_model(model: str, pdfs: List[Path]) -> Dict[str, Any]:
    """
    Erzeugt das Wissensmodul-Dictionary für ein Modell aus den
    zugehörigen Handbuch-PDFs.
    """
    all_samples: List[WissenSample] = []

    for pdf_path in pdfs:
        print(f"  -> lese Textproben aus: {pdf_path.name}")
        samples = extract_samples_from_pdf(model, pdf_path)
        all_samples.extend(samples)

    data: Dict[str, Any] = {
        "type": "GPT51_WISSENSMODUL",
        "model": model,
        "source_type": "base_document",
        "sample_count": len(all_samples),
        "samples": [asdict(s) for s in all_samples],
    }
    return data


# --------------------------------------------------------------------
# Hauptlogik: alle Modelle verarbeiten
# --------------------------------------------------------------------

def build_wissensmodule() -> None:
    print("=== WISSENSMODUL-BUILDER (mit Modellerkennung & Config) ===")

    model_to_pdfs = discover_manual_pdfs()
    if not model_to_pdfs:
        print(f"Keine Handbuch-PDFs unter {INPUT_ROOT}/<MODEL>/manuals gefunden.")
        return

    print("PDF-Dateien und zugeordnete Modelle:")
    for model_name, pdfs in sorted(model_to_pdfs.items()):
        for p in pdfs:
            print(f"  - {p.name} -> {model_name}")

    for model_name, pdfs in sorted(model_to_pdfs.items()):
        # optionaler Plausibilitätscheck mit detect_model_generic()
        # (nur Info, beeinflußt nicht die Verwendung des Ordnernamens)
        first_pdf = pdfs[0]
        detected = detect_model_generic(first_pdf)
        if detected and detected.strip() != model_name:
            print(
                f"[Hinweis] detect_model_generic() meldet '{detected}' "
                f"für {first_pdf.name}, Ordnername ist aber '{model_name}'. "
                f"Ordnername wird verwendet."
            )

        print(f"\nErzeuge Wissensmodul für Modell: {model_name}")
        data = build_wissensmodul_for_model(model_name, pdfs)

        model_out_dir = OUTPUT_MODELS_DIR / model_name
        model_out_dir.mkdir(parents=True, exist_ok=True)

        out_file = model_out_dir / f"{model_name}_GPT51_WISSENSMODUL.json"
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"  -> Wissensmodul gespeichert: {out_file}")

    print("=== FERTIG ===")


def main() -> None:
    build_wissensmodule()


if __name__ == "__main__":
    main()
