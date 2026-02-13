from __future__ import annotations

from typing import Any, Callable, Dict, List


def search_general(
    *,
    query: str,
    top_k: int,
    search_similar: Callable[..., List[Dict[str, Any]]] | None,
) -> List[Dict[str, Any]]:
    if search_similar is None:
        return []

    top_k = max(2, min(int(top_k or 3), 4))
    candidates_k = min(80, max(40, int(top_k) * 10))

    try:
        results = search_similar(query, top_k=candidates_k, model_filter="general", source_type_filter=None)
    except TypeError:
        results = search_similar(query, candidates_k)
    except Exception:
        return []

    filtered: List[Dict[str, Any]] = []
    for result in results or []:
        if not isinstance(result, dict):
            continue
        meta = result.get("metadata") or {}
        layer = None
        if isinstance(meta, dict):
            layer = meta.get("layer")
            nested = meta.get("metadata") if layer is None else None
            if isinstance(nested, dict):
                layer = nested.get("layer")
                if layer is not None:
                    result["metadata"] = nested
        if layer == "liccon_general":
            result_copy = dict(result)
            meta_copy = dict(meta)
            result_copy["model"] = "Frage / Antwort"
            source_type = result_copy.get("source_type") or meta_copy.get("source_type") or "Diagnose"
            if not source_type or source_type == "UNKNOWN":
                source_type = "Antwort"
            result_copy["source_type"] = source_type
            meta_copy["model"] = "Frage / Antwort"
            if not meta_copy.get("source_type") or meta_copy.get("source_type") == "UNKNOWN":
                meta_copy["source_type"] = "antwort"
            result_copy["metadata"] = meta_copy
            filtered.append(result_copy)
    return filtered[:top_k]
