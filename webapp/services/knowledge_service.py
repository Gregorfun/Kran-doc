from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


def _find_first_existing(paths: list[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


@lru_cache(maxsize=64)
def load_full_knowledge_model(*, models_dir: str, model: str) -> Dict[str, Any]:
    model_dir = Path(models_dir) / model
    candidate = _find_first_existing(
        [
            model_dir / f"{model}_FULL_KNOWLEDGE.json",
            model_dir / f"{model}_GPT51_FULL_KNOWLEDGE.json",
            model_dir / f"{model}_FULL_KNOWLEDGE",
            model_dir / f"{model}_GPT51_FULL_KNOWLEDGE",
        ]
    )
    if not candidate:
        return {}
    try:
        data = _load_json(candidate)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=64)
def load_lec_index_for_model(*, models_dir: str, model: str) -> Dict[str, Dict[str, Any]]:
    model_dir = Path(models_dir) / model
    source_path = _find_first_existing(
        [
            model_dir / f"{model}_LEC_ERRORS.json",
            model_dir / f"{model}_LEC_ERRORS",
        ]
    )
    if not source_path:
        return {}

    try:
        data = _load_json(source_path)
    except Exception:
        return {}

    if isinstance(data, dict) and "errors" in data and isinstance(data["errors"], list):
        errors = data["errors"]
    elif isinstance(data, list):
        errors = data
    elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        errors = data["data"]
    else:
        errors = []

    index: Dict[str, Dict[str, Any]] = {}
    for entry in errors:
        if not isinstance(entry, dict):
            continue
        code = (entry.get("error_code") or entry.get("code") or entry.get("id") or "").strip()
        if not code:
            continue
        index[code.upper()] = entry
    return index


@lru_cache(maxsize=64)
def load_spl_references_for_model(*, models_dir: str, model: str) -> Dict[str, Any]:
    model_dir = Path(models_dir) / model
    source_path = _find_first_existing(
        [
            model_dir / f"{model}_SPL_REFERENCES.json",
            model_dir / f"{model}_SPL_REFERENCES",
        ]
    )
    if not source_path:
        return {}

    try:
        data = _load_json(source_path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
