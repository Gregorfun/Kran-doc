from __future__ import annotations

from pathlib import Path


def resolve_input_document_path(*, base_dir: str, filename: str) -> Path:
    return Path(base_dir) / "input" / filename
