# Datei: scripts/build_local_embedding_index.py
"""
Baut den lokalen Embedding-Index für PDFDoc / Kran-Tools.

Pipeline:
1) knowledge_chunks.jsonl einlesen
   - jede Zeile: {"text": "...", weitere Felder ...}
2) Texte mit SentenceTransformer einbetten
3) Embeddings + Texte + Metadaten als Dateien ablegen:
   - output/embeddings/local_embeddings.npy
   - output/embeddings/embeddings_meta.json

Die Webapp nutzt anschließend:
  scripts.semantic_index.has_embedding_index
  scripts.semantic_index.search_similar
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from tqdm.auto import tqdm
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parents[1]  # .../kran-tools
EMB_DIR = BASE_DIR / "output" / "embeddings"
CHUNKS_PATH = EMB_DIR / "knowledge_chunks.jsonl"

INDEX_PATH = EMB_DIR / "local_embeddings.npy"
META_PATH = EMB_DIR / "embeddings_meta.json"


def _load_chunks() -> List[Dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        raise SystemExit(f"[EMB] ERROR: Chunks-Datei nicht gefunden: {CHUNKS_PATH}")

    chunks: List[Dict[str, Any]] = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                print(f"[EMB] WARN: Zeile {line_no} in {CHUNKS_PATH} konnte nicht gelesen werden: {e}")
                continue

            if not isinstance(obj, dict):
                continue

            # --- NEW ---
            src_meta = obj.get("metadata", {})
            if not isinstance(src_meta, dict):
                src_meta = {}
            dst_meta = dict(src_meta)
            obj["metadata"] = dst_meta

            text = obj.get("text") or obj.get("chunk") or ""
            if not text.strip():
                # leere Texte ignorieren
                continue

            obj["text"] = text.strip()
            chunks.append(obj)

    print(f"[EMB] Geladene Chunks aus {CHUNKS_PATH}: {len(chunks)}")
    return chunks


def build_index() -> None:
    EMB_DIR.mkdir(parents=True, exist_ok=True)

    print("=== BUILD LOCAL EMBEDDING INDEX (Kran-Tools) ===")
    print(f"Basisverzeichnis      : {BASE_DIR}")
    print(f"Embeddings-Verzeichnis: {EMB_DIR}")
    print(f"Chunks-Datei          : {CHUNKS_PATH}")

    chunks = _load_chunks()
    if not chunks:
        print("[EMB] WARN: Keine Chunks gefunden – Index wird nicht erstellt.")
        return

    texts: List[str] = [c["text"] for c in chunks]

    metadatas: List[Dict[str, Any]] = []
    for c in chunks:
        # --- NEW ---
        src_meta = c.get("metadata", {})
        if not isinstance(src_meta, dict):
            src_meta = {}
        dst_meta = dict(src_meta)

        # Modell sicherstellen
        if "model" not in dst_meta and "modell" in dst_meta:
            dst_meta["model"] = dst_meta.get("modell")

        # Source-Type heuristisch, falls nicht gesetzt
        st = (
            dst_meta.get("source_type")
            or c.get("source_type")
            or c.get("type")
            or c.get("origin")
            or ""
        ).lower()
        if not dst_meta.get("source_type"):
            if st in ("handbuch", "manual", "base_document", "page"):
                dst_meta["source_type"] = "base_document"
            elif st in ("lec", "lec_error", "error", "fehler"):
                dst_meta["source_type"] = "lec_error"
            elif st.startswith("bmk"):
                dst_meta["source_type"] = "bmk_component"
            elif st.startswith("spl"):
                dst_meta["source_type"] = "spl_reference"
            else:
                dst_meta["source_type"] = "UNKNOWN"

        meta_entry = {"id": c.get("id"), "metadata": dst_meta, "source_type": dst_meta.get("source_type")}
        metadatas.append(meta_entry)

    print(f"[EMB] Lade SentenceTransformer-Modell: sentence-transformers/all-MiniLM-L6-v2")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    print(f"[EMB] Erzeuge Embeddings für {len(texts)} Texte ...")
    # in Batches encoden, um RAM zu schonen
    batch_size = 512
    all_embeddings = []
    for start in tqdm(range(0, len(texts), batch_size), desc="Batches"):
        batch = texts[start:start + batch_size]
        emb = model.encode(batch, convert_to_numpy=True, show_progress_bar=False)
        all_embeddings.append(emb)

    embeddings = np.vstack(all_embeddings)
    print(f"[EMB] Embedding-Matrix: shape={embeddings.shape}")

    # Dateien schreiben
    np.save(INDEX_PATH, embeddings)
    with META_PATH.open("w", encoding="utf-8") as f:
        json.dump({"texts": texts, "metadatas": metadatas}, f, ensure_ascii=False)

    print(f"[EMB] Index gespeichert in: {INDEX_PATH}")
    print(f"[EMB] Metadaten gespeichert in: {META_PATH}")
    # --- NEW ---
    print("META layer counts:", Counter(m.get("metadata", {}).get("layer") for m in metadatas if isinstance(m, dict)))
    print("=== FERTIG ===")


def main() -> None:
    build_index()


if __name__ == "__main__":
    main()
