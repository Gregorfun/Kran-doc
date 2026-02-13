"""
Validate PDFDoc System Script
==============================

Validiert das PDFDoc-System nach Reset und Rebuild:

1. Prüft ob Server auf Port 5002 startet
2. Prüft ob Embeddings-Index existiert
3. Prüft ob Health-Endpoint erreichbar ist
4. Führt eine Test-Suche durch

Verwendung:
  python scripts/validate_system.py
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))


def check_port_available(port: int, timeout: float = 2.0) -> bool:
    """Prüft ob ein Port erreichbar ist."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex(("127.0.0.1", port))
        return result == 0
    except Exception:
        return False
    finally:
        sock.close()


def check_embeddings_index() -> tuple[bool, Optional[str]]:
    """Prüft ob Embeddings-Index existiert."""
    emb_dir = BASE_DIR / "output" / "embeddings"

    chunks_file = emb_dir / "knowledge_chunks.jsonl"
    index_file = emb_dir / "local_embeddings.npy"
    meta_file = emb_dir / "embeddings_meta.json"

    missing = []

    if not chunks_file.exists():
        missing.append(str(chunks_file.relative_to(BASE_DIR)))

    if not index_file.exists():
        missing.append(str(index_file.relative_to(BASE_DIR)))

    if not meta_file.exists():
        missing.append(str(meta_file.relative_to(BASE_DIR)))

    if missing:
        return False, f"Fehlende Dateien: {', '.join(missing)}"

    return True, None


def check_health_endpoint(port: int = 5002, timeout: float = 5.0) -> tuple[bool, Optional[str]]:
    """Prüft Health-Endpoint."""
    try:
        import requests

        url = f"http://127.0.0.1:{port}/health"
        response = requests.get(url, timeout=timeout)

        if response.status_code == 200:
            return True, None
        else:
            return False, f"Status Code: {response.status_code}"

    except ImportError:
        # requests nicht installiert - Port-Check als Fallback
        if check_port_available(port):
            return True, "requests-Modul fehlt, nur Port-Check"
        else:
            return False, "Server nicht erreichbar"

    except Exception as e:
        return False, str(e)


def test_semantic_search() -> tuple[bool, Optional[str]]:
    """Führt Test-Suche durch."""
    try:
        from scripts.semantic_index import has_embedding_index, search_similar

        if not has_embedding_index():
            return False, "Embedding-Index nicht gefunden"

        # Einfache Test-Suche
        results = search_similar("test", top_k=1)

        if results:
            return True, f"{len(results)} Ergebnis(se) gefunden"
        else:
            return True, "0 Ergebnisse (Index leer oder keine Matches)"

    except Exception as e:
        return False, str(e)


def main() -> None:
    print("=" * 70)
    print("PDFDOC SYSTEM VALIDATION")
    print("=" * 70)
    print()

    PORT = 5002
    all_passed = True

    # Check 1: Embeddings-Index
    print("[1/4] Embeddings-Index prüfen...")
    success, error = check_embeddings_index()
    if success:
        print("  ✅ Embeddings-Index existiert")
    else:
        print(f"  ❌ Embeddings-Index fehlt: {error}")
        all_passed = False
    print()

    # Check 2: Port verfügbar
    print(f"[2/4] Server-Port {PORT} prüfen...")

    # Hinweis wenn Server nicht läuft
    if not check_port_available(PORT):
        print(f"  ℹ️  Server läuft nicht auf Port {PORT}")
        print(f"      Starte mit: python webapp/app.py")
        print()

        # Versuche Server zu starten
        print("  ⚙️  Versuche Server zu starten...")
        import subprocess

        try:
            proc = subprocess.Popen(
                [sys.executable, str(BASE_DIR / "webapp" / "app.py")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(BASE_DIR),
            )

            # Warte auf Server-Start
            max_wait = 15
            for i in range(max_wait):
                time.sleep(1)
                if check_port_available(PORT):
                    print(f"  ✅ Server gestartet auf Port {PORT}")
                    break
                if i == max_wait - 1:
                    print(f"  ❌ Server-Start Timeout nach {max_wait}s")
                    proc.terminate()
                    all_passed = False
        except Exception as e:
            print(f"  ❌ Server-Start fehlgeschlagen: {e}")
            all_passed = False
    else:
        print(f"  ✅ Server läuft auf Port {PORT}")

    print()

    # Check 3: Health-Endpoint
    print("[3/4] Health-Endpoint prüfen...")
    success, error = check_health_endpoint(PORT)
    if success:
        print(f"  ✅ Health-Endpoint erreichbar")
        if error:
            print(f"      ({error})")
    else:
        print(f"  ❌ Health-Endpoint nicht erreichbar: {error}")
        all_passed = False
    print()

    # Check 4: Semantische Suche
    print("[4/4] Semantische Suche testen...")
    success, error = test_semantic_search()
    if success:
        print(f"  ✅ Semantische Suche funktioniert")
        if error:
            print(f"      ({error})")
    else:
        print(f"  ❌ Semantische Suche fehlgeschlagen: {error}")
        all_passed = False
    print()

    # Zusammenfassung
    print("=" * 70)
    if all_passed:
        print("✅ ALLE CHECKS BESTANDEN")
        print()
        print(f"System bereit auf: http://127.0.0.1:{PORT}")
    else:
        print("❌ EINIGE CHECKS FEHLGESCHLAGEN")
        print()
        print("Führe aus:")
        print("  1. python scripts/reset_knowledge_artifacts.py")
        print("  2. python scripts/rebuild_knowledge_pipeline.py")
        print("  3. python webapp/app.py")

    print("=" * 70)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Abgebrochen durch Benutzer")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ FEHLER: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
