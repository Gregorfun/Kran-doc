from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_DIR = BASE_DIR / "output" / "models"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_full_knowledge(model: str) -> Dict[str, Any]:
    model_dir = MODELS_DIR / model
    if not model_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {model_dir}")

    # zuerst GPT51, dann legacy
    fk = model_dir / f"{model}_GPT51_FULL_KNOWLEDGE.json"
    if not fk.exists():
        fk = model_dir / f"{model}_FULL_KNOWLEDGE.json"
    return load_json(fk)


def list_codes_with_bmk(model: str) -> None:
    data = load_full_knowledge(model)
    lec_errors = data.get("lec_errors") or []
    if not isinstance(lec_errors, list):
        lec_errors = []

    codes: List[Dict[str, Any]] = []
    for err in lec_errors:
        if not isinstance(err, dict):
            continue
        if err.get("linked_bmk"):
            codes.append(
                {
                    "code": err.get("code") or err.get("error_code"),
                    "lsb_key": err.get("lsb_key"),
                    "num_bmk": len(err.get("linked_bmk") or []),
                    "bmk_summary": err.get("bmk_summary"),
                }
            )

    print(f"[MODEL] {model}")
    print(f"  Fehler mit BMK-Link: {len(codes)}")

    # ein paar Beispiele ausgeben
    for entry in codes[:50]:
        print(
            f"  {entry['code']}: BMK={entry['bmk_summary']} "
            f"(LSB={entry['lsb_key']}, Links={entry['num_bmk']})"
        )


def debug_single_code(model: str, code: str) -> None:
    data = load_full_knowledge(model)
    lec_errors = data.get("lec_errors") or []
    if not isinstance(lec_errors, list):
        lec_errors = []

    print(f"[DEBUG] Modell: {model}, Fehlercode: {code}")
    found = False
    for err in lec_errors:
        if not isinstance(err, dict):
            continue
        err_code = err.get("code") or err.get("error_code")
        if str(err_code) != str(code):
            continue

        found = True
        print(f"  Gefunden in FULL_KNOWLEDGE.")
        print(f"    lsb_raw:   {err.get('lsb') or err.get('lsb_raw') or err.get('lsb_text')}")
        print(f"    lsb_key:   {err.get('lsb_key')}")
        print(f"    bmk_links: {len(err.get('linked_bmk') or [])}")
        print(f"    bmk_summary: {err.get('bmk_summary')}")
        if err.get("linked_bmk"):
            for i, b in enumerate(err["linked_bmk"], 1):
                print(
                    f"      [{i}] BMK={b.get('bmk')} "
                    f"Sensor={b.get('sensor_name')} "
                    f"Ort={b.get('location')} "
                    f"Modul={b.get('module')}"
                )
        break

    if not found:
        print("  -> Fehlercode in FULL_KNOWLEDGE nicht gefunden.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Verwendung:")
        print("  python -m scripts.debug_bmk_links <Modell> [Fehlercode]")
        print("Beispiele:")
        print("  python -m scripts.debug_bmk_links LTM1110-5.1")
        print("  python -m scripts.debug_bmk_links LTM1110-5.1 1B1950")
        return

    model = sys.argv[1]
    if len(sys.argv) == 2:
        list_codes_with_bmk(model)
    else:
        code = sys.argv[2]
        debug_single_code(model, code)


if __name__ == "__main__":
    main()
