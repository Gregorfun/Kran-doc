"""
Lokaler Embedding-Index + Suchfunktion für PDFDoc / Kran-Tools.

- has_embedding_index(): prüft Index-Dateien
- search_similar(): semantische Suche mit optionalen Filtern (model/source_type)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
EMB_DIR = BASE_DIR / "output" / "embeddings"

INDEX_PATH = EMB_DIR / "local_embeddings.npy"
META_PATH = EMB_DIR / "embeddings_meta.json"


def has_embedding_index() -> bool:
    return INDEX_PATH.exists() and META_PATH.exists()


@lru_cache(maxsize=1)
def _load_model():
    """Lazy-load SentenceTransformer to keep webapp startup fast.

    Importing sentence_transformers pulls in torch/transformers which can be slow
    (especially on Windows). We only load the model when semantic search is used.
    """

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "sentence-transformers ist nicht installiert/ladbar. " "Installiere es oder deaktiviere Semantic Search."
        ) from exc

    import os

    model_name = os.environ.get("KRANDOC_EMBEDDING_MODEL") or "sentence-transformers/all-MiniLM-L6-v2"
    return SentenceTransformer(model_name)


@lru_cache(maxsize=1)
def _load_index() -> Tuple[np.ndarray, List[str], List[Dict[str, Any]]]:
    if not has_embedding_index():
        raise RuntimeError("Embedding-Index nicht gefunden. Bitte zuerst build_local_embedding_index.py ausführen.")

    embeddings = np.load(INDEX_PATH)

    with META_PATH.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    if isinstance(meta, dict) and "texts" in meta:
        texts = meta.get("texts", [])
        metas_raw = meta.get("metadatas", meta.get("metas", []))
        if isinstance(metas_raw, list):
            for entry in metas_raw:
                if isinstance(entry, dict) and isinstance(entry.get("metadata"), dict):
                    inner = dict(entry.get("metadata") or {})
                    if entry.get("id") is not None and "_id" not in inner:
                        inner["_id"] = entry.get("id")
                    if entry.get("source_type") is not None and "source_type" not in inner:
                        inner["source_type"] = entry.get("source_type")
                    metadatas.append(inner)
                elif isinstance(entry, dict):
                    metadatas.append(entry)
                else:
                    metadatas.append({})
    elif isinstance(meta, list):
        for entry in meta:
            if isinstance(entry, dict):
                texts.append(entry.get("text") or entry.get("chunk") or "")
                tmp = dict(entry)
                tmp.pop("text", None)
                metadatas.append(tmp)
            else:
                texts.append("")
                metadatas.append({})

    if len(texts) != embeddings.shape[0] or len(metadatas) != embeddings.shape[0]:
        raise RuntimeError(
            f"Embedding-Index inkonsistent: {embeddings.shape[0]} Vektoren, "
            f"{len(texts)} Texte, {len(metadatas)} Metadaten."
        )

    return embeddings, texts, metadatas


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-12)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-12)
    return a_norm @ b_norm.T


def _normalize_source_type(source_type: str) -> str:
    st = (source_type or "").lower().strip()
    if st in ("handbuch", "manual", "base_document", "page"):
        return "base_document"
    if st in ("lec", "lec_error", "error", "fehler"):
        return "lec_error"
    if st.startswith("bmk"):
        return "bmk_component"
    if st.startswith("spl"):
        return "spl_reference"
    return source_type or "UNKNOWN"


def search_similar(
    query: str,
    top_k: int = 5,
    model_filter: Optional[str] = None,
    source_type_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Rückgabe:
    {
      "model": "<MODEL>",
      "source_type": "<QUELLE>",
      "metadata": {...},
      "text": "<chunk>",
      "score": float
    }
    """
    if not query:
        return []

    embeddings, texts, metadatas = _load_index()
    model = _load_model()

    query_vec = model.encode([query], convert_to_numpy=True)
    sims = _cosine_sim(embeddings, query_vec)[:, 0]

    # erstmal mehr holen, dann filtern (damit Filter nicht alles leer macht)
    pre_k = min(max(top_k * 15, top_k), len(texts))
    top_idx = np.argpartition(-sims, pre_k - 1)[:pre_k]
    top_idx = top_idx[np.argsort(-sims[top_idx])]

    source_type_filter_norm = (source_type_filter or "").strip()
    if source_type_filter_norm.lower() in ("alle", "all", "*", ""):
        source_type_filter_norm = None
    if source_type_filter_norm:
        source_type_filter_norm = _normalize_source_type(source_type_filter_norm)

    results: List[Dict[str, Any]] = []
    for idx in top_idx:
        meta = dict(metadatas[idx] or {})
        text = texts[idx]

        mname = meta.get("model") or meta.get("modell") or "UNKNOWN"
        stype = meta.get("source_type") or meta.get("type") or meta.get("source") or "UNKNOWN"
        stype = _normalize_source_type(str(stype))

        if model_filter and mname != model_filter:
            continue
        if source_type_filter_norm and stype != source_type_filter_norm:
            continue

        results.append(
            {
                "model": mname,
                "source_type": stype,
                "metadata": meta,
                "text": text,
                "score": float(sims[idx]),
            }
        )

        if len(results) >= top_k:
            break

    return results


def warmup_semantic(load_index: Optional[bool] = None) -> Dict[str, Any]:
    """Warm up semantic search components.

    - Loads the embedding model (may trigger heavy imports: torch/transformers).
    - Optionally loads the local embedding index.

    Args:
        load_index: If True, try to load the local index. If False, skip.
            If None (default), load index only if it exists.

    Returns:
        A dict with status flags (safe to print/log).
    """

    info: Dict[str, Any] = {
        "model_loaded": False,
        "has_index": bool(has_embedding_index()),
        "index_loaded": False,
    }

    # model warmup
    _load_model()
    info["model_loaded"] = True

    # index warmup (optional)
    should_load_index = info["has_index"] if load_index is None else bool(load_index)
    if should_load_index:
        try:
            _load_index()
            info["index_loaded"] = True
        except Exception as exc:
            info["index_loaded"] = False
            info["index_error"] = str(exc)

    return info
