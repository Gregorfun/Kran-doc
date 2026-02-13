from __future__ import annotations

import hashlib
import hmac
import json
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


def read_bundle_manifest(*, bundle_path: Path) -> Dict[str, Any] | None:
    try:
        import zipfile

        with zipfile.ZipFile(bundle_path, "r") as archive:
            with archive.open("manifest.json", "r") as file:
                payload = json.loads(file.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def validate_bundle_compatibility(*, manifest: Dict[str, Any], app_name: str, min_version: str = "1.0") -> Dict[str, Any]:
    bundle_type = str(manifest.get("bundle_type") or "")
    version = str(manifest.get("version") or "")
    compatible = bundle_type == "model_data" and bool(version)
    reasons: List[str] = []
    if bundle_type != "model_data":
        reasons.append("Unsupported bundle_type")
    if not version:
        reasons.append("Missing version")

    return {
        "compatible": compatible,
        "app_name": app_name,
        "required_min_version": min_version,
        "bundle_version": version,
        "reasons": reasons,
    }


def compute_bundle_signature(*, bundle_path: Path, secret: str) -> str:
    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    return hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_bundle_signature(*, bundle_path: Path, secret: str, provided_signature: str) -> bool:
    if not secret or not provided_signature:
        return False
    expected = compute_bundle_signature(bundle_path=bundle_path, secret=secret)
    return hmac.compare_digest(expected, provided_signature)
