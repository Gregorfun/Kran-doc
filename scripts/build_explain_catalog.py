#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kran-Doc Explain Catalog Builder (MVP)

- Scans model folders for LEC error exports (e.g. <MODEL>_LEC_ERRORS.json).
- Applies keyword rules to classify each error into a category.
- Builds an explain object from category templates.
- Writes:
  - output/models/<MODEL>/explain_catalog.json  (per model)
  - output/explain_catalog_all.json            (optional, aggregated)

No GPT, no API. Deterministic + safe.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ERROR_CODE_RE = re.compile(r"^[0-9A-F]{4,8}$", re.IGNORECASE)

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def normalize_text(*parts: Any) -> str:
    text = "\n".join(str(p or "") for p in parts)
    text = text.replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()

def extract_code(err: Dict[str, Any]) -> Optional[str]:
    code = (err.get("error_code") or err.get("code") or err.get("id") or "").strip().upper()
    if not code:
        return None
    if ERROR_CODE_RE.match(code):
        return code
    m = re.search(r"\b[0-9A-F]{4,8}\b", code, re.IGNORECASE)
    return m.group(0).upper() if m else None

Rule = Dict[str, Any]

def match_rule(rule: Rule, text: str, code: str) -> bool:
    codes = rule.get("codes")
    if isinstance(codes, list) and codes:
        return code.upper() in {str(c).strip().upper() for c in codes}

    match_all = [str(x).lower() for x in (rule.get("match_all") or [])]
    match_any = [str(x).lower() for x in (rule.get("match_any") or [])]
    match_none = [str(x).lower() for x in (rule.get("match_none") or [])]

    if match_all and not all(k in text for k in match_all):
        return False
    if match_any and not any(k in text for k in match_any):
        return False
    if match_none and any(k in text for k in match_none):
        return False

    if not match_all and not match_any and not codes:
        return False

    return True

def choose_category(rules: List[Rule], text: str, code: str) -> Optional[str]:
    for rule in rules:
        cat = rule.get("category")
        if not cat:
            continue
        if match_rule(rule, text=text, code=code):
            return str(cat)
    return None

def build_explain_from_template(template: Dict[str, Any], model: str, code: str, short_text: str, long_text: str) -> Dict[str, Any]:
    exp = dict(template)
    exp.setdefault("category", template.get("category"))
    exp["context"] = f"{model} · {code}"

    if short_text:
        exp.setdefault("lec_short_text", short_text.strip())
    if long_text:
        exp.setdefault("lec_long_text", long_text.strip()[:600])

    return exp

def find_lec_errors_file(model_dir: Path, model_name: str) -> Optional[Path]:
    candidates = [
        model_dir / f"{model_name}_LEC_ERRORS.json",
        model_dir / "lec_errors.json",
        model_dir / "LEC_ERRORS.json",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None

def iter_lec_errors(lec_json: Any) -> List[Dict[str, Any]]:
    if isinstance(lec_json, list):
        return [x for x in lec_json if isinstance(x, dict)]
    if isinstance(lec_json, dict):
        if isinstance(lec_json.get("errors"), list):
            return [x for x in lec_json["errors"] if isinstance(x, dict)]
        if isinstance(lec_json.get("data"), list):
            return [x for x in lec_json["data"] if isinstance(x, dict)]
    return []

def build_for_model(model_dir: Path, model_name: str, rules: List[Rule], templates: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    lec_file = find_lec_errors_file(model_dir, model_name)
    if not lec_file:
        return {}, {}

    lec_json = load_json(lec_file)
    errors = iter_lec_errors(lec_json)

    catalog: Dict[str, Any] = {}
    stats: Dict[str, int] = {"total_errors": 0, "with_explain": 0, "no_match": 0}

    for err in errors:
        stats["total_errors"] += 1
        code = extract_code(err)
        if not code:
            continue

        short_text = str(err.get("short_text") or err.get("title") or "").strip()
        long_text = str(err.get("long_text") or err.get("text") or "").strip()
        text = normalize_text(short_text, long_text)

        category = choose_category(rules, text=text, code=code)
        if not category:
            stats["no_match"] += 1
            continue

        template = templates.get(category)
        if not template:
            stats["no_match"] += 1
            continue

        tpl = dict(template)
        tpl.setdefault("category", category)

        explain = build_explain_from_template(
            tpl,
            model=model_name,
            code=code,
            short_text=short_text,
            long_text=long_text,
        )
        catalog[code] = explain
        stats["with_explain"] += 1

    return catalog, stats

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", required=True, help="Path to output/models (contains model subfolders)")
    ap.add_argument("--rules", default="config/explain_rules.json", help="Path to explain_rules.json")
    ap.add_argument("--templates", default="config/explain_templates.json", help="Path to explain_templates.json")
    ap.add_argument("--out-name", default="explain_catalog.json", help="Output filename inside each model folder")
    ap.add_argument("--write-aggregated", action="store_true", help="Also write output/explain_catalog_all.json")
    args = ap.parse_args()

    models_dir = Path(args.models_dir).expanduser().resolve()
    rules_path = Path(args.rules).expanduser().resolve()
    templates_path = Path(args.templates).expanduser().resolve()

    if not models_dir.exists():
        raise SystemExit(f"models-dir not found: {models_dir}")
    if not rules_path.exists():
        raise SystemExit(f"rules not found: {rules_path}")
    if not templates_path.exists():
        raise SystemExit(f"templates not found: {templates_path}")

    rules = load_json(rules_path)
    templates = load_json(templates_path)

    if not isinstance(rules, list):
        raise SystemExit("rules json must be a list")
    if not isinstance(templates, dict):
        raise SystemExit("templates json must be an object/dict")

    aggregated: Dict[str, Any] = {}
    overall = {"models": 0, "total_errors": 0, "with_explain": 0, "no_match": 0}

    for model_dir in sorted([p for p in models_dir.iterdir() if p.is_dir()]):
        model_name = model_dir.name
        catalog, stats = build_for_model(model_dir, model_name, rules=rules, templates=templates)
        if not catalog:
            continue

        out_path = model_dir / args.out_name
        save_json(out_path, catalog)

        overall["models"] += 1
        overall["total_errors"] += stats.get("total_errors", 0)
        overall["with_explain"] += stats.get("with_explain", 0)
        overall["no_match"] += stats.get("no_match", 0)

        aggregated.update(catalog)

        print(f"[{model_name}] wrote {len(catalog)} explain entries -> {out_path.name} "
              f"(total={stats.get('total_errors')} matched={stats.get('with_explain')} no_match={stats.get('no_match')})")

    if args.write_aggregated:
        out_all = models_dir.parent / "explain_catalog_all.json"
        save_json(out_all, aggregated)
        print(f"[ALL] wrote {len(aggregated)} entries -> {out_all}")

    print("DONE", overall)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
