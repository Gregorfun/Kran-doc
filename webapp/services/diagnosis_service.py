from __future__ import annotations

import re
from typing import Any, Dict, List

_DIAG_BMK_RE = re.compile(r"^(?:[AXSFBY]\d{1,4}(?:\.[A-Z0-9]{1,6})?)$", re.IGNORECASE)


def diagnosis_collect_related(tokens: List[str], target: str) -> Dict[str, List[str]]:
    groups = {"connectors": [], "fuses": [], "controllers": [], "sensors": []}
    seen = set()
    for raw in tokens:
        token = (raw or "").strip().upper()
        if not token or token == target:
            continue
        if token in seen:
            continue
        if not _DIAG_BMK_RE.fullmatch(token):
            continue
        seen.add(token)
        if token.startswith("X"):
            groups["connectors"].append(token)
        elif token.startswith("F"):
            groups["fuses"].append(token)
        elif token.startswith("A"):
            groups["controllers"].append(token)
        elif token.startswith("S"):
            groups["sensors"].append(token)
    for key in groups:
        groups[key] = sorted(groups[key])[:12]
    return groups


def build_diagnosis_path_from_spl(
    *, bmk_code: str, spl_pages: List[Dict[str, Any]], has_lec_index: bool
) -> Dict[str, Any]:
    target = (bmk_code or "").strip().upper()
    if not target or not _DIAG_BMK_RE.fullmatch(target):
        return {}

    relevant_pages: List[Dict[str, Any]] = []
    related_tokens: List[str] = []

    for page in spl_pages:
        if not isinstance(page, dict):
            continue
        tokens = page.get("tokens") or []
        tokens_norm = page.get("tokens_norm") or []
        hay_tokens = {str(token).upper() for token in tokens if token}
        hay_tokens_norm = {str(token).upper() for token in tokens_norm if token}
        text = page.get("text") or ""
        if target not in hay_tokens and target not in hay_tokens_norm and target not in text.upper():
            continue

        lines = []
        for line in str(text).splitlines():
            if target in line.upper():
                lines.append(line.strip())
            if len(lines) >= 4:
                break

        relevant_pages.append({"page": page.get("page"), "lines": lines})
        related_tokens.extend([str(token) for token in tokens])

    related = diagnosis_collect_related(related_tokens, target)
    lec_hint = "Weitere Hinweise in der LEC-Fehlerliste pruefen." if has_lec_index else ""
    knowledge_hint = "Details im Schaltplan pruefen; keine Pin-Zuordnung garantiert."

    return {
        "bmk": target,
        "spl_refs": relevant_pages,
        "related_bmks": related,
        "notes": [knowledge_hint],
        "hints": [hint for hint in [lec_hint] if hint],
    }
