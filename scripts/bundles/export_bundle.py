"""
Bundle Export
=============

Exportiert Model-Bundles für Offline-Sync
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import settings


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of file"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def collect_model_files(model_name: str) -> Dict[str, Path]:
    """Collect all files for a model"""
    files = {}

    model_dir = settings.models_dir / model_name
    if not model_dir.exists():
        print(f"Warning: Model directory not found: {model_dir}")
        return files

    # Knowledge file
    knowledge_file = model_dir / "FULL_KNOWLEDGE.json"
    if knowledge_file.exists():
        files["knowledge"] = knowledge_file

    # Normalized outputs
    for pattern in ["*_normalized.json", "*_lec.json", "*_bmk.json", "*_spl.json"]:
        for f in model_dir.glob(pattern):
            files[f.stem] = f

    # Embeddings
    embeddings_dir = settings.embeddings_dir / model_name
    if embeddings_dir.exists():
        for f in embeddings_dir.glob("*.jsonl"):
            files[f"embeddings/{f.name}"] = f

    return files


def create_manifest(model_name: str, files: Dict[str, Path], checksums: Dict[str, str]) -> Dict[str, Any]:
    """Create bundle manifest"""

    file_info = []
    total_size = 0

    for key, path in files.items():
        size = path.stat().st_size
        total_size += size

        file_info.append({"path": key, "size": size, "checksum": checksums.get(str(path), "")})

    manifest = {
        "version": "1.0",
        "bundle_type": "model_data",
        "model_name": model_name,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "total_files": len(files),
        "total_size": total_size,
        "files": file_info,
        "metadata": {"exporter": "kran-doc-bundle-exporter", "description": f"Bundle for {model_name}"},
    }

    return manifest


def export_bundle(model_name: str, output_path: Optional[Path] = None, compress: bool = True) -> Optional[Path]:
    """
    Export model bundle

    Args:
        model_name: Name of the model
        output_path: Output file path (default: output/bundles/<model>_bundle.zip)
        compress: Create zip file (default: True)

    Returns:
        Path to created bundle file
    """

    print(f"Exporting bundle for model: {model_name}")

    # Collect files
    files = collect_model_files(model_name)

    if not files:
        print(f"Error: No files found for model {model_name}")
        return None

    print(f"Found {len(files)} files")

    # Calculate checksums
    print("Calculating checksums...")
    checksums = {}
    for key, path in files.items():
        checksums[str(path)] = calculate_sha256(path)

    # Create manifest
    manifest = create_manifest(model_name, files, checksums)

    # Determine output path
    if output_path is None:
        bundles_dir = settings.output_dir / "bundles"
        bundles_dir.mkdir(parents=True, exist_ok=True)
        output_path = bundles_dir / f"{model_name}_bundle.zip"

    # Create bundle
    if compress:
        print(f"Creating bundle: {output_path}")

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add manifest
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # Add all files
            for key, path in files.items():
                arcname = f"data/{key}"
                if not key.startswith("embeddings/"):
                    arcname = f"data/{key}"
                else:
                    arcname = f"data/{key}"

                print(f"  Adding: {key}")
                zf.write(path, arcname)

        print(f"✓ Bundle created: {output_path}")
        print(f"  Size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

        return output_path

    else:
        # Just copy files to directory
        output_dir = output_path.with_suffix("")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write manifest
        with open(output_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Copy files
        data_dir = output_dir / "data"
        data_dir.mkdir(exist_ok=True)

        for key, path in files.items():
            target = data_dir / key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

        print(f"✓ Bundle created: {output_dir}")
        return output_dir


def list_available_models() -> List[str]:
    """List all available models"""
    models = []

    if settings.models_dir.exists():
        for item in settings.models_dir.iterdir():
            if item.is_dir():
                models.append(item.name)

    return sorted(models)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Export model bundle")
    parser.add_argument("--model", type=str, help="Model name")
    parser.add_argument("--out", type=str, help="Output path")
    parser.add_argument("--list", action="store_true", help="List available models")
    parser.add_argument("--no-compress", action="store_true", help="Do not compress")

    args = parser.parse_args()

    if args.list:
        models = list_available_models()
        print(f"Available models ({len(models)}):")
        for model in models:
            print(f"  - {model}")
        return

    if not args.model:
        print("Error: --model required")
        parser.print_help()
        sys.exit(1)

    output_path = Path(args.out) if args.out else None
    compress = not args.no_compress

    result = export_bundle(args.model, output_path, compress)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
