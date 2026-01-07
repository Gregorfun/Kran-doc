# Datei: scripts/global_index_builder.py
"""
Globaler Index-Builder für PDFDoc / Kran-Tools, mit zentraler Konfiguration.

Erzeugt:
- <reports_dir>/global_error_index.json
- <reports_dir>/global_bmk_index.json

BMK-Index (robust):
- Primär: aus <model>_GPT51_FULL_KNOWLEDGE.json -> data["bmk_lists"][wagon]["components"]
- Fallback: aus separaten Dateien in output/models/<model>/  (*BMK*.json)
  - unterstützt unterschiedliche JSON-Strukturen (dict/list, components/items/entries)
  - erkennt wagon aus Dateiname (_OW/_UW), sonst "unknown"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config_loader import get_config

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = get_config()

_models_dir = Path(CONFIG.models_dir)
MODELS_DIR = (BASE_DIR / _models_dir) if not _models_dir.is_absolute() else _models_dir

_reports_dir = Path(CONFIG.reports_dir)
REPORTS_DIR = (BASE_DIR / _reports_dir) if not _reports_dir.is_absolute() else _reports_dir

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        return s or None
    return str(x).strip() or None


def _guess_wagon_from_filename(name: str) -> str:
    u = name.upper()
    if "_OW" in u or "OBERWAGEN" in u:
        return "oberwagen"
    if "_UW" in u or "UNTERWAGEN" in u:
        return "unterwagen"
    return "unknown"


def _iter_candidate_lists(obj: Any) -> Iterable[List[Any]]:
    """
    Liefert mögliche Listen mit BMK-Records aus verschieden strukturierten JSONs.
    """
    if isinstance(obj, list):
        yield obj
        return

    if not isinstance(obj, dict):
        return

    # Häufige Container-Felder
    for k in ("components", "entries", "items", "bmks", "records", "data"):
        v = obj.get(k)
        if isinstance(v, list):
            yield v

    # Manchmal sind unter dict-Werten Listen versteckt
    for v in obj.values():
        if isinstance(v, list):
            yield v


def _extract_bmk_from_record(rec: Any) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """
    Versucht, aus einem Record (dict) eine BMK + Titel/Bezeichnung zu ziehen.
    Gibt (bmk, title, extras) zurück.
    """
    if not isinstance(rec, dict):
        return None, None, {}

    # BMK Code kann unterschiedlich heißen
    bmk = (
        _safe_str(rec.get("bmk"))
        or _safe_str(rec.get("code"))
        or _safe_str(rec.get("bmk_code"))
        or _safe_str(rec.get("bmkId"))
        or _safe_str(rec.get("id"))
    )

    title = (
        _safe_str(rec.get("title"))
        or _safe_str(rec.get("description"))
        or _safe_str(rec.get("desc"))
        or _safe_str(rec.get("name"))
        or _safe_str(rec.get("component"))
        or _safe_str(rec.get("text"))
    )

    extras: Dict[str, Any] = {}
    # optional: was wir oft haben/sehen
    for k in ("area", "group", "lsb_address", "lsb", "location", "remarks"):
        if k in rec and rec.get(k) is not None:
            extras[k] = rec.get(k)

    return bmk, title, extras


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


def _append_bmks_from_full_knowledge(model_name: str, data: Any, out_list: List[Dict[str, Any]]) -> int:
    """
    Nutzt data['bmk_lists'][wagon]['components'] falls vorhanden.
    """
    if not isinstance(data, dict):
        return 0

    bmk_lists = data.get("bmk_lists")
    if not isinstance(bmk_lists, dict):
        return 0

    added = 0
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

            bmk = _safe_str(comp.get("bmk"))
            if not bmk:
                continue

            entry = {
                "model": model_name,
                "wagon": wagon,
                "bmk": bmk,
                "area": comp.get("area"),
                "group": comp.get("group"),
                "title": comp.get("title"),
                "lsb_address": comp.get("lsb_address"),
                "source": {
                    "type": "full_knowledge",
                    "file": f"{model_name}_GPT51_FULL_KNOWLEDGE.json",
                },
            }
            out_list.append(entry)
            added += 1

    return added


def _append_bmks_from_bmk_files(model_dir: Path, model_name: str, out_list: List[Dict[str, Any]]) -> int:
    """
    Liest *BMK*.json Dateien im Modell-Ordner.
    """
    added = 0
    for p in sorted(model_dir.glob("*BMK*.json")):
        try:
            data = load_json(p)
        except Exception:
            continue

        wagon = _guess_wagon_from_filename(p.name)

        found_any = False
        for lst in _iter_candidate_lists(data):
            for rec in lst:
                bmk, title, extras = _extract_bmk_from_record(rec)
                if not bmk:
                    continue
                found_any = True

                entry = {
                    "model": model_name,
                    "wagon": wagon,
                    "bmk": bmk,
                    "title": title,
                    "source": {"type": "bmk_file", "file": p.name},
                }
                entry.update(extras)
                out_list.append(entry)
                added += 1

        # Wenn Datei ein Dict ist, aber keine Liste gefunden wurde:
        if isinstance(data, dict) and not found_any:
            # Manche Formate sind "bmk -> details" mapping
            # z.B. {"S304": {...}, "S305": {...}}
            # Wir erkennen das, wenn viele keys wie BMK aussehen.
            mapped = 0
            for k, v in data.items():
                kk = _safe_str(k)
                if not kk:
                    continue
                if isinstance(v, dict):
                    # heuristik: BMK keys oft kurz und alphanumerisch (S304, A81, Y221)
                    if len(kk) <= 10:
                        title = (
                            _safe_str(v.get("title"))
                            or _safe_str(v.get("description"))
                            or _safe_str(v.get("name"))
                        )
                        entry = {
                            "model": model_name,
                            "wagon": wagon,
                            "bmk": kk,
                            "title": title,
                            "source": {"type": "bmk_file_map", "file": p.name},
                        }
                        out_list.append(entry)
                        added += 1
                        mapped += 1
            # (optional) falls mapped==0: ignorieren

    return added


def build_global_bmk_index() -> None:
    bmk_index: List[Dict[str, Any]] = []

    model_dirs = [m for m in sorted(MODELS_DIR.iterdir()) if m.is_dir()]
    for model_dir in model_dirs:
        model_name = model_dir.name

        # 1) Full Knowledge (wenn vorhanden)
        full_file = model_dir / f"{model_name}_GPT51_FULL_KNOWLEDGE.json"
        if full_file.exists():
            try:
                data = load_json(full_file)
                _append_bmks_from_full_knowledge(model_name, data, bmk_index)
            except Exception:
                pass

        # 2) Fallback: BMK-Dateien direkt
        _append_bmks_from_bmk_files(model_dir, model_name, bmk_index)

    out = {
        "type": "global_bmk_index",
        "model_count": len(model_dirs),
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
