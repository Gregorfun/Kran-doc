from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List


def collect_bmk_components_for_model(
    *,
    models_dir: str,
    model: str,
    load_full_knowledge_model: Callable[..., Dict[str, Any]],
) -> List[Dict[str, Any]]:
    data = load_full_knowledge_model(models_dir=models_dir, model=model) or {}
    components: List[Dict[str, Any]] = []

    raw_lists = []
    bmk_lists = data.get("bmk_lists") if isinstance(data, dict) else None
    if isinstance(bmk_lists, dict):
        for wagon_key in ("oberwagen", "unterwagen"):
            wagon_data = bmk_lists.get(wagon_key)
            if isinstance(wagon_data, dict):
                raw_lists.append((wagon_key, wagon_data))

    for key in ("bmk_components", "bmk_list", "bmk", "components"):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, dict):
            raw_lists.append(("unknown", value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    component = dict(item)
                    component.setdefault("_wagon", item.get("wagon") or "unknown")
                    components.append(component)

    for wagon_key, raw in raw_lists:
        if not isinstance(raw, dict):
            continue

        items: List[Any] = []
        if isinstance(raw.get("components"), list):
            items = raw["components"]
        elif isinstance(raw.get("items"), list):
            items = raw["items"]
        elif isinstance(raw.get("data"), list):
            items = raw["data"]

        for item in items:
            if isinstance(item, dict):
                component = dict(item)
                component["_wagon"] = wagon_key
                components.append(component)

    model_dir = Path(models_dir) / model
    for wagon, filename in (("oberwagen", f"{model}_BMK_OW.json"), ("unterwagen", f"{model}_BMK_UW.json")):
        path = model_dir / filename
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as file:
                bm_data = json.load(file)
            if isinstance(bm_data, dict) and isinstance(bm_data.get("components"), list):
                for item in bm_data["components"]:
                    if isinstance(item, dict):
                        component = dict(item)
                        component.setdefault("_wagon", wagon)
                        components.append(component)
        except Exception:
            continue

    return components


def build_bmk_index_for_components(
    *,
    components: List[Dict[str, Any]],
    is_probably_non_german: Callable[[str], bool],
    is_valid_bmk_code: Callable[[str], bool],
    clean_text_field: Callable[[Any], str],
    clean_description: Callable[[Any], str],
    lsb_keys_from_bmk_lsb: Callable[[Any], List[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}

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

        raw_lsb = (
            component.get("lsb_address")
            or component.get("lsb")
            or component.get("lsb_key")
            or component.get("lsb_bmk_address")
        )
        keys = lsb_keys_from_bmk_lsb(raw_lsb)
        if not keys:
            continue

        location = (area + (" / " + group if group else "")).strip() or None

        entry = {
            "sensor_bmk": bmk_code or None,
            "sensor_title": title or None,
            "sensor_description": desc_clean or None,
            "sensor_location": location,
            "sensor_area": area or None,
            "sensor_group": group or None,
            "sensor_wagon": wagon or None,
            "lsb_bmk_address": str(raw_lsb).strip() if raw_lsb else None,
            "_raw_component": component,
        }

        for key in keys:
            index.setdefault(key, []).append(entry)

    for key in list(index.keys()):
        index[key] = sorted(
            index[key], key=lambda item: ((item.get("sensor_bmk") or ""), (item.get("sensor_title") or ""))
        )

    return index
