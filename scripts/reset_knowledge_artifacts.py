"""
Reset Knowledge Artifacts Script
==================================

Löscht alle automatisch erzeugten Wissensartefakte (Chunks, Embeddings, Indizes),
OHNE die Parser-Outputs (LEC, BMK, SPL, Manuals) zu entfernen.

Dies ist notwendig nach strukturellen Projektänderungen, um eine vollständige
Neugenerierung sicherzustellen.

Artefakte die gelöscht werden:
- output/embeddings/*.jsonl (Chunk-Dateien)
- output/embeddings/*.npy (Embedding-Vektoren)
- output/embeddings/*.json (Metadaten, Versionen)
- Temporäre Cache-Ordner

Artefakte die NICHT gelöscht werden:
- Parser-Outputs in output/models/ (LEC, BMK, SPL, FULL_KNOWLEDGE.json)
- Logs
- Input-Dateien
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

BASE_DIR = Path(__file__).resolve().parents[1]
EMBEDDINGS_DIR = BASE_DIR / "output" / "embeddings"


def reset_artifacts() -> None:
    """Löscht alle Chunks, Embeddings und Indizes."""

    print("=" * 70)
    print("RESET KNOWLEDGE ARTIFACTS")
    print("=" * 70)
    print()
    print(f"Projektpfad: {BASE_DIR}")
    print(f"Embeddings-Dir: {EMBEDDINGS_DIR}")
    print()

    if not EMBEDDINGS_DIR.exists():
        print("⚠ Embeddings-Verzeichnis existiert nicht. Nichts zu löschen.")
        return

    # Dateien die gelöscht werden sollen
    patterns_to_delete = [
        "*.jsonl",  # Chunk-Dateien
        "*.npy",  # Numpy-Arrays (Embeddings)
        "*_meta.json",  # Metadaten
        "*_version.json",  # Versionsinformationen
        "*.bak",  # Backup-Dateien
    ]

    deleted_files: List[Path] = []

    for pattern in patterns_to_delete:
        for file_path in EMBEDDINGS_DIR.glob(pattern):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    deleted_files.append(file_path)
                    print(f"✔ Gelöscht: {file_path.name}")
                except Exception as e:
                    print(f"✗ Fehler beim Löschen von {file_path.name}: {e}")

    # Temporäre Cache-Ordner (falls vorhanden)
    cache_dirs = [
        EMBEDDINGS_DIR / "__pycache__",
        BASE_DIR / ".cache",
    ]

    for cache_dir in cache_dirs:
        if cache_dir.exists() and cache_dir.is_dir():
            try:
                shutil.rmtree(cache_dir)
                deleted_files.append(cache_dir)
                print(f"✔ Gelöscht: {cache_dir.relative_to(BASE_DIR)}/")
            except Exception as e:
                print(f"✗ Fehler beim Löschen von {cache_dir}: {e}")

    print()
    print("=" * 70)

    if deleted_files:
        print(f"✅ Reset erfolgreich: {len(deleted_files)} Artefakte gelöscht")
        print()
        print("WICHTIG: Führe jetzt aus:")
        print("  1) python scripts/export_for_embeddings.py")
        print("  2) python scripts/build_local_embedding_index.py")
    else:
        print("ℹ Keine Artefakte gefunden zum Löschen")

    print("=" * 70)


def main() -> None:
    try:
        reset_artifacts()
    except KeyboardInterrupt:
        print("\n\n⚠ Abgebrochen durch Benutzer")
        raise SystemExit(1)
    except Exception as e:
        print(f"\n\n❌ FEHLER: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
