#!/usr/bin/env python
"""
PDFDoc / Kran-Tools CLI

Command-line interface for managing PDFDoc/Kran-Tools pipelines.

Unterstützt:
    - Typer-basiert (moderne CLI mit --help)
    - Fallback: Interaktives Menü (wenn Typer nicht verfügbar)

Verwendung (mit Typer):
    pdfdoc pipeline run          # Komplett-Pipeline
    pdfdoc pipeline wissenmodul  # Nur Wissensmodule
    pdfdoc server --port 5002    # Flask-Server starten
    pdfdoc --help                # Hilfe anzeigen
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Projektbasis ermitteln
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from scripts.logger import get_logger

logger = get_logger(__name__)

try:
    import typer

    TYPER_AVAILABLE = True
except ImportError:
    TYPER_AVAILABLE = False


# ============================================================
# CLI APP (Typer-basiert, wenn verfügbar)
# ============================================================

if TYPER_AVAILABLE:
    app = typer.Typer(help="PDFDoc / Kran-Tools - PDF Documentation Management")

    @app.command()
    def pipeline(
        action: str = typer.Argument("run", help="Action: run, wissenmodul, lec, spl, bmk, merge, index, export"),
    ):
        """Manage documentation processing pipelines."""
        from scripts.bmk_parser import process_all_bmk_pdfs
        from scripts.export_for_embeddings import main as run_export_embeddings
        from scripts.global_index_builder import main as run_global_indices
        from scripts.lec_parser import process_all_lec_pdfs
        from scripts.merge_knowledge import main as run_merge
        from scripts.run_pdfdoc_pipeline import main as run_full_pipeline
        from scripts.spl_parser import process_all_spl_pdfs
        from scripts.wissensmodul_builder import main as run_wissensmodule

        try:
            if action == "run":
                typer.echo("🚀 Running complete pipeline...")
                run_full_pipeline()
            elif action == "wissenmodul":
                typer.echo("📚 Building knowledge modules...")
                run_wissensmodule()
            elif action == "lec":
                typer.echo("🔴 Processing LEC error codes...")
                process_all_lec_pdfs()
            elif action == "spl":
                typer.echo("📋 Processing SPL schematics...")
                process_all_spl_pdfs()
            elif action == "bmk":
                typer.echo("🔧 Processing BMK components...")
                process_all_bmk_pdfs()
            elif action == "merge":
                typer.echo("🔀 Merging knowledge modules...")
                run_merge()
            elif action == "index":
                typer.echo("📑 Building global indices...")
                run_global_indices()
            elif action == "export":
                typer.echo("💾 Exporting for embeddings...")
                run_export_embeddings()
            else:
                typer.echo(f"❌ Unknown action: {action}")
                raise typer.Exit(1)

            typer.echo("✅ Done!")
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            typer.echo(f"❌ Error: {e}", err=True)
            raise typer.Exit(1)

    @app.command()
    def server(
        host: str = typer.Option("127.0.0.1", help="Server host"),
        port: int = typer.Option(5002, help="Server port"),
        debug: bool = typer.Option(False, help="Enable debug mode"),
    ):
        """Start the Flask web server."""
        from webapp.app import main as run_app

        typer.echo(f"🌐 Starting server on {host}:{port}")

        import os

        os.environ["FLASK_HOST"] = host
        os.environ["FLASK_PORT"] = str(port)
        if debug:
            os.environ["FLASK_DEBUG"] = "1"

        try:
            run_app()
        except KeyboardInterrupt:
            typer.echo("\n⚠️  Server stopped.")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
            typer.echo(f"❌ Error: {e}", err=True)
            raise typer.Exit(1)

    def main():
        """Entry point for Typer CLI."""
        app()


# ============================================================
# FALLBACK: Interaktives Menü (falls Typer nicht verfügbar)
# ============================================================

else:
    from scripts.bmk_parser import process_all_bmk_pdfs
    from scripts.export_for_embeddings import main as run_export_embeddings
    from scripts.global_index_builder import main as run_global_indices
    from scripts.lec_parser import process_all_lec_pdfs
    from scripts.merge_knowledge import main as run_merge
    from scripts.run_pdfdoc_pipeline import main as run_full_pipeline
    from scripts.spl_parser import process_all_spl_pdfs
    from scripts.wissensmodul_builder import main as run_wissensmodule

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
