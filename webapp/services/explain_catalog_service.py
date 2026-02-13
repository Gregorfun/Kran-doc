from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


def explain_paths_for_model(*, base_dir: str, model: Optional[str]) -> List[Path]:
    paths: List[Path] = []
    base = Path(base_dir)
    if model:
        paths.append(base / "output" / "models" / model / "explain_catalog.json")
    paths.append(base / "output" / "explain_catalog_all.json")
    return paths


@lru_cache(maxsize=128)
def load_explain_catalog(*, base_dir: str, model: Optional[str]) -> Dict[str, Any]:
    for path in explain_paths_for_model(base_dir=base_dir, model=model):
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as file:
                    data = json.load(file)
                if isinstance(data, dict):
                    return data
        except Exception:
            continue
    return {}
