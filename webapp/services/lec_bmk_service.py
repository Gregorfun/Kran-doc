from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

_AUTO_BMK_CODE_RE = re.compile(r"\b([SAYE]\d{2,4})\b", re.IGNORECASE)
_BMK_FROM_RELATED_RE = re.compile(r"\bbmk_([^_]+)_([A-Z]\d{2,4})\b", re.IGNORECASE)


def extract_bmk_hits_from_related_chunks(related_chunks: List[str]) -> List[Dict[str, str]]:
    hits: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in related_chunks or []:
        if not item:
            continue
        text = str(item)
        for match in _BMK_FROM_RELATED_RE.finditer(text):
            code = match.group(2).upper()
            if code in seen:
                continue
            seen.add(code)
            hits.append({"code": code, "model": (match.group(1) or "").strip()})
    return hits


def extract_bmk_codes_from_text(text: str) -> List[str]:
    if not text:
        return []
    codes: List[str] = []
    seen: set[str] = set()
    for match in _AUTO_BMK_CODE_RE.finditer(text):
        code = match.group(1).upper()
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
    return codes


def format_auto_bmk_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "model": entry.get("model"),
        "bmk": entry.get("bmk"),
        "title": entry.get("title"),
        "area": entry.get("area"),
        "group": entry.get("group"),
    }


def collect_auto_bmks_for_result(
    *,
    result: Dict[str, Any],
    model_hint: Optional[str],
    normalize_model: Callable[[str], str],
    first_value: Callable[[Dict[str, Any], Dict[str, Any], List[str]], Optional[Any]],
    normalize_list_field: Callable[[Any], List[str]],
    get_bmk_entry: Callable[[str, str], Optional[Dict[str, Any]]],
    max_entries: int = 5,
) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        return []

    meta = result.get("metadata") or {}
    source_type = (result.get("source_type") or meta.get("source_type") or "").lower().strip()
    if source_type != "lec_error":
        return []

    model = normalize_model(result.get("model") or meta.get("model") or (model_hint or ""))
    if not model or model.lower() in ("all", "alle", "*"):
        return []

    related_raw = first_value(result, meta, ["related_chunks", "related"])
    related_chunks = normalize_list_field(related_raw)
    related_hits = extract_bmk_hits_from_related_chunks(related_chunks) if related_chunks else []

    codes: List[str] = []
    if related_hits:
        for hit in related_hits:
            codes.append(hit["code"])
    else:
        text_parts = [
            result.get("text"),
            meta.get("text"),
            meta.get("short_text"),
            meta.get("long_text"),
            result.get("short_description"),
            meta.get("short_description"),
            result.get("title"),
            meta.get("title"),
        ]
        text = " ".join([str(value) for value in text_parts if value])
        codes = extract_bmk_codes_from_text(text)

    if not codes:
        return []

    entries: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for code in codes:
        code_key = code.upper()
        if code_key in seen:
            continue
        seen.add(code_key)
        entry = get_bmk_entry(model, code_key)
        if entry:
            entries.append(format_auto_bmk_entry(entry))
        if len(entries) >= max_entries:
            break

    return entries


