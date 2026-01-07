from __future__ import annotations

"""
Assumption: This script lives under .../kran-tools/scripts and the reference file
defaults to docs/reference/muster_wissenskarte_v1.json relative to the repo root.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


ALLOWED_TYPES = {"lec", "bmk", "spl", "qa", "manual", "community"}
ALLOWED_CONFIDENCE = {"starterpack", "community", "imported"}

OPTIONAL_FIELDS = {
    "short_description",
    "text",
    "severity",
    "symptoms",
    "likely_causes",
    "checks",
    "bmk_refs",
    "lsb_address",
    "related_chunks",
    "tags",
    "question",
    "answer",
}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return json.loads(path.read_text(encoding="utf-8-sig"))


def load_reference_doc(path: Path) -> Dict[str, Any]:
    data = _read_json(path)
    if not isinstance(data, dict):
        return {}
    return data


def load_reference_chunks(path: Path) -> List[Dict[str, Any]]:
    doc = load_reference_doc(path)
    chunks = doc.get("chunks")
    if not isinstance(chunks, list):
        return []
    return [c for c in chunks if isinstance(c, dict)]


def _error(code: str, message: str, chunk_id: Optional[str] = None) -> Dict[str, Any]:
    item: Dict[str, Any] = {"code": code, "message": message}
    if chunk_id:
        item["chunk_id"] = chunk_id
    return item


def _warn(code: str, message: str, chunk_id: Optional[str] = None) -> Dict[str, Any]:
    item: Dict[str, Any] = {"code": code, "message": message}
    if chunk_id:
        item["chunk_id"] = chunk_id
    return item


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _has_whitespace(value: str) -> bool:
    return any(ch.isspace() for ch in value)


def validate_reference_doc(doc: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not isinstance(doc, dict):
        errors.append(_error("invalid_root", "JSON root must be an object."))
        return errors, warnings

    schema_version = doc.get("schema_version")
    if not _is_non_empty_str(schema_version):
        errors.append(_error("missing_schema_version", "schema_version is required and must be a string."))

    chunks = doc.get("chunks")
    if not isinstance(chunks, list):
        errors.append(_error("invalid_chunks", "chunks must be a list."))
        return errors, warnings

    seen_ids: set[str] = set()

    for idx, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            errors.append(_error("invalid_chunk", f"Chunk at index {idx} is not an object."))
            continue

        chunk_id = chunk.get("id")
        if not _is_non_empty_str(chunk_id):
            errors.append(_error("missing_id", "id is required and must be a non-empty string."))
            chunk_id = None
        else:
            if _has_whitespace(str(chunk_id)):
                errors.append(_error("invalid_id", "id must not contain whitespace.", str(chunk_id)))
            if str(chunk_id) in seen_ids:
                errors.append(_error("duplicate_id", "id must be unique.", str(chunk_id)))
            seen_ids.add(str(chunk_id))

        chunk_type = chunk.get("type")
        if not _is_non_empty_str(chunk_type):
            errors.append(_error("missing_type", "type is required and must be a string.", chunk_id))
        elif str(chunk_type) not in ALLOWED_TYPES:
            errors.append(_error("invalid_type", f"type must be one of {sorted(ALLOWED_TYPES)}.", chunk_id))

        model = chunk.get("model")
        if not _is_non_empty_str(model):
            errors.append(_error("missing_model", "model is required and must be a non-empty string.", chunk_id))

        title = chunk.get("title")
        if not _is_non_empty_str(title):
            errors.append(_error("missing_title", "title is required and must be a non-empty string.", chunk_id))

        confidence = chunk.get("confidence")
        if not _is_non_empty_str(confidence):
            errors.append(_error("missing_confidence", "confidence is required and must be a string.", chunk_id))
        elif str(confidence) not in ALLOWED_CONFIDENCE:
            errors.append(
                _error("invalid_confidence", f"confidence must be one of {sorted(ALLOWED_CONFIDENCE)}.", chunk_id)
            )

        source = chunk.get("source")
        if not isinstance(source, dict):
            errors.append(_error("missing_source", "source must be an object with at least source.type.", chunk_id))
        else:
            source_type = source.get("type")
            if not _is_non_empty_str(source_type):
                errors.append(_error("missing_source_type", "source.type is required and must be a string.", chunk_id))

        related = chunk.get("related_chunks")
        if related is not None and not isinstance(related, list):
            warnings.append(
                _warn("invalid_related_chunks", "related_chunks should be a list of ids.", chunk_id)
            )

        for field in OPTIONAL_FIELDS:
            if field in chunk and chunk[field] in ("", None):
                warnings.append(
                    _warn("empty_optional_field", f"Optional field '{field}' is empty.", chunk_id)
                )

    # Cross-reference validation
    id_set = set(seen_ids)
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        chunk_id = chunk.get("id") if _is_non_empty_str(chunk.get("id")) else None
        related = chunk.get("related_chunks")
        if isinstance(related, list):
            for rel in related:
                if not _is_non_empty_str(rel):
                    warnings.append(
                        _warn("invalid_related_id", "related_chunks contains a non-string id.", chunk_id)
                    )
                    continue
                if str(rel) not in id_set:
                    errors.append(
                        _error("missing_related_chunk", f"related_chunks references unknown id '{rel}'.", chunk_id)
                    )

    return errors, warnings


def _normalize_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _build_text(chunk: Dict[str, Any]) -> str:
    text = _normalize_text(chunk.get("text"))
    if text:
        return text
    question = _normalize_text(chunk.get("question"))
    answer = _normalize_text(chunk.get("answer"))
    if answer and question:
        return f"Frage: {question}\nAntwort: {answer}"
    if answer:
        return answer
    if question:
        return f"Frage: {question}"
    return ""


def _build_content(chunk: Dict[str, Any], text: str) -> str:
    title = _normalize_text(chunk.get("title"))
    chunk_type = _normalize_text(chunk.get("type"))
    if chunk_type == "qa":
        question = _normalize_text(chunk.get("question"))
        answer = _normalize_text(chunk.get("answer"))
        parts = [title]
        if question:
            parts.append(f"Frage: {question}")
        if answer:
            parts.append(f"Antwort: {answer}")
        return "\n\n".join([p for p in parts if p])
    short_description = _normalize_text(chunk.get("short_description"))
    parts = [title]
    if short_description:
        parts.append(short_description)
    if text:
        parts.append(text)
    return "\n\n".join([p for p in parts if p])


def _to_jsonl_rows(chunks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        text = _build_text(chunk)
        row = {
            "id": _normalize_text(chunk.get("id")),
            "type": _normalize_text(chunk.get("type")),
            "model": _normalize_text(chunk.get("model")),
            "title": _normalize_text(chunk.get("title")),
            "text": text,
            "tags": chunk.get("tags") if isinstance(chunk.get("tags"), list) else [],
            "confidence": _normalize_text(chunk.get("confidence")),
            "source": chunk.get("source") if isinstance(chunk.get("source"), dict) else {},
            "related_chunks": chunk.get("related_chunks") if isinstance(chunk.get("related_chunks"), list) else [],
        }
        row["content"] = _build_content(chunk, text)
        rows.append(row)
    return rows


def export_jsonl(chunks: Iterable[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = _to_jsonl_rows(chunks)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _default_reference_path() -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    return base_dir / "docs" / "reference" / "muster_wissenskarte_v1.json"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Loader/Validator for reference knowledge map.")
    ap.add_argument("--input", help="Path to reference JSON file.")
    ap.add_argument("--validate", action="store_true", help="Validate reference JSON.")
    ap.add_argument("--export-jsonl", help="Export chunks as JSONL.")
    args = ap.parse_args(argv)

    ref_path = Path(args.input) if args.input else _default_reference_path()
    if not ref_path.exists():
        print(json.dumps({"status": "error", "message": f"File not found: {ref_path}"}, ensure_ascii=False))
        return 1

    doc = load_reference_doc(ref_path)
    errors, warnings = validate_reference_doc(doc)

    if args.validate or args.export_jsonl:
        report = {
            "file": str(ref_path),
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))

    if errors:
        return 1

    if args.export_jsonl:
        chunks = doc.get("chunks") if isinstance(doc.get("chunks"), list) else []
        export_jsonl([c for c in chunks if isinstance(c, dict)], Path(args.export_jsonl))
        print(json.dumps({"status": "ok", "exported": args.export_jsonl}, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
