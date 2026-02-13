from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


@lru_cache(maxsize=1)
def load_embeddings_meta_data(*, base_dir: str) -> Any:
    path = Path(base_dir) / "output" / "embeddings" / "embeddings_meta.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def chunk_from_meta_entry(entry: Dict[str, Any], text: str) -> Optional[Dict[str, Any]]:
    if not isinstance(entry, dict):
        return None
    raw_meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else entry
    meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    chunk_id = entry.get("id") or meta.get("id") or meta.get("_id")

    chunk = dict(meta)
    if chunk_id is not None:
        chunk["id"] = chunk_id
    if text and not chunk.get("text"):
        chunk["text"] = text
    if entry.get("source_type") and not chunk.get("source_type"):
        chunk["source_type"] = entry.get("source_type")
    return chunk


def find_chunk_by_id(*, base_dir: str, chunk_id: str) -> Optional[Dict[str, Any]]:
    if not chunk_id:
        return None

    data = load_embeddings_meta_data(base_dir=base_dir)
    if not data:
        return None

    def _matches(value: Any) -> bool:
        return value is not None and str(value) == str(chunk_id)

    if isinstance(data, dict) and "texts" in data:
        texts = data.get("texts") or []
        metas = data.get("metadatas") or data.get("metas") or []
        if not isinstance(metas, list):
            return None
        for index, entry in enumerate(metas):
            text = texts[index] if index < len(texts) else ""
            chunk = chunk_from_meta_entry(entry, text)
            if chunk and _matches(chunk.get("id")):
                return chunk
        return None

    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text") or entry.get("chunk") or ""
            chunk = chunk_from_meta_entry(entry, text)
            if chunk and _matches(chunk.get("id")):
                return chunk
    return None
