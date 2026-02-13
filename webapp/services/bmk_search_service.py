from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def parse_bmk_search_request(data: Dict[str, Any]) -> Dict[str, Any]:
    query = (data.get("query") or "").strip()
    model = data.get("model") or None
    return {
        "query": query,
        "model": model,
    }


def validate_bmk_search_request(*, query: str, model: Optional[str]) -> Optional[str]:
    if not query:
        return "Bitte BMK-Code oder Begriff eingeben."
    if not model:
        return "Bitte ein Modell auswählen"
    return None


def bmk_search_in_model(
    *,
    model: str,
    query: str,
    build_bmk_index_for_model: Callable[[str], Dict[str, List[Dict[str, Any]]]],
    collect_bmk_components_for_model: Callable[[str], List[Dict[str, Any]]],
    looks_like_lsb_query: Callable[[str], Optional[str]],
    looks_like_bmk_code_query: Callable[[str], bool],
    is_probably_non_german: Callable[[str], bool],
    is_valid_bmk_code: Callable[[str], bool],
    clean_text_field: Callable[[Any], str],
    clean_description: Callable[[Any], str],
    limit: int = 1,
) -> List[Dict[str, Any]]:
    limit = 1
    query = (query or "").strip()
    if not query:
        return []

    query_upper = query.upper()
    results: List[Dict[str, Any]] = []

    lsb_key = looks_like_lsb_query(query)
    if lsb_key:
        index = build_bmk_index_for_model(model)
        hits = index.get(lsb_key, [])
        if not hits:
            return []
        hit = hits[0]

        bmk_code = hit.get("sensor_bmk") or ""
        title = hit.get("sensor_title") or ""
        desc = hit.get("sensor_description") or ""
        display = " – ".join([part for part in [bmk_code, title] if part]).strip()
        if desc and desc.lower() not in (title.lower(), display.lower()):
            display = (display + f" — {desc}").strip()

        meta = {
            "model": model,
            "source_type": "bmk_component",
            "bmk": bmk_code or None,
            "lsb_bmk_address": hit.get("lsb_bmk_address"),
            "title": title or None,
            "description": desc or None,
            "description_clean": desc or None,
            "sensor_name": display or None,
            "sensor_location": hit.get("sensor_location"),
            "lsb_key": lsb_key,
            "raw": hit.get("_raw_component"),
        }
        return [
            {
                "model": model,
                "source_type": "bmk_component",
                "title": display or (bmk_code or "BMK"),
                "text": desc or title or "",
                "score": 0.95,
                "metadata": meta,
            }
        ][:limit]

    components = collect_bmk_components_for_model(model)
    code_query_mode = looks_like_bmk_code_query(query_upper)

    for component in components:
        raw_title = component.get("title") or component.get("name") or ""
        raw_desc = component.get("description") or ""

        lang = (component.get("lang") or "").strip().lower()
        if lang and lang != "de":
            continue
        if is_probably_non_german(str(raw_title) + " " + str(raw_desc)):
            continue

        raw_bmk = component.get("bmk") or component.get("code") or component.get("bmk_code") or ""
        bmk_code = str(raw_bmk).strip()
        if bmk_code and not is_valid_bmk_code(bmk_code):
            bmk_code = ""

        title = clean_text_field(raw_title) or clean_text_field(raw_desc)
        desc_clean = clean_description(raw_desc)

        area = clean_text_field(component.get("area") or "")
        group = clean_text_field(component.get("group") or "")
        wagon = clean_text_field(component.get("wagon") or component.get("_wagon") or "")

        score = 0.0
        if code_query_mode:
            if bmk_code and query_upper == bmk_code.upper():
                score = 1.0
            else:
                continue
        else:
            haystack = f"{bmk_code} {title} {desc_clean} {area} {group}".upper()
            if bmk_code and query_upper == bmk_code.upper():
                score = 1.0
            elif query_upper in haystack:
                score = 0.65

        if score <= 0:
            continue

        display = " – ".join([part for part in [bmk_code, title] if part]).strip()
        if desc_clean and desc_clean.lower() not in (title.lower(), display.lower()):
            display = (display + f" — {desc_clean}").strip()

        raw_lsb = component.get("lsb_address") or component.get("lsb") or component.get("lsb_key")

        meta = {
            "model": model,
            "source_type": "bmk_component",
            "bmk": bmk_code or None,
            "lsb_bmk_address": str(raw_lsb).strip() if raw_lsb else None,
            "title": title or None,
            "description": component.get("description") or None,
            "description_clean": desc_clean or None,
            "sensor_name": display or None,
            "sensor_location": (area + (" / " + group if group else "")).strip() or None,
            "wagon": wagon or None,
            "raw": component,
        }

        results.append(
            {
                "model": model,
                "source_type": "bmk_component",
                "title": display or title or bmk_code or "BMK",
                "text": desc_clean or title or "",
                "score": score,
                "metadata": meta,
            }
        )

    if not results:
        return []

    results_sorted = sorted(results, key=lambda item: float(item.get("score") or 0.0), reverse=True)
    seen = set()
    for result in results_sorted:
        meta = result.get("metadata") or {}
        key = (
            result.get("model"),
            (meta.get("bmk") or ""),
            (meta.get("description_clean") or ""),
            (meta.get("title") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        return [result]

    return []


def bmk_search_all_models(
    *,
    query: str,
    model_hint: Optional[str],
    list_models: Callable[[], List[str]],
    search_in_model: Callable[[str, str], List[Dict[str, Any]]],
    limit: int = 1,
) -> List[Dict[str, Any]]:
    limit = 1
    models = [model_hint] if model_hint else list_models()

    best: Optional[Dict[str, Any]] = None
    for model in models:
        hits = search_in_model(model, query)
        if not hits:
            continue
        candidate = hits[0]
        if best is None or float(candidate.get("score") or 0.0) > float(best.get("score") or 0.0):
            best = candidate
        if float(candidate.get("score") or 0.0) >= 1.0:
            break

    return [best] if best else []
