from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def extract_error_code_from_result(result: Dict[str, Any]) -> Optional[str]:
    meta = result.get("metadata") or {}
    candidates = [
        meta.get("error_code"),
        meta.get("code"),
        meta.get("bmk"),
        meta.get("id"),
        result.get("error_code"),
        result.get("code"),
        result.get("bmk"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        normalized = str(candidate).strip().upper()
        if 4 <= len(normalized) <= 8 and all(char in "0123456789ABCDEF" for char in normalized):
            return normalized
    return None


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts: List[str] = []
        for key, item in value.items():
            if item is None:
                continue
            key_text = str(key).strip()
            item_text = flatten_text(item).strip()
            if not item_text:
                continue
            if key_text:
                parts.append(f"{key_text}: {item_text}")
            else:
                parts.append(item_text)
        return " ".join(parts).strip()
    if isinstance(value, (list, tuple, set)):
        parts = [part for part in (flatten_text(item).strip() for item in value) if part]
        return " ".join(parts).strip()
    return str(value).strip()


def extract_explain_text(result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return ""
    explain = result.get("explain")
    if explain:
        return flatten_text(explain).strip()
    meta = result.get("metadata") or {}
    if isinstance(meta, dict):
        explain = meta.get("explain")
        if explain:
            return flatten_text(explain).strip()
    return ""


def meta_to_text(meta: Any) -> str:
    if not isinstance(meta, dict):
        return ""
    return flatten_text(meta).strip()


def classify_traffic_light(explain_text: str, meta: Dict[str, Any]) -> Dict[str, str]:
    text = (explain_text or "").lower()
    meta_text = meta_to_text(meta).lower()

    red_keywords = [
        "kritisch",
        "sofort",
        "not-aus",
        "not aus",
        "abschalten",
        "stop",
        "brand",
        "überhitz",
        "kurzschluss",
        "hydraulikdruck",
        "druck zu hoch",
        "brems",
        "lenkung",
        "ausfall sicherheit",
        "sicherheitsrelevant",
    ]
    yellow_keywords = [
        "warnung",
        "kommunikation",
        "can",
        "lsb",
        "datenbus",
        "sporadisch",
        "wackler",
        "teilnehmer offline",
        "telegramm",
        "feuchtigkeit",
        "korrosion",
        "kontaktproblem",
        "leitung",
        "abschirmung",
    ]

    def _find_match(haystack: str, keywords: List[str]) -> Optional[str]:
        for keyword in keywords:
            if keyword in haystack:
                return keyword
        return None

    red_match = _find_match(text, red_keywords) or _find_match(meta_text, red_keywords)
    if red_match:
        return {
            "traffic": "red",
            "traffic_label": "KRITISCH",
            "traffic_advice": "Betrieb stoppen bzw. sofort prüfen. Fehler kann Folgeschäden verursachen.",
            "traffic_reason": red_match,
        }

    yellow_match = _find_match(text, yellow_keywords) or _find_match(meta_text, yellow_keywords)
    if yellow_match:
        return {
            "traffic": "yellow",
            "traffic_label": "WARNUNG",
            "traffic_advice": "Weiterbetrieb möglich, aber zeitnah prüfen / Service planen.",
            "traffic_reason": yellow_match,
        }

    return {
        "traffic": "green",
        "traffic_label": "OK",
        "traffic_advice": "Weiterbetrieb möglich. Beobachten.",
    }


def attach_explain(
    *,
    results: List[Any],
    model: Optional[str],
    load_explain_catalog: Callable[[Optional[str]], Dict[str, Any]],
) -> List[Any]:
    catalog = load_explain_catalog(model)
    if not catalog:
        return results
    for result in results or []:
        try:
            if isinstance(result, dict) and "explain" not in result:
                code = extract_error_code_from_result(result)
                if code and code in catalog:
                    explain_data = catalog[code]
                    if "metadata" not in result or not isinstance(result.get("metadata"), dict):
                        result["metadata"] = {}
                    if isinstance(explain_data, dict):
                        result["metadata"].update(explain_data)
                    else:
                        result["metadata"].update({"explain": explain_data})
                    result["explain"] = explain_data
        except Exception:
            continue
    return results


def attach_traffic_light(*, results: List[Any]) -> List[Any]:
    for result in results or []:
        if not isinstance(result, dict):
            continue
        explain_text = extract_explain_text(result)
        if not explain_text:
            continue
        meta = result.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        traffic = classify_traffic_light(explain_text, meta)
        result["traffic_light"] = traffic
        if "metadata" not in result or not isinstance(result.get("metadata"), dict):
            result["metadata"] = {}
        result["metadata"]["traffic_light"] = traffic
    return results
