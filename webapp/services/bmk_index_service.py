from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


@lru_cache(maxsize=1)
def load_global_bmk_index(*, base_dir: str) -> Dict[tuple[str, str], Dict[str, Any]]:
    path = Path(base_dir) / "output" / "reports" / "global_bmk_index.json"
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return {}

    bmks = data.get("bmks") if isinstance(data, dict) else None
    lookup: Dict[tuple[str, str], Dict[str, Any]] = {}

    if isinstance(bmks, list):
        for entry in bmks:
            if not isinstance(entry, dict):
                continue
            model = (entry.get("model") or "").strip()
            bmk = (entry.get("bmk") or "").strip()
            if not model or not bmk:
                continue
            key = (model.upper(), bmk.upper())
            lookup[key] = entry

    return lookup


def get_bmk_entry(*, base_dir: str, model: str, bmk_code: str) -> Optional[Dict[str, Any]]:
    model_key = (model or "").strip().upper()
    bmk_key = (bmk_code or "").strip().upper()
    if not model_key or not bmk_key:
        return None
    lookup = load_global_bmk_index(base_dir=base_dir)
    return lookup.get((model_key, bmk_key))
