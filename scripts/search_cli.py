# Datei: scripts/search_cli.py
"""
Einfache Kommandozeilen-Suche über den lokalen Embedding-Index.

Beispiele:

    # Einfache Frage
    python scripts/search_cli.py "LTM1110 Unterwagen Fehler 0123 Hydraulikdruck"

    # Mit Modell-Filter
    python scripts/search_cli.py "CAN-Bus Fehleradresse 35" --model LTM1110-5.1

    # Nur LEC-Fehler durchsuchen
    python scripts/search_cli.py "Drucksensor Ausfall" --source-type lec_error

Voraussetzung:
    - knowledge_chunks.jsonl wurde erzeugt
    - build_local_embedding_index.py ausgeführt
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

# Basis: .../kran-tools
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.semantic_index import has_embedding_index, search_similar  # type: ignore[import]
from scripts.config_loader import get_config  # type: ignore[import]


def print_result(result: dict, index: int) -> None:
    """
    Gibt einen einzelnen Treffer hübsch auf der Konsole aus.
    """
    score = float(result.get("score", 0.0))
    model = result.get("model") or "-"
    source_type = result.get("source_type") or "-"
    meta = result.get("metadata") or {}

    code = meta.get("code") or meta.get("bmk") or ""
    blatt = meta.get("blatt") or meta.get("sheet") or ""
    wagon = meta.get("wagon") or meta.get("wagen") or ""
    stecker = meta.get("stecker") or ""
    addr = meta.get("lsb_address") or ""
    short_text = meta.get("short_text") or ""
    area = meta.get("area") or ""
    group = meta.get("group") or ""
    has_long = meta.get("has_long_text")
    has_desc = meta.get("has_description")

    print("=" * 80)
    print(f"[{index}] Modell: {model} | Quelle: {source_type} | Score: {score:.3f}")
    print("-" * 80)

    if code:
        print(f"  Code/BMK      : {code}")
    if blatt:
        print(f"  Blatt         : {blatt}")
    if wagon:
        print(f"  Wagen         : {wagon}")
    if stecker:
        print(f"  Stecker       : {stecker}")
    if addr:
        print(f"  LSB-Adresse   : {addr}")
    if area or group:
        print(f"  Bereich/Gruppe: {area or '-'} / {group or '-'}")
    if short_text:
        wrapped = textwrap.fill(short_text, width=76, subsequent_indent=" " * 18)
        print(f"  Titel         : {wrapped}")
    if has_long:
        print("  Langtext      : vorhanden")
    if has_desc:
        print("  Beschreibung  : vorhanden")

    if not any([code, blatt, wagon, stecker, addr, short_text, area, group, has_long, has_desc]):
        print("  (Keine detaillierten Metadaten vorhanden.)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantische Suche im Kran-Wissensindex (lokal)."
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Frage / Problem, z.B. 'LTM1110 Unterwagen Fehler 0123 Hydraulikdruck'",
    )
    parser.add_argument(
        "--model",
        "-m",
        dest="model",
        help="Kranmodell filtern, z.B. LTM1110-5.1",
    )
    parser.add_argument(
        "--source-type",
        "-s",
        dest="source_type",
        help="Quelle filtern (lec_error, bmk_component, base_document, spl_reference)",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        dest="top_k",
        type=int,
        default=5,
        help="Anzahl der Treffer (Standard: 5)",
    )

    args = parser.parse_args()

    if not has_embedding_index():
        print(
            "ERROR: Kein Embedding-Index gefunden.\n"
            "Bitte zuerst:\n"
            "  1) Embedding-Chunks erzeugen (CLI: [8] Embedding-Export)\n"
            "  2) build_local_embedding_index.py ausführen\n"
        )
        sys.exit(1)

    if args.question:
        question = args.question.strip()
    else:
        try:
            question = input("Frage / Problem eingeben: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAbbruch.")
            return

    if not question:
        print("Keine Frage eingegeben – Abbruch.")
        return

    print(f"\nSuche nach: {question!r}")
    if args.model:
        print(f"  Modell-Filter    : {args.model}")
    if args.source_type:
        print(f"  Quellen-Filter   : {args.source_type}")
    print(f"  Anzahl Treffer   : {args.top_k}")
    print()

    results = search_similar(
        query=question,
        top_k=args.top_k,
        model_filter=args.model,
        source_type_filter=args.source_type,
    )

    if not results:
        print("Keine Treffer gefunden.")
        return

    for idx, r in enumerate(results, start=1):
        print_result(r, idx)


if __name__ == "__main__":
    main()
