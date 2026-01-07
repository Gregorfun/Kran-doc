from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def _read_jsonl(path: Path, label: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    chunks: List[Dict[str, Any]] = []
    invalid_lines: List[Dict[str, Any]] = []
    if not path.exists():
        return chunks, invalid_lines

    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                if len(invalid_lines) < 5:
                    invalid_lines.append({"file": str(path), "line": idx, "reason": "invalid_json"})
                raise ValueError(f"{label}: invalid JSON at line {idx}")
            if not isinstance(obj, dict):
                if len(invalid_lines) < 5:
                    invalid_lines.append({"file": str(path), "line": idx, "reason": "not_object"})
                raise ValueError(f"{label}: JSON is not an object at line {idx}")
            chunk_id = obj.get("id")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                if len(invalid_lines) < 5:
                    invalid_lines.append({"file": str(path), "line": idx, "reason": "missing_id"})
                raise ValueError(f"{label}: missing/empty id at line {idx}")
            chunks.append(obj)
    return chunks, invalid_lines


def _merge_chunks(
    main_chunks: Iterable[Dict[str, Any]],
    ref_chunks: Iterable[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    ref_ids: List[str] = []
    for ch in ref_chunks:
        cid = str(ch.get("id"))
        if cid in seen_ids:
            continue
        ref_ids.append(cid)
        seen_ids.add(cid)
        output.append(ch)

    ref_id_set = set(ref_ids)
    overwritten_ids: List[str] = []
    deduped_main = 0

    for ch in main_chunks:
        cid = str(ch.get("id"))
        if cid in ref_id_set:
            if cid not in overwritten_ids:
                overwritten_ids.append(cid)
            deduped_main += 1
            continue
        if cid in seen_ids:
            deduped_main += 1
            continue
        seen_ids.add(cid)
        output.append(ch)

    report_counts = {
        "overwritten_by_ref": len(overwritten_ids),
        "deduped_main": deduped_main,
    }
    return output, {"overwritten_ids": overwritten_ids[:20], "counts": report_counts}


def _default_report_path(out_path: Path) -> Path:
    return out_path.with_name(out_path.stem + "_report.json")


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _inplace_replace(main_path: Path, out_path: Path) -> None:
    backup = main_path.with_suffix(main_path.suffix + ".bak")
    if main_path.exists():
        if backup.exists():
            backup.unlink()
        main_path.replace(backup)
    out_path.replace(main_path)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge reference chunks into main JSONL.")
    ap.add_argument("--in-main", required=True, help="Path to main JSONL.")
    ap.add_argument("--in-ref", required=True, help="Path to reference JSONL.")
    ap.add_argument("--out", required=True, help="Output JSONL path.")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite output if it exists.")
    ap.add_argument("--inplace", action="store_true", help="Replace main file with output (backup to .bak).")
    args = ap.parse_args(argv)

    in_main = Path(args.in_main)
    in_ref = Path(args.in_ref)
    out_path = Path(args.out)
    report_path = _default_report_path(out_path)

    if out_path.exists() and not args.overwrite and not args.inplace:
        print(json.dumps({"status": "error", "message": f"Output exists: {out_path}"}, ensure_ascii=False))
        return 1

    try:
        ref_chunks, ref_invalid = _read_jsonl(in_ref, "ref")
        main_chunks, main_invalid = _read_jsonl(in_main, "main")
    except ValueError as e:
        invalid_lines = []
        if "ref_invalid" in locals():
            invalid_lines.extend(ref_invalid)
        if "main_invalid" in locals():
            invalid_lines.extend(main_invalid)
        print(
            json.dumps(
                {
                    "status": "error",
                    "message": str(e),
                    "examples": {"invalid_lines": invalid_lines[:5]},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    merged, merge_info = _merge_chunks(main_chunks, ref_chunks)

    _write_jsonl(out_path, merged)
    if args.inplace:
        _inplace_replace(in_main, out_path)

    report = {
        "in_main": str(in_main),
        "in_ref": str(in_ref),
        "out": str(in_main if args.inplace else out_path),
        "counts": {
            "main_total": len(main_chunks),
            "ref_total": len(ref_chunks),
            "out_total": len(merged),
            "overwritten_by_ref": merge_info["counts"]["overwritten_by_ref"],
            "deduped_main": merge_info["counts"]["deduped_main"],
        },
        "examples": {
            "overwritten_ids": merge_info["overwritten_ids"],
        },
    }
    _write_report(report_path, report)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
