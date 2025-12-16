# Datei: scripts/run_pdfdoc_pipeline.py
"""
Komplette PDFDoc-/Kran-Tools-Pipeline:

1) Wissensmodule aus allen PDFs bauen
2) LEC-Fehlercodelisten parsen
3) SPL-Schaltpläne parsen (inkl. OCR-Fallback, falls konfiguriert)
4) BMK-Listen (UW/OW) parsen
5) Pro Modell FULL_KNOWLEDGE.json erzeugen (Merge)
6) Globale Indizes (Fehlercodes + BMKs) bauen
7) Markdown-Report zum Lauf erstellen
"""

from __future__ import annotations

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.wissensmodul_builder import main as run_wissensmodule
from scripts.lec_parser import main as run_lec_parser
from scripts.spl_parser import process_all_spl_pdfs
from scripts.bmk_parser import main as run_bmk_parser
from scripts.merge_knowledge import main as run_merge
from scripts.global_index_builder import main as run_global_indices
from scripts.run_report import main as run_report


def main() -> None:
    print("===================================================")
    print(" PDFDOC / KRAN-TOOLS – GESAMT-PIPELINE")
    print("===================================================")
    print(f"Projektpfad: {BASE_DIR}")
    print("")

    # 1) Wissensmodule
    print("\n[1/7] Wissensmodule bauen ...\n")
    run_wissensmodule()

    # 2) LEC-Parser
    print("\n[2/7] LEC-Fehlercodelisten parsen ...\n")
    run_lec_parser()

    # 3) SPL-Parser
    print("\n[3/7] SPL-Schaltpläne parsen ...\n")
    process_all_spl_pdfs()

    # 4) BMK-Parser
    print("\n[4/7] BMK-Listen parsen ...\n")
    run_bmk_parser()

    # 5) Merge FULL_KNOWLEDGE
    print("\n[5/7] FULL_KNOWLEDGE pro Modell erzeugen ...\n")
    run_merge()

    # 6) Globale Indizes
    print("\n[6/7] Globale Indizes bauen ...\n")
    run_global_indices()

    # 7) Markdown-Report
    print("\n[7/7] Lauf-Report (Markdown) erzeugen ...\n")
    run_report()

    print("\n=== PIPELINE FERTIG ===")


if __name__ == "__main__":
    main()
