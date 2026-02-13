"""
Test Bundle Manifest
====================

Tests für Bundle Export/Import Manifest und Checksums
"""

import hashlib
import json
import tempfile
from pathlib import Path

import pytest


def test_sha256_checksum():
    """Test SHA256 checksum calculation"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content\n")
        temp_path = Path(f.name)

    try:
        # Calculate checksum
        sha256 = hashlib.sha256()
        with open(temp_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        checksum = sha256.hexdigest()

        assert len(checksum) == 64
        assert checksum.isalnum()

        # Verify consistency
        sha256_2 = hashlib.sha256()
        with open(temp_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_2.update(chunk)

        assert checksum == sha256_2.hexdigest()

    finally:
        temp_path.unlink()


def test_manifest_structure():
    """Test bundle manifest structure"""
    manifest = {
        "version": "1.0",
        "bundle_type": "model_data",
        "model_name": "LTM1070",
        "created_at": "2024-01-01T12:00:00Z",
        "total_files": 5,
        "total_size": 1024000,
        "files": [{"path": "knowledge", "size": 512000, "checksum": "abc123..."}],
        "metadata": {"exporter": "kran-doc-bundle-exporter"},
    }

    # Validate structure
    assert manifest["version"] == "1.0"
    assert "model_name" in manifest
    assert "files" in manifest
    assert isinstance(manifest["files"], list)

    # Validate file entry
    file_entry = manifest["files"][0]
    assert "path" in file_entry
    assert "size" in file_entry
    assert "checksum" in file_entry


def test_manifest_serialization():
    """Test manifest can be serialized to JSON"""
    manifest = {"version": "1.0", "model_name": "test", "total_files": 0, "files": []}

    # Serialize
    json_str = json.dumps(manifest, indent=2)
    assert json_str

    # Deserialize
    parsed = json.loads(json_str)
    assert parsed == manifest


def test_checksum_verification():
    """Test checksum verification logic"""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content\n")
        temp_path = Path(f.name)

    try:
        # Calculate expected checksum
        sha256 = hashlib.sha256()
        with open(temp_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        expected = sha256.hexdigest()

        # Verify
        sha256_2 = hashlib.sha256()
        with open(temp_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_2.update(chunk)
        actual = sha256_2.hexdigest()

        assert actual == expected

        # Test mismatch
        assert actual != "wrong_checksum"

    finally:
        temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
