from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def prepare_temp_bundle_path(*, base_dir: str, filename: str, sanitize_filename: Any) -> Path:
    temp_dir = Path(base_dir) / "output" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = sanitize_filename(filename)
    return temp_dir / safe_filename


def cleanup_temp_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def list_bundles(*, bundles_dir: Path) -> List[Dict[str, Any]]:
    if not bundles_dir.exists():
        return []

    bundles: List[Dict[str, Any]] = []
    for bundle_file in bundles_dir.glob("*.zip"):
        bundles.append(
            {
                "name": bundle_file.name,
                "size": bundle_file.stat().st_size,
                "created": bundle_file.stat().st_mtime,
            }
        )
    return bundles
