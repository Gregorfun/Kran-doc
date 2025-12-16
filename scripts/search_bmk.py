from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]  # .../kran-tools
MODELS_DIR = BASE_DIR / "output" / "models"


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_model_dirs(model: Optional[str]) -> List[Path]:
    """
    Wenn model=None -> alle Modelle, sonst nur das angegebene.
    """
    if not MODELS_DIR.exists():
        return []

    if model:
        d = MODELS_DIR / model
        return [d] if d.exists() else []

    # alle Modellordner
    return [d for d in MODELS_DIR.iterdir() if d.is_dir()]


def find_full_knowledge_file(model_dir: Path) -> Optional[Path]:
    """
    Nimmt – wie export_for_embeddings – zuerst *_GPT51_FULL_KNOWLEDGE.json,
    sonst *_FULL_KNOWLEDGE.json.
    """
    gpt51 = list(model_dir.glob("*_GPT51_FULL_KNOWLEDGE.json"))
    if gpt51:
        return gpt51[0]

    legacy = list(model_dir.glob("*_FULL_KNOWLEDGE.json"))
    if legacy:
        return legacy[0]

    return None


def iter_bmk_components(data: Dict[str, Any]):
    """
    Generator über alle BMK-Komponenten in FULL_KNOWLEDGE.
    Erwartete Struktur:
        "bmk_data": [
            { "components": [ { ... }, ... ] },
            ...
        ]
    """
    bmk_blocks = data.get("bmk_data") or []
    if not isinstance(bmk_blocks, list):
        return

    for block in bmk_blocks:
        if not isinstance(block, dict):
            continue
        comps = block.get("components")
        if not isinstance(comps, list):
            continue
        for comp in comps:
            if isinstance(comp, dict):
                yield comp


def bmk_matches(comp: Dict[str, Any], query: str) -> bool:
    """
    Prüft, ob der BMK-Code den Suchstring enthält (case-insensitive).
    z.B. query='A81' → findet 'A81', 'ZA81', 'A81-1', ...
    """
    q = query.upper()
    bmk = (
        comp.get("bmk")
        or comp.get("tag")
        or comp.get("kennzeichen")
        or ""
    )
    return q in str(bmk).upper()


def format_bmk_component(model: str, comp: Dict[str, Any]) -> str:
    bmk = comp.get("bmk") or comp.get("tag") or comp.get("kennzeichen") or "?"
    descr = (
        comp.get("sensor_name")
        or comp.get("description")
        or comp.get("component")
        or ""
    )
    loc = (
        comp.get("location")
        or comp.get("area")
        or comp.get("ort")
        or comp.get("einbauort")
        or ""
    )
    module = (
        comp.get("module")
        or comp.get("group")
        or comp.get("modul")
        or comp.get("wagen_blatt")
        or ""
    )
    sheet = comp.get("sheet") or comp.get("blatt") or ""
    lsb = comp.get("lsb_key") or comp.get("lsb") or ""

    lines = [
        f"Modell:      {model}",
        f"BMK:         {bmk}",
    ]
    if descr:
        lines.append(f"Beschreibung: {descr}")
    if loc:
        lines.append(f"Ort/Bereich:  {loc}")
    if module:
        lines.append(f"Gruppe/Modul: {module}")
    if sheet:
        lines.append(f"Blatt/Wagen:  {sheet}")
    if lsb:
        lines.append(f"LSB-Key:      {lsb}")

    return "\n".join(lines)


def search_bmk(query: str, model: Optional[str] = None) -> None:
    model_dirs = find_model_dirs(model)
    if not model_dirs:
        print("[BMK-SUCHE] Keine passenden Modell-Ordner gefunden.")
        return

    print(f"[BMK-SUCHE] Suche nach '{query}'" + (f" im Modell {model}" if model else " in allen Modellen"))
    print()

    hit_count = 0

    for mdir in model_dirs:
        fk = find_full_knowledge_file(mdir)
        if not fk:
            continue

        data = load_json(fk)
        if not isinstance(data, dict):
            continue

        model_name = data.get("model") or mdir.name

        for comp in iter_bmk_components(data):
            if not bmk_matches(comp, query):
                continue

            hit_count += 1
            print("=" * 70)
            print(format_bmk_component(model_name, comp))
            print()

    if hit_count == 0:
        print("[BMK-SUCHE] Keine Treffer gefunden.")
    else:
        print(f"[BMK-SUCHE] Gesamt-Treffer: {hit_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Direkte BMK-Suche (BMK-Code → Beschreibung/Ort)."
    )
    parser.add_argument(
        "query",
        help="BMK-Code oder Teil davon (z.B. 'A81', 'S987').",
    )
    parser.add_argument(
        "model",
        nargs="?",
        default=None,
        help="Optional: Modellname (z.B. 'LTM1110-5.1'). Wenn leer, werden alle Modelle durchsucht.",
    )

    args = parser.parse_args()
    search_bmk(args.query, args.model)


if __name__ == "__main__":
    main()
