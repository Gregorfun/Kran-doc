from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional


def safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def result_dedupe_key(result: Dict[str, Any]) -> str:
    meta = result.get("metadata") or {}
    meta_id = meta.get("id")
    if meta_id:
        return f"id:{meta_id}"
    title = safe_str(meta.get("title") or result.get("title") or "")
    text = safe_str(result.get("text") or result.get("chunk") or "")
    payload = (title + "\n" + text).strip()
    return "hash:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()


def dedupe_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    output: List[Dict[str, Any]] = []
    for result in results or []:
        if not isinstance(result, dict):
            continue
        key = result_dedupe_key(result)
        if key in seen:
            continue
        seen.add(key)
        output.append(result)
    return output


def normalize_list_field(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[\n;]+", value) if part.strip()]
        if len(parts) == 1 and "," in value:
            parts = [part.strip() for part in value.split(",") if part.strip()]
        return parts
    return [str(value).strip()] if str(value).strip() else []


def first_value(result: Dict[str, Any], meta: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for key in keys:
        value = result.get(key)
        if value is not None and value != "":
            return value
        value = meta.get(key)
        if value is not None and value != "":
            return value
    return None


def normalize_chunk_result(result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result

    meta = result.get("metadata")
    if not isinstance(meta, dict):
        meta = {}
    result["metadata"] = meta

    id_value = first_value(result, meta, ["id", "_id"])
    if id_value is not None:
        result.setdefault("id", id_value)
        meta.setdefault("id", id_value)

    fields = {
        "type": ["type"],
        "model": ["model", "modell"],
        "title": ["title"],
        "short_description": ["short_description", "short_desc", "short_text"],
        "question": ["question"],
        "answer": ["answer"],
        "confidence": ["confidence"],
        "tags": ["tags"],
        "source": ["source"],
        "text": ["text", "chunk"],
    }
    for field, keys in fields.items():
        value = first_value(result, meta, keys)
        if value is not None and value != "":
            result.setdefault(field, value)
            meta.setdefault(field, value)

    list_fields = {
        "related_chunks": ["related_chunks", "related"],
        "symptoms": ["symptoms"],
        "likely_causes": ["likely_causes", "causes"],
        "checks": ["checks"],
    }
    for field, keys in list_fields.items():
        value = first_value(result, meta, keys)
        items = normalize_list_field(value)
        if items:
            result.setdefault(field, items)
            meta.setdefault(field, items)

    return result


def normalize_chunk_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not results:
        return results
    for result in results:
        if isinstance(result, dict):
            normalize_chunk_result(result)
    return results


def first_non_empty_str(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
