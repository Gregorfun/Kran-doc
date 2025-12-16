# Datei: scripts/global_index_builder.py
"""
Globaler Index-Builder für PDFDoc / Kran-Tools, mit zentraler Konfiguration.

Erzeugt:
- <reports_dir>/global_error_index.json
- <reports_dir>/global_bmk_index.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.config_loader import get_config

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = get_config()

_models_dir = Path(CONFIG.models_dir)
if not _models_dir.is_absolute():
    MODELS_DIR = BASE_DIR / _models_dir
else:
    MODELS_DIR = _models_dir

_reports_dir = Path(CONFIG.reports_dir)
if not _reports_dir.is_absolute():
    REPORTS_DIR = BASE_DIR / _reports_dir
else:
    REPORTS_DIR = _reports_dir

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_global_error_index() -> None:
    error_index: List[Dict[str, Any]] = []

    for model_dir in sorted(MODELS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue

        model_name = model_dir.name
        full_file = model_dir / f"{model_name}_GPT51_FULL_KNOWLEDGE.json"
        if not full_file.exists():
            continue

        data = load_json(full_file)

        lec = data.get("lec_errors")
        if not isinstance(lec, dict):
            continue

        errors = lec.get("errors") or lec.get("entries") or []
        if not isinstance(errors, list):
            continue

        for err in errors:
            if not isinstance(err, dict):
                continue

            entry = {
                "model": model_name,
                "code": err.get("code"),
                "short_text": err.get("short_text") or err.get("title"),
                "long_text": err.get("long_text") or err.get("details"),
                "stecker": err.get("stecker"),
                "blatt": err.get("blatt"),
                "k": err.get("k"),
                "w": err.get("w"),
            }
            if entry["code"]:
                error_index.append(entry)

    out = {
        "type": "global_error_index",
        "model_count": sum(1 for m in MODELS_DIR.iterdir() if m.is_dir()),
        "error_count": len(error_index),
        "errors": error_index,
    }

    output_file = REPORTS_DIR / "global_error_index.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Globaler Fehlercode-Index gespeichert unter: {output_file}")
    print(f"  -> Modelle: {out['model_count']}, Fehlercodes: {out['error_count']}")


def build_global_bmk_index() -> None:
    bmk_index: List[Dict[str, Any]] = []

    for model_dir in sorted(MODELS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue

        model_name = model_dir.name
        full_file = model_dir / f"{model_name}_GPT51_FULL_KNOWLEDGE.json"
        if not full_file.exists():
            continue

        data = load_json(full_file)

        bmk_lists = data.get("bmk_lists")
        if not isinstance(bmk_lists, dict):
            continue

        for wagon in ("unterwagen", "oberwagen"):
            bmk_data = bmk_lists.get(wagon)
            if not isinstance(bmk_data, dict):
                continue
            components = bmk_data.get("components", [])
            if not isinstance(components, list):
                continue

            for comp in components:
                if not isinstance(comp, dict):
                    continue
                entry = {
                    "model": model_name,
                    "wagon": wagon,
                    "bmk": comp.get("bmk"),
                    "area": comp.get("area"),
                    "group": comp.get("group"),
                    "title": comp.get("title"),
                    "lsb_address": comp.get("lsb_address"),
                }
                if entry["bmk"]:
                    bmk_index.append(entry)

    out = {
        "type": "global_bmk_index",
        "model_count": sum(1 for m in MODELS_DIR.iterdir() if m.is_dir()),
        "bmk_count": len(bmk_index),
        "bmks": bmk_index,
    }

    output_file = REPORTS_DIR / "global_bmk_index.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Globaler BMK-Index gespeichert unter: {output_file}")
    print(f"  -> Modelle: {out['model_count']}, BMKs: {out['bmk_count']}")


def main() -> None:
    print("=== GLOBAL INDEX BUILDER (mit Config) ===")
    build_global_error_index()
    build_global_bmk_index()
    print("=== FERTIG ===")


if __name__ == "__main__":
    main()
