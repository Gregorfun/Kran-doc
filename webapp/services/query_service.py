from __future__ import annotations

import re
from typing import List, Optional

_ERROR_CODE_RE = re.compile(r"\b[0-9A-F]{6}\b", re.IGNORECASE)


def extract_error_codes(text: str) -> List[str]:
    if not text:
        return []
    return [match.group(0).upper() for match in _ERROR_CODE_RE.finditer(text)]


def is_pure_code_query(question: str, codes: List[str], source_type: Optional[str]) -> bool:
    if source_type and source_type not in ("", None, "lec_error"):
        return False
    query = (question or "").strip()
    if len(codes) != 1:
        return False
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", query)
    return cleaned.upper() == codes[0]