def attach_auto_bmks(
    *,
    results: List[Dict[str, Any]],
    model_hint: Optional[str],
    normalize_model: Callable[[str], str],
    first_value: Callable[[Dict[str, Any], Dict[str, Any], List[str]], Optional[Any]],
    normalize_list_field: Callable[[Any], List[str]],
    get_bmk_entry: Callable[[str, str], Optional[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not results:
        return results
    for result in results:
        if not isinstance(result, dict):
            continue
        auto_bmks = collect_auto_bmks_for_result(
            result=result,
            model_hint=model_hint,
            normalize_model=normalize_model,
            first_value=first_value,
            normalize_list_field=normalize_list_field,
            get_bmk_entry=get_bmk_entry,
        )
        if auto_bmks:
            result["auto_bmks"] = auto_bmks
            meta = result.get("metadata")
            if isinstance(meta, dict):
                meta["auto_bmks"] = auto_bmks
                result["metadata"] = meta
    return results


def attach_solution_counts(
    *,
    results: List[Dict[str, Any]],
    count_solutions: Callable[[str, str], int],
) -> List[Dict[str, Any]]:
    if not results:
        return results
    for result in results:
        if not isinstance(result, dict):
            continue
        meta = result.get("metadata") or {}
        source_type = (result.get("source_type") or meta.get("source_type") or "").lower().strip()
        if source_type != "lec_error":
            continue
        model = result.get("model") or meta.get("model") or ""
        code = meta.get("error_code") or meta.get("code") or ""
        if not code:
            continue
        count = count_solutions(model, str(code))
        result["solution_count"] = count
        if isinstance(meta, dict):
            meta["solution_count"] = count
            result["metadata"] = meta
    return results


def attach_lec_display_text(
    *,
    results: List[Dict[str, Any]],
    model_hint: Optional[str],
    normalize_model: Callable[[str], str],
    load_lec_index_for_model: Callable[[str], Dict[str, Dict[str, Any]]],
    first_non_empty_str: Callable[..., str],
) -> List[Dict[str, Any]]:
    if not results:
        return results
    for result in results:
        if not isinstance(result, dict):
            continue
        meta = result.get("metadata") or {}
        source_type = (result.get("source_type") or meta.get("source_type") or "").lower().strip()
        if source_type != "lec_error":
            continue
        model = normalize_model(result.get("model") or meta.get("model") or (model_hint or ""))
        if not model:
            continue
        code = meta.get("error_code") or meta.get("code") or result.get("error_code") or result.get("code")
        if not code:
            continue
        error_entry = load_lec_index_for_model(model).get(str(code).upper())
        if not error_entry:
            continue

        short_display = first_non_empty_str(
            error_entry.get("short_text"),
            error_entry.get("summary"),
            error_entry.get("title"),
            error_entry.get("short_description"),
        )
        long_display = first_non_empty_str(
            error_entry.get("long_text"),
            error_entry.get("description"),
            error_entry.get("reaction"),
            error_entry.get("remedy"),
        )
        if short_display:
            meta.setdefault("short_text_display", short_display)
        if long_display:
            meta.setdefault("long_text_display", long_display)
        result["metadata"] = meta
    return results


def direct_lec_results_for_codes(
    *,
    codes: List[str],
    model_hint: Optional[str],
    top_k: int,
    load_lec_index_for_model: Callable[[str], Dict[str, Dict[str, Any]]],
    full_lsb_address: Callable[[Dict[str, Any]], Optional[str]],
) -> List[Dict[str, Any]]:
    if not model_hint:
        return []

    lec_index = load_lec_index_for_model(model_hint)
    out: List[Dict[str, Any]] = []

    for code in codes:
        err = lec_index.get(str(code).upper())
        if not err:
            continue
        lsb_address = full_lsb_address(err) or err.get("lsb_address") or err.get("lsb")
        out.append(
            {
                "model": model_hint,
                "source_type": "lec_error",
                "title": f"LEC Fehler {code}",
                "text": err.get("short_text") or "",
                "score": 1.0,
                "metadata": {
                    "model": model_hint,
                    "source_type": "lec_error",
                    "error_code": str(code).upper(),
                    "code": str(code).upper(),
                    "short_text": err.get("short_text"),
                    "long_text": err.get("long_text"),
                    "lsb_address": lsb_address,
                },
            }
        )

    return out[:top_k]


def enrich_results_with_bmk(
    *,
    results: List[Dict[str, Any]],
    model_hint: Optional[str],
    load_lec_index_for_model: Callable[[str], Dict[str, Dict[str, Any]]],
    full_lsb_address: Callable[[Dict[str, Any]], Optional[str]],
    extract_lsb_key_from_error_data: Callable[[Dict[str, Any]], Optional[str]],
    build_bmk_index_for_model: Callable[[str], Dict[str, List[Dict[str, Any]]]],
) -> List[Dict[str, Any]]:
    if not results:
        return results

    for result in results:
        meta = result.get("metadata") or {}
        result["metadata"] = meta

        source_type = result.get("source_type") or meta.get("source_type") or result.get("source") or meta.get("source")
        if source_type not in ("lec_error",):
            continue

        model = result.get("model") or meta.get("model") or model_hint
        code = meta.get("error_code") or meta.get("code")
        if not model or not code:
            continue

        lec_index = load_lec_index_for_model(model)
        err = lec_index.get(str(code).upper())
        if not err:
            continue

        meta.setdefault("short_text", err.get("short_text"))
        meta.setdefault("long_text", err.get("long_text"))
        meta.setdefault("lsb_address", err.get("lsb_address") or err.get("lsb"))

        full_lsb = full_lsb_address(err)
        if full_lsb:
            current_lsb = meta.get("lsb_address")
            if not current_lsb or (full_lsb.startswith(str(current_lsb)) and len(str(current_lsb)) < len(full_lsb)):
                meta["lsb_address"] = full_lsb

        lsb_key = extract_lsb_key_from_error_data(err)
        if not lsb_key:
            continue
        meta["lsb_error_key"] = lsb_key

        bmk_index = build_bmk_index_for_model(model)
        candidates = bmk_index.get(lsb_key) or []
        if not candidates:
            continue

        best = candidates[0]

        meta["sensor_bmk"] = best.get("sensor_bmk")
        meta["sensor_title"] = best.get("sensor_title")
        meta["sensor_description"] = best.get("sensor_description")
        meta["sensor_location"] = best.get("sensor_location")
        meta["bmk_candidate_count"] = len(candidates)

        bmk_code = best.get("sensor_bmk") or ""
        title = best.get("sensor_title") or ""
        desc = best.get("sensor_description") or ""

        parts: List[str] = []
        if bmk_code:
            parts.append(f"BMK {bmk_code}")
        if title:
            parts.append(title)
        display = " – ".join(parts).strip()

        if desc and desc.lower() not in (title.lower(), display.lower()):
            display = (display + f" — {desc}").strip()

        meta["sensor_name"] = display or title or desc or None

    return results
