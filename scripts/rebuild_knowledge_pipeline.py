"""
Rebuild Knowledge Pipeline Script
===================================

Führt den vollständigen Rebuild der Wissensartefakte aus:

1. Reset: Löscht alte Chunks, Embeddings, Indizes
2. Export: Erzeugt neue Chunks aus FULL_KNOWLEDGE.json
3. Build Index: Erzeugt Embeddings und semantischen Index
4. Validierung: Prüft dass alles erfolgreich erstellt wurde

Nach strukturellen Änderungen am Projekt ausführen, um sicherzustellen,
dass keine veralteten Artefakte oder Referenzen zurückbleiben.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))


def main() -> None:
    print("=" * 70)
    print("REBUILD KNOWLEDGE PIPELINE")
    print("=" * 70)
    print()

    # Schritt 1: Reset
    print("[1/3] Reset: Lösche alte Artefakte...")
    print("-" * 70)
    try:
        from scripts.reset_knowledge_artifacts import reset_artifacts

        reset_artifacts()
        print()
    except Exception as e:
        print(f"❌ FEHLER beim Reset: {e}")
        raise SystemExit(1)

    # Schritt 2: Export Chunks
    print()
    print("[2/3] Export: Erzeuge neue Chunks...")
    print("-" * 70)
    try:
        from scripts.export_for_embeddings import export

        export()
        print()
    except Exception as e:
        print(f"❌ FEHLER beim Chunk-Export: {e}")
        print("Stelle sicher, dass FULL_KNOWLEDGE.json-Dateien existieren.")
        raise SystemExit(1)

    # Schritt 3: Build Index
    print()
    print("[3/3] Build Index: Erzeuge Embeddings und Index...")
    print("-" * 70)
    try:
        from scripts.build_local_embedding_index import build_index

        build_index()
        print()
    except Exception as e:
        print(f"❌ FEHLER beim Index-Build: {e}")
        raise SystemExit(1)

    # Validierung
    print()
    print("=" * 70)
    print("VALIDIERUNG")
    print("=" * 70)

    emb_dir = BASE_DIR / "output" / "embeddings"
    chunks_file = emb_dir / "knowledge_chunks.jsonl"
    index_file = emb_dir / "local_embeddings.npy"
    meta_file = emb_dir / "embeddings_meta.json"

    errors = []

    if not chunks_file.exists():
        errors.append(f"✗ Chunks-Datei fehlt: {chunks_file}")
    else:
        print(f"✔ Chunks-Datei: {chunks_file}")

    if not index_file.exists():
        errors.append(f"✗ Index-Datei fehlt: {index_file}")
    else:
        print(f"✔ Index-Datei: {index_file}")

    if not meta_file.exists():
        errors.append(f"✗ Metadaten-Datei fehlt: {meta_file}")
    else:
        print(f"✔ Metadaten-Datei: {meta_file}")

    print()

    if errors:
        print("❌ VALIDIERUNG FEHLGESCHLAGEN:")
        for err in errors:
            print(f"  {err}")
        raise SystemExit(1)

    print("=" * 70)
    print("✅ REBUILD ERFOLGREICH ABGESCHLOSSEN")
    print("=" * 70)
    print()
    print("Alle Wissensartefakte wurden neu erzeugt:")
    print(f"  • Chunks: {chunks_file}")
    print(f"  • Embeddings: {index_file}")
    print(f"  • Metadaten: {meta_file}")
    print()
    print("Das System ist bereit für Suchanfragen.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Abgebrochen durch Benutzer")
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n\n❌ UNERWARTETER FEHLER: {e}")
        import traceback

        traceback.print_exc()
        raise SystemExit(1)
