from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def load_feedback_entries(*, base_dir: str, limit: int = 5000) -> List[Dict[str, Any]]:
    path = Path(base_dir) / "logs" / "feedback.jsonl"
    if not path.exists():
        return []

    entries: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    entries.append(item)
    except Exception:
        return []

    if limit > 0 and len(entries) > limit:
        return entries[-limit:]
    return entries


def build_feedback_insights(*, feedback_entries: List[Dict[str, Any]], solutions: List[Dict[str, Any]]) -> Dict[str, Any]:
    negative_notes = 0
    code_counter: Counter[str] = Counter()
    model_counter: Counter[str] = Counter()

    for entry in feedback_entries:
        note = str(entry.get("note") or "").strip().lower()
        result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}

        if note:
            negative_notes += 1

        code = metadata.get("error_code") or metadata.get("code") or metadata.get("bmk")
        if code:
            code_counter[str(code).upper()] += 1

        model = result.get("model") or metadata.get("model")
        if model:
            model_counter[str(model)] += 1

    approved_solution_codes = {
        str(s.get("error_code") or "").upper()
        for s in solutions
        if (s.get("status") or "").strip().lower() == "approved" and s.get("error_code")
    }

    missing_solution_codes = [
        {"code": code, "mentions": count}
        for code, count in code_counter.most_common(10)
        if code not in approved_solution_codes
    ]

    return {
        "feedback_total": len(feedback_entries),
        "feedback_negative_notes": negative_notes,
        "top_codes": [{"code": code, "mentions": count} for code, count in code_counter.most_common(10)],
        "top_models": [{"model": model, "mentions": count} for model, count in model_counter.most_common(10)],
        "missing_solution_codes": missing_solution_codes,
    }


def build_quick_help_cards(*, solutions: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    approved = [s for s in solutions if (s.get("status") or "").strip().lower() == "approved"]
    scored: Dict[tuple[str, str], Dict[str, Any]] = {}

    for item in approved:
        model = str(item.get("model") or "").strip()
        code = str(item.get("error_code") or "").strip().upper()
        if not model or not code:
            continue
        key = (model, code)
        bucket = scored.setdefault(
            key,
            {
                "model": model,
                "error_code": code,
                "title": item.get("title") or "",
                "symptom": item.get("symptom") or "",
                "count": 0,
                "last_created_at": item.get("created_at") or "",
            },
        )
        bucket["count"] += 1
        created_at = str(item.get("created_at") or "")
        if created_at > str(bucket.get("last_created_at") or ""):
            bucket["last_created_at"] = created_at
            bucket["title"] = item.get("title") or bucket.get("title")
            bucket["symptom"] = item.get("symptom") or bucket.get("symptom")

    cards = sorted(scored.values(), key=lambda row: (int(row.get("count") or 0), str(row.get("last_created_at") or "")), reverse=True)
    out = []
    for row in cards[:limit]:
        out.append(
            {
                "model": row.get("model"),
                "error_code": row.get("error_code"),
                "title": row.get("title"),
                "symptom": row.get("symptom"),
                "occurrence": row.get("count"),
            }
        )
    return out


def compute_coverage_kpis(
    *,
    model_names: List[str],
    solutions: List[Dict[str, Any]],
    load_lec_index_for_model: Any,
) -> Dict[str, Any]:
    approved_by_model: Dict[str, set[str]] = {}
    for solution in solutions:
        if (solution.get("status") or "").strip().lower() != "approved":
            continue
        model = str(solution.get("model") or "").strip()
        code = str(solution.get("error_code") or "").strip().upper()
        if not model or not code:
            continue
        approved_by_model.setdefault(model, set()).add(code)

    per_model: List[Dict[str, Any]] = []
    total_lec = 0
    total_with_solution = 0

    for model in model_names:
        try:
            lec_index = load_lec_index_for_model(model) or {}
        except Exception:
            lec_index = {}
        lec_codes = {str(code).upper() for code in lec_index.keys()}
        solved_codes = approved_by_model.get(model, set())
        covered = len(lec_codes.intersection(solved_codes)) if lec_codes else 0
        coverage_ratio = (covered / len(lec_codes)) if lec_codes else 0.0
        total_lec += len(lec_codes)
        total_with_solution += covered

        per_model.append(
            {
                "model": model,
                "lec_codes": len(lec_codes),
                "covered_codes": covered,
                "coverage_ratio": round(coverage_ratio, 4),
            }
        )

    overall_ratio = (total_with_solution / total_lec) if total_lec else 0.0
    return {
        "overall": {
            "lec_codes": total_lec,
            "covered_codes": total_with_solution,
            "coverage_ratio": round(overall_ratio, 4),
        },
        "per_model": per_model,
    }