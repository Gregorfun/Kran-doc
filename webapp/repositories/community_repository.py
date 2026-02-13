from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[2]
COMMUNITY_DIR = BASE_DIR / "community"
USERS_PATH = COMMUNITY_DIR / "users.json"
SOLUTIONS_PATH = COMMUNITY_DIR / "solutions.json"

_community_lock = threading.Lock()


def _load_json_file(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return default


def _save_json_atomic(path: Path, data: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
    tmp_path.replace(path)


def ensure_community_storage() -> None:
    COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_PATH.exists():
        _save_json_atomic(USERS_PATH, [])
    if not SOLUTIONS_PATH.exists():
        _save_json_atomic(SOLUTIONS_PATH, [])


def load_users() -> List[Dict[str, Any]]:
    with _community_lock:
        data = _load_json_file(USERS_PATH, [])
    return data if isinstance(data, list) else []


def save_users(users: List[Dict[str, Any]]) -> None:
    with _community_lock:
        _save_json_atomic(USERS_PATH, users)


def load_solutions() -> List[Dict[str, Any]]:
    with _community_lock:
        data = _load_json_file(SOLUTIONS_PATH, [])
    return data if isinstance(data, list) else []


def save_solutions(solutions: List[Dict[str, Any]]) -> None:
    with _community_lock:
        _save_json_atomic(SOLUTIONS_PATH, solutions)
