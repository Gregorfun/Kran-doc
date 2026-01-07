# Datei: scripts/manual_parser.py
"""
manual_parser.py

Liest Handbuch-PDFs fuer ein Kranmodell ein und erzeugt eine
MANUAL_KNOWLEDGE-Datei im JSON-Format.

Neue Standardpfade:
  Input-PDFs:   input/Liebherr/models/<MODEL>/manuals/*.pdf
  Output-JSON:  output/models/<MODEL>/<MODEL>_MANUAL_KNOWLEDGE.json

Aufrufbeispiel:
  python -m scripts.manual_parser --model LTM1110-5.1
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

from scripts.config_loader import get_config

try:
    from pypdf import PdfReader  # moderner Nachfolger von PyPDF2
except ImportError:
    PdfReader = None

try:
    import pypdfium2 as pdfium  # pip install pypdfium2
    from PIL import Image  # pip install pillow
    import pytesseract  # pip install pytesseract
except Exception:
    pdfium = None
    Image = None
    pytesseract = None

CONFIG = get_config()

BASE_DIR = Path(__file__).resolve().parents[1]
models_root = Path(CONFIG.models_root)
if not models_root.is_absolute():
    MODELS_ROOT = BASE_DIR / models_root
else:
    MODELS_ROOT = models_root


# ---------------------------------------------------------
# Datenstrukturen
# ---------------------------------------------------------


@dataclass
class ManualSection:
    id: str
    title: str
    text: str
    page_start: int
    page_end: int
    origin: str = "handbuch"
    meta: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------


def extract_text_from_pdf(pdf_path: Path) -> List[str]:
    """
    Extrahiert Text pro Seite aus einem PDF.
    Rueckgabe: Liste von Strings, index = page_index (0-based).
    """
    if PdfReader is None:
        print(
            "[manual_parser] ERROR: pypdf ist nicht installiert. "
            "Bitte mit 'pip install pypdf' nachinstallieren.",
            file=sys.stderr,
        )
        return []

    if CONFIG.tesseract_cmd and pytesseract is not None:
        pytesseract.pytesseract.tesseract_cmd = CONFIG.tesseract_cmd

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"[manual_parser] ERROR: Konnte PDF {pdf_path} nicht oeffnen: {e}", file=sys.stderr)
        return []

    pages_text: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception as e:
            print(
                f"[manual_parser] WARN: Fehler beim Lesen von Seite {i+1} in {pdf_path}: {e}",
                file=sys.stderr,
            )
            txt = ""

        if CONFIG.ocr_enabled and _needs_ocr(txt):
            ocr_txt = _ocr_pdf_page(pdf_path, i)
            if ocr_txt:
                txt = ocr_txt

        # Grobe Bereinigung
        txt = txt.replace("\r", "\n")
        # Mehrfache Leerzeilen etwas eindampfen
        while "\n\n\n" in txt:
            txt = txt.replace("\n\n\n", "\n\n")

        pages_text.append(txt.strip())

    return pages_text


def build_sections_from_pdfs(model: str, input_dir: Path) -> List[ManualSection]:
    """
    Laedt alle PDFs aus input_dir und erzeugt pro Seite eine ManualSection.
    Seiten ohne nennenswerten Text werden uebersprungen.
    """

    if not input_dir.exists():
        print(f"[manual_parser] WARN: Input-Verzeichnis {input_dir} existiert nicht.")
        return []

    pdf_files = sorted(p for p in input_dir.glob("*.pdf") if p.is_file())

    if not pdf_files:
        print(f"[manual_parser] WARN: Keine PDF-Dateien in {input_dir} gefunden.")
        return []

    sections: List[ManualSection] = []
    section_counter = 1

    print(f"[manual_parser] INFO: Verarbeite {len(pdf_files)} PDF-Datei(en) fuer Modell {model}.")

    for pdf in pdf_files:
        print(f"[manual_parser] INFO: Lese {pdf.name} ...")
        pages_text = extract_text_from_pdf(pdf)
        if not pages_text:
            continue

        for idx, page_text in enumerate(pages_text):
            page_num = idx + 1

            # Seiten ohne Text oder nur mit sehr wenig Inhalt ueberspringen
            if not _has_meaningful_text(page_text):
                continue

            sec_id = f"{pdf.stem}_p{page_num:03d}"
            title = f"{model} Handbuch - {pdf.stem} - Seite {page_num}"

            section = ManualSection(
                id=sec_id,
                title=title,
                text=page_text,
                page_start=page_num,
                page_end=page_num,
                origin="handbuch",
                meta={
                    "model": model,
                    "chapter": pdf.stem,
                    "source_type": "base_document",
                    "file_name": pdf.name,
                },
            )
            sections.append(section)
            section_counter += 1

    print(f"[manual_parser] INFO: Insgesamt {len(sections)} Handbuch-Sektionen erzeugt.")
    return sections


def write_manual_knowledge(
    model: str,
    sections: List[ManualSection],
    output_dir: Path,
) -> Path:
    """
    Schreibt die MANUAL_KNOWLEDGE-Datei fuer ein Modell.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{model}_MANUAL_KNOWLEDGE.json"

    data: Dict[str, Any] = {
        "model": model,
        "source_type": "base_document",
        "section_count": len(sections),
        "sections": [asdict(sec) for sec in sections],
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[manual_parser] INFO: MANUAL_KNOWLEDGE fuer {model} geschrieben nach {out_path}")
    return out_path


# ---------------------------------------------------------
# OCR / Heuristik
# ---------------------------------------------------------


def _needs_ocr(text: str) -> bool:
    sample = (text or "").strip()
    if not sample:
        return True
    if len(sample) < 50:
        return False
    total = len(sample)
    alnum = sum(1 for ch in sample if ch.isalnum())
    alnum_ratio = alnum / total
    control = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
    control_ratio = control / total
    tokens = [t for t in sample.split() if t]
    non_alnum_tokens = 0
    if tokens:
        non_alnum_tokens = sum(1 for t in tokens if not any(ch.isalnum() for ch in t))
    return alnum_ratio < 0.15 or control_ratio > 0.02 or (tokens and (non_alnum_tokens / len(tokens)) > 0.8)


def _ocr_pdf_page(pdf_path: Path, page_index: int) -> str:
    if pdfium is None or pytesseract is None:
        return ""
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        page = pdf.get_page(page_index)
        bitmap = page.render(scale=200 / 72)
        pil_image: Image.Image = bitmap.to_pil()
        page.close()
        pdf.close()
    except Exception:
        return ""
    try:
        return pytesseract.image_to_string(pil_image, lang=CONFIG.ocr_lang)
    except Exception:
        return ""


def _has_meaningful_text(text: str) -> bool:
    if not text:
        return False
    sample = text.strip()
    if not sample:
        return False
    alnum = sum(1 for ch in sample if ch.isalnum())
    if len(sample) < 40 and alnum < 10:
        return False
    if len(sample) >= 200 and alnum < 15:
        return False
    return True


# ---------------------------------------------------------
# Main / CLI
# ---------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Erzeuge MANUAL_KNOWLEDGE aus Handbuch-PDFs fuer ein Kranmodell.",
    )
    parser.add_argument(
        "--model",
        "-m",
        required=True,
        help="Kranmodell, z.B. LTM1110-5.1",
    )
    parser.add_argument(
        "--input-dir",
        help=(
            "Verzeichnis mit Handbuch-PDFs. "
            "Standard: input/Liebherr/models/<MODEL>/manuals/ (Fallback: input/<MODEL>/manuals/)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Ausgabeverzeichnis fuer MANUAL_KNOWLEDGE. "
            "Standard: output/models/<MODEL>/"
        ),
    )

    args = parser.parse_args(argv)
    model = args.model.strip()

    # Default-Input ist input/Liebherr/models/<MODEL>/manuals (Fallback: input/<MODEL>/manuals)
    if args.input_dir:
        input_dir = Path(args.input_dir)
    else:
        input_dir = MODELS_ROOT / model / "manuals"
        legacy_input = BASE_DIR / "input" / model / "manuals"
        if not input_dir.exists() and legacy_input.exists():
            input_dir = legacy_input
    output_dir = Path(args.output_dir) if args.output_dir else (
        BASE_DIR / "output" / "models" / model
    )

    print(f"[manual_parser] BASE_DIR:      {BASE_DIR}")
    print(f"[manual_parser] Modell:        {model}")
    print(f"[manual_parser] Input-Pfade:   {input_dir}")
    print(f"[manual_parser] Output-Pfade:  {output_dir}")

    sections = build_sections_from_pdfs(model=model, input_dir=input_dir)
    if not sections:
        print("[manual_parser] WARN: Keine Sektionen erzeugt, MANUAL_KNOWLEDGE wird nicht geschrieben.")
        return 1

    write_manual_knowledge(model=model, sections=sections, output_dir=output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


