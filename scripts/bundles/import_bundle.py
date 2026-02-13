"""
Bundle Import
=============

Importiert Model-Bundles für Offline-Sync
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
from typing import Any, Dict, Optional

# Add project root to path
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import settings


def verify_checksum(file_path: Path, expected_checksum: str) -> bool:
    """Verify file checksum"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)

    actual = sha256.hexdigest()
    return actual == expected_checksum


def extract_bundle(bundle_path: Path, extract_dir: Path) -> bool:
    """Extract bundle zip file"""
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            zf.extractall(extract_dir)
        return True
    except Exception as e:
        print(f"Error extracting bundle: {e}")
        return False


def load_manifest(extract_dir: Path) -> Optional[Dict[str, Any]]:
    """Load manifest from extracted bundle"""
    manifest_path = extract_dir / "manifest.json"

    if not manifest_path.exists():
        print("Error: manifest.json not found in bundle")
        return None

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading manifest: {e}")
        return None


def verify_bundle_integrity(extract_dir: Path, manifest: Dict[str, Any]) -> bool:
    """Verify all files match checksums"""
    print("Verifying bundle integrity...")

    data_dir = extract_dir / "data"
    errors = []

    for file_info in manifest.get("files", []):
        file_path = data_dir / file_info["path"]

        if not file_path.exists():
            errors.append(f"Missing file: {file_info['path']}")
            continue

        expected_checksum = file_info.get("checksum", "")
        if expected_checksum:
            if not verify_checksum(file_path, expected_checksum):
                errors.append(f"Checksum mismatch: {file_info['path']}")

    if errors:
        print("Integrity check failed:")
        for error in errors:
            print(f"  - {error}")
        return False

    print("✓ Integrity check passed")
    return True


def import_to_system(extract_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Import bundle files to system"""

    model_name = manifest.get("model_name", "unknown")
    print(f"Importing model: {model_name}")

    data_dir = extract_dir / "data"

    # Target directories
    model_target = settings.models_dir / model_name
    embeddings_target = settings.embeddings_dir / model_name

    model_target.mkdir(parents=True, exist_ok=True)
    embeddings_target.mkdir(parents=True, exist_ok=True)

    imported_count = 0
    errors = []

    for file_info in manifest.get("files", []):
        source = data_dir / file_info["path"]

        if not source.exists():
            errors.append(f"File not found: {file_info['path']}")
            continue

        # Determine target
        rel_path = file_info["path"]

        if rel_path.startswith("embeddings/"):
            target = embeddings_target / rel_path.replace("embeddings/", "")
        else:
            target = model_target / Path(rel_path).name

        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(source, target)
            imported_count += 1
            print(f"  ✓ {rel_path}")
        except Exception as e:
            errors.append(f"Failed to copy {rel_path}: {e}")

    # Try to index to Qdrant if available
    qdrant_indexed = False
    try:
        qdrant_indexed = _index_to_qdrant(model_name, embeddings_target)
    except Exception as e:
        print(f"Warning: Qdrant indexing failed: {e}")

    summary = {
        "model": model_name,
        "imported_files": imported_count,
        "total_files": len(manifest.get("files", [])),
        "errors": errors,
        "qdrant_indexed": qdrant_indexed,
    }

    return summary


def _index_to_qdrant(model_name: str, embeddings_dir: Path) -> bool:
    """Index embeddings to Qdrant (optional)"""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, PointStruct, VectorParams

        if not settings.qdrant_url:
            return False

        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

        collection_name = f"{settings.qdrant_collection}_{model_name}"

        # Read embeddings
        points = []
        point_id = 0

        for embedding_file in embeddings_dir.glob("*.jsonl"):
            with open(embedding_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)

                        if "embedding" in data and "text" in data:
                            points.append(
                                PointStruct(
                                    id=point_id,
                                    vector=data["embedding"],
                                    payload={
                                        "text": data["text"],
                                        "source_document": data.get("source_document"),
                                        "page_number": data.get("page_number"),
                                        "confidence": data.get("confidence"),
                                        **data.get("metadata", {}),
                                    },
                                )
                            )
                            point_id += 1

        if not points:
            return False

        # Create collection if not exists
        try:
            client.get_collection(collection_name)
        except Exception:
            # Create new
            vector_size = len(points[0].vector)
            client.create_collection(
                collection_name=collection_name, vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )

        # Upsert points
        client.upsert(collection_name=collection_name, points=points)

        print(f"✓ Indexed {len(points)} points to Qdrant")
        return True

    except Exception as e:
        print(f"Qdrant indexing failed: {e}")
        return False


def import_bundle(bundle_path: Path) -> Dict[str, Any]:
    """
    Import bundle from zip file

    Args:
        bundle_path: Path to bundle zip file

    Returns:
        Import summary dict
    """

    print(f"Importing bundle: {bundle_path}")

    if not bundle_path.exists():
        return {"error": f"Bundle not found: {bundle_path}"}

    # Create temp extraction directory
    bundle_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    extract_dir = settings.output_dir / "bundles" / f"import_{bundle_id}"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Extract
        if not extract_bundle(bundle_path, extract_dir):
            return {"error": "Failed to extract bundle"}

        # Load manifest
        manifest = load_manifest(extract_dir)
        if not manifest:
            return {"error": "Failed to load manifest"}

        print(f"Bundle version: {manifest.get('version')}")
        print(f"Model: {manifest.get('model_name')}")
        print(f"Files: {manifest.get('total_files')}")

        # Verify integrity
        if not verify_bundle_integrity(extract_dir, manifest):
            return {"error": "Integrity check failed"}

        # Import
        summary = import_to_system(extract_dir, manifest)

        if summary["imported_files"] == summary["total_files"]:
            print("✓ Import completed successfully")
        else:
            print(f"⚠ Import completed with errors: {len(summary['errors'])}")

        return summary

    finally:
        # Cleanup extraction directory
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Import model bundle")
    parser.add_argument("--bundle", type=str, required=True, help="Bundle zip file path")

    args = parser.parse_args()

    bundle_path = Path(args.bundle)

    result = import_bundle(bundle_path)

    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)

    print("\nImport summary:")
    print(f"  Model: {result['model']}")
    print(f"  Files imported: {result['imported_files']}/{result['total_files']}")
    print(f"  Qdrant indexed: {result['qdrant_indexed']}")

    if result["errors"]:
        print(f"  Errors: {len(result['errors'])}")
        for error in result["errors"]:
            print(f"    - {error}")

    sys.exit(0 if not result["errors"] else 1)


if __name__ == "__main__":
    main()
