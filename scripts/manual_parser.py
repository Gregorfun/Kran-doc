# Datei: scripts/manual_parser.py
"""
manual_parser.py

Liest Handbuch-PDFs für ein Kranmodell ein und erzeugt eine
MANUAL_KNOWLEDGE-Datei im JSON-Format.

Neue Standardpfade:
  Input-PDFs:   input/<MODEL>/manuals/*.pdf
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

try:
    from pypdf import PdfReader  # moderner Nachfolger von PyPDF2
except ImportError:
    PdfReader = None


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
    Rückgabe: Liste von Strings, index = page_index (0-based).
    """
    if PdfReader is None:
        print(
            "[manual_parser] ERROR: pypdf ist nicht installiert. "
            "Bitte mit 'pip install pypdf' nachinstallieren.",
            file=sys.stderr,
        )
        return []

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"[manual_parser] ERROR: Konnte PDF {pdf_path} nicht öffnen: {e}", file=sys.stderr)
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

        # Grobe Bereinigung
        txt = txt.replace("\r", "\n")
        # Mehrfache Leerzeilen etwas eindampfen
        while "\n\n\n" in txt:
            txt = txt.replace("\n\n\n", "\n\n")

        pages_text.append(txt.strip())

    return pages_text


def build_sections_from_pdfs(model: str, input_dir: Path) -> List[ManualSection]:
    """
    Lädt alle PDFs aus input_dir und erzeugt pro Seite eine ManualSection.
    Seiten ohne nennenswerten Text werden übersprungen.
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

    print(f"[manual_parser] INFO: Verarbeite {len(pdf_files)} PDF-Datei(en) für Modell {model}.")

    for pdf in pdf_files:
        print(f"[manual_parser] INFO: Lese {pdf.name} ...")
        pages_text = extract_text_from_pdf(pdf)
        if not pages_text:
            continue

        for idx, page_text in enumerate(pages_text):
            page_num = idx + 1

            # Seiten ohne Text oder nur mit sehr wenig Inhalt überspringen
            if not page_text or len(page_text) < 40:
                continue

            sec_id = f"{pdf.stem}_p{page_num:03d}"
            title = f"{model} Handbuch – {pdf.stem} – Seite {page_num}"

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
    Schreibt die MANUAL_KNOWLEDGE-Datei für ein Modell.
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

    print(f"[manual_parser] INFO: MANUAL_KNOWLEDGE für {model} geschrieben nach {out_path}")
    return out_path


# ---------------------------------------------------------
# Main / CLI
# ---------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    base_dir = Path(__file__).resolve().parents[1]  # .../kran-tools

    parser = argparse.ArgumentParser(
        description="Erzeuge MANUAL_KNOWLEDGE aus Handbuch-PDFs für ein Kranmodell.",
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
            "Standard: input/<MODEL>/manuals/"
        ),
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Ausgabeverzeichnis für MANUAL_KNOWLEDGE. "
            "Standard: output/models/<MODEL>/"
        ),
    )

    args = parser.parse_args(argv)
    model = args.model.strip()

    # NEU: Default-Input ist input/<MODEL>/manuals
    input_dir = Path(args.input_dir) if args.input_dir else (
        base_dir / "input" / model / "manuals"
    )
    output_dir = Path(args.output_dir) if args.output_dir else (
        base_dir / "output" / "models" / model
    )

    print(f"[manual_parser] BASE_DIR:      {base_dir}")
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
