#!/usr/bin/env python3
"""
Test Runner - Automatisiertes Testing für Kran-Tools.

Dieses Tool bietet:
- Pytest-Integration
- Test-Discovery
- Coverage-Reports
- Performance-Tests
- Integration-Tests
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]


def run_pytest(
    test_path: Optional[str] = None,
    verbose: bool = True,
    coverage: bool = False,
    markers: Optional[str] = None,
) -> int:
    """
    Führt pytest aus.
    
    Args:
        test_path: Pfad zu Tests (None = alle Tests)
        verbose: Verbose-Output
        coverage: Coverage-Report erstellen
        markers: Pytest-Markers (z.B. "unit", "integration")
        
    Returns:
        Exit-Code von pytest
    """
    cmd = [sys.executable, "-m", "pytest"]

    if test_path:
        cmd.append(test_path)

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=scripts", "--cov=webapp", "--cov-report=html", "--cov-report=term"])

    if markers:
        cmd.extend(["-m", markers])

    print(f"Führe aus: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    return result.returncode


def discover_tests() -> List[Path]:
    """
    Entdeckt alle Test-Dateien im Projekt.
    
    Returns:
        Liste der Test-Dateien
    """
    test_files = []

    # Suche in tests/ Verzeichnis
    tests_dir = BASE_DIR / "tests"
    if tests_dir.exists():
        test_files.extend(tests_dir.glob("test_*.py"))
        test_files.extend(tests_dir.glob("**/test_*.py"))

    # Suche in scripts/ für inline-Tests
    scripts_dir = BASE_DIR / "scripts"
    if scripts_dir.exists():
        test_files.extend(scripts_dir.glob("test_*.py"))

    return sorted(test_files)


def main():
    """Hauptfunktion für Test-Runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Test-Runner für Kran-Tools")
    parser.add_argument("path", nargs="?", help="Pfad zu Tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose-Output")
    parser.add_argument("-c", "--coverage", action="store_true", help="Coverage-Report erstellen")
    parser.add_argument("-m", "--markers", help="Pytest-Markers (z.B. 'unit')")
    parser.add_argument("--discover", action="store_true", help="Entdecke Test-Dateien")

    args = parser.parse_args()

    if args.discover:
        test_files = discover_tests()
        print(f"\nGefundene Test-Dateien ({len(test_files)}):")
        for test_file in test_files:
            print(f"  - {test_file.relative_to(BASE_DIR)}")
        return 0

    return run_pytest(
        test_path=args.path,
        verbose=args.verbose,
        coverage=args.coverage,
        markers=args.markers,
    )


if __name__ == "__main__":
    sys.exit(main())
