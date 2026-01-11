# Datei: scripts/pdfdoc_cli.py
"""
Interaktives CLI-Menü für PDFDoc / Kran-Tools.

Funktionen:
    [1] Komplett-Pipeline (alles)
    [2] Nur Wissensmodule
    [3] Nur LEC-Parser
    [4] Nur SPL-Parser
    [5] Nur BMK-Parser
    [6] Merge: FULL_KNOWLEDGE
    [7] Globale Indizes
    [8] Embedding-Export (knowledge_chunks.jsonl)
    [0] Beenden
"""

from __future__ import annotations

import sys
from pathlib import Path
import subprocess

# Projektbasis ermitteln (Ordner "kran-tools")
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

# Einzelne Module importieren
from scripts.wissensmodul_builder import main as run_wissensmodule
from scripts.lec_parser import process_all_lec_pdfs
from scripts.spl_parser import process_all_spl_pdfs
from scripts.bmk_parser import process_all_bmk_pdfs
from scripts.merge_knowledge import main as run_merge
from scripts.global_index_builder import main as run_global_indices
from scripts.run_pdfdoc_pipeline import main as run_full_pipeline
try:
    # new name
    from scripts.export_for_embeddings import export_chunks_jsonl as run_export_embeddings
except Exception:
    # backward compatible
    from scripts.export_for_embeddings import export as run_export_embeddings


def run_explain_catalog_builder() -> None:
    """Rebuild explain catalogs (per model + aggregated) from rules/templates."""
    rules_path = BASE_DIR / "config" / "explain_rules.json"
    templates_path = BASE_DIR / "config" / "explain_templates.json"
    models_dir = BASE_DIR / "output" / "models"

    cmd = [
        sys.executable,
        str(BASE_DIR / "scripts" / "build_explain_catalog.py"),
        "--models-dir",
        str(models_dir),
        "--rules",
        str(rules_path),
        "--templates",
        str(templates_path),
        "--write-aggregated",
    ]

    print("\n[Explain] Baue Explain-Kataloge neu...")
    print(f"  models-dir: {models_dir}")
    print(f"  rules:      {rules_path}")
    print(f"  templates:  {templates_path}\n")

    try:
        subprocess.run(cmd, cwd=str(BASE_DIR), check=True)
        print("\n[Explain] Fertig. (output/explain_catalog_all.json + pro Modell)")
    except FileNotFoundError as e:
        print(f"\n[Explain] ERROR: Python/Skript nicht gefunden: {e}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"\n[Explain] ERROR: Builder fehlgeschlagen (exit={e.returncode}).", file=sys.stderr)


def print_header() -> None:
    print("=" * 60)
    print(" PDFDOC / KRAN-TOOLS – KOMFORT-MENÜ")
    print("=" * 60)
    print(f"Projektpfad: {BASE_DIR}")
    print()


def print_menu() -> None:
    print("Bitte eine Option wählen:")
    print("  [1] Komplett-Pipeline")
    print("  [2] Nur Wissensmodule bauen")
    print("  [3] Nur LEC-Parser ausführen")
    print("  [4] Nur SPL-Parser ausführen")
    print("  [5] Nur BMK-Parser ausführen")
    print("  [6] Merge: FULL_KNOWLEDGE pro Modell erzeugen")
    print("  [7] Globale Indizes (Fehlercodes + BMKs) bauen")
    print("  [8] Embedding-Export (knowledge_chunks.jsonl)")
    print("  [9] Explain-Katalog neu bauen (Regeln/Templates)")
    print("  [10] Systemcheck / Doctor (OCR/PDF/Config)")
    print("  [0] Beenden")
    print()


def wait_for_enter() -> None:
    try:
        input("\nWeiter mit [Enter] ... ")
    except KeyboardInterrupt:
        pass


def handle_choice(choice: str) -> bool:
    """
    Verarbeitet die Auswahl.
    Rückgabe:
        True  -> Menü weiter anzeigen
        False -> Programm beenden
    """
    choice = choice.strip()

    if choice == "1":
        print("\n[1] Komplett-Pipeline wird gestartet...\n")
        run_full_pipeline()
        wait_for_enter()
        return True

    if choice == "2":
        print("\n[2] Nur Wissensmodule werden gebaut...\n")
        run_wissensmodule()
        wait_for_enter()
        return True

    if choice == "3":
        print("\n[3] LEC-Parser wird ausgeführt...\n")
        process_all_lec_pdfs()
        wait_for_enter()
        return True

    if choice == "4":
        print("\n[4] SPL-Parser wird ausgeführt...\n")
        process_all_spl_pdfs()
        wait_for_enter()
        return True

    if choice == "5":
        print("\n[5] BMK-Parser wird ausgeführt...\n")
        process_all_bmk_pdfs()
        wait_for_enter()
        return True

    if choice == "6":
        print("\n[6] Merge: FULL_KNOWLEDGE wird erzeugt...\n")
        run_merge()
        wait_for_enter()
        return True

    if choice == "7":
        print("\n[7] Globale Indizes werden erstellt...\n")
        run_global_indices()
        wait_for_enter()
        return True

    if choice == "8":
        print("\n[8] Embedding-Export wird ausgeführt...\n")
        run_export_embeddings()
        wait_for_enter()
        return True

    if choice == "9":
        run_explain_catalog_builder()
        wait_for_enter()
        return True

    if choice == "10":
        print("\n[10] Systemcheck / Doctor wird ausgeführt...\n")
        cmd = [sys.executable, str(BASE_DIR / "scripts" / "doctor.py")]
        try:
            subprocess.run(cmd, cwd=str(BASE_DIR), check=False)
        except FileNotFoundError as e:
            print(f"\n[Doctor] ERROR: Python/Skript nicht gefunden: {e}", file=sys.stderr)
        wait_for_enter()
        return True

    if choice == "0":
        print("\nProgramm wird beendet.")
        return False

    print("\nUngültige Auswahl. Bitte eine Zahl aus dem Menü wählen.")
    wait_for_enter()
    return True


def main() -> None:
    while True:
        print_header()
        print_menu()
        try:
            choice = input("Auswahl: ")
        except (EOFError, KeyboardInterrupt):
            print("\n\nAbbruch. Programm wird beendet.")
            break

        if not handle_choice(choice):
            break


if __name__ == "__main__":
    main()
