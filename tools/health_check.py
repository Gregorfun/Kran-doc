#!/usr/bin/env python3
"""
Health Check - System-Gesundheitsüberwachung für Kran-Tools.

Dieses Tool bietet:
- System-Status-Checks
- Ressourcen-Monitoring
- Dependency-Checks
- Health-Report
"""

from __future__ import annotations

import json
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass
class HealthCheckResult:
    """Ergebnis eines Health-Checks."""

    name: str
    status: str  # "ok", "warning", "error"
    message: str
    details: Optional[Dict[str, Any]] = None


class HealthChecker:
    """
    System-Gesundheitsüberwachung.
    
    Verwendung:
        checker = HealthChecker()
        results = checker.run_all_checks()
        checker.print_report()
    """

    def __init__(self):
        self.results: List[HealthCheckResult] = []

    def check_python_version(self) -> HealthCheckResult:
        """Prüft Python-Version."""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"

        if version >= (3, 8):
            return HealthCheckResult(
                name="Python-Version",
                status="ok",
                message=f"Python {version_str} ist installiert",
                details={"version": version_str, "executable": sys.executable},
            )
        else:
            return HealthCheckResult(
                name="Python-Version",
                status="error",
                message=f"Python {version_str} ist zu alt (mindestens 3.8 erforderlich)",
                details={"version": version_str},
            )

    def check_dependencies(self) -> HealthCheckResult:
        """Prüft kritische Dependencies."""
        required_packages = ["flask", "pypdf", "yaml", "PIL"]
        missing = []
        installed = []

        for package in required_packages:
            try:
                __import__(package)
                installed.append(package)
            except ImportError:
                missing.append(package)

        if not missing:
            return HealthCheckResult(
                name="Dependencies",
                status="ok",
                message=f"Alle {len(installed)} kritischen Packages installiert",
                details={"installed": installed},
            )
        else:
            return HealthCheckResult(
                name="Dependencies",
                status="error",
                message=f"{len(missing)} Package(s) fehlen: {', '.join(missing)}",
                details={"missing": missing, "installed": installed},
            )

    def check_directories(self) -> HealthCheckResult:
        """Prüft wichtige Verzeichnisse."""
        required_dirs = ["scripts", "webapp", "config", "tools"]
        missing = []
        existing = []

        for dir_name in required_dirs:
            dir_path = BASE_DIR / dir_name
            if dir_path.exists():
                existing.append(dir_name)
            else:
                missing.append(dir_name)

        if not missing:
            return HealthCheckResult(
                name="Verzeichnisse",
                status="ok",
                message=f"Alle {len(existing)} wichtigen Verzeichnisse vorhanden",
                details={"existing": existing},
            )
        else:
            return HealthCheckResult(
                name="Verzeichnisse",
                status="warning",
                message=f"{len(missing)} Verzeichnis(se) fehlen: {', '.join(missing)}",
                details={"missing": missing, "existing": existing},
            )

    def check_disk_space(self) -> HealthCheckResult:
        """Prüft Festplattenspeicher."""
        try:
            usage = shutil.disk_usage(BASE_DIR)
            free_gb = usage.free / (1024**3)
            percent_used = (usage.used / usage.total) * 100

            if free_gb > 5:
                status = "ok"
                message = f"{free_gb:.1f} GB frei ({percent_used:.1f}% belegt)"
            elif free_gb > 1:
                status = "warning"
                message = f"Nur noch {free_gb:.1f} GB frei ({percent_used:.1f}% belegt)"
            else:
                status = "error"
                message = f"Kritisch: Nur noch {free_gb:.1f} GB frei ({percent_used:.1f}% belegt)"

            return HealthCheckResult(
                name="Festplattenspeicher",
                status=status,
                message=message,
                details={"free_gb": free_gb, "total_gb": usage.total / (1024**3), "percent_used": percent_used},
            )

        except Exception as e:
            return HealthCheckResult(
                name="Festplattenspeicher",
                status="error",
                message=f"Fehler beim Prüfen: {e}",
            )

    def check_memory(self) -> HealthCheckResult:
        """Prüft verfügbaren Arbeitsspeicher."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)
            percent_used = memory.percent

            if available_gb > 2:
                status = "ok"
                message = f"{available_gb:.1f} GB verfügbar ({percent_used:.1f}% belegt)"
            elif available_gb > 0.5:
                status = "warning"
                message = f"Nur noch {available_gb:.1f} GB verfügbar ({percent_used:.1f}% belegt)"
            else:
                status = "error"
                message = f"Kritisch: Nur noch {available_gb:.1f} GB verfügbar ({percent_used:.1f}% belegt)"

            return HealthCheckResult(
                name="Arbeitsspeicher",
                status=status,
                message=message,
                details={"available_gb": available_gb, "total_gb": memory.total / (1024**3), "percent_used": percent_used},
            )

        except ImportError:
            return HealthCheckResult(
                name="Arbeitsspeicher",
                status="warning",
                message="psutil nicht installiert, Speicher-Check übersprungen",
            )

    def check_tesseract(self) -> HealthCheckResult:
        """Prüft Tesseract OCR."""
        try:
            import pytesseract

            version = pytesseract.get_tesseract_version()
            return HealthCheckResult(
                name="Tesseract OCR",
                status="ok",
                message=f"Tesseract {version} verfügbar",
                details={"version": str(version)},
            )

        except Exception as e:
            return HealthCheckResult(
                name="Tesseract OCR",
                status="warning",
                message="Tesseract nicht verfügbar (OCR-Funktionen deaktiviert)",
                details={"error": str(e)},
            )

    def run_all_checks(self) -> List[HealthCheckResult]:
        """
        Führt alle Health-Checks aus.
        
        Returns:
            Liste der Ergebnisse
        """
        self.results = [
            self.check_python_version(),
            self.check_dependencies(),
            self.check_directories(),
            self.check_disk_space(),
            self.check_memory(),
            self.check_tesseract(),
        ]

        return self.results

    def print_report(self):
        """Gibt einen formatierten Health-Report aus."""
        if not self.results:
            self.run_all_checks()

        print("\n" + "=" * 80)
        print("SYSTEM HEALTH CHECK")
        print("=" * 80)
        print(f"Zeitpunkt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version.split()[0]}")
        print("=" * 80 + "\n")

        # Status-Symbole
        status_icons = {"ok": "✓", "warning": "⚠", "error": "✗"}

        for result in self.results:
            icon = status_icons.get(result.status, "?")
            print(f"[{icon}] {result.name}: {result.message}")

        print("\n" + "=" * 80)

        # Zusammenfassung
        ok_count = sum(1 for r in self.results if r.status == "ok")
        warning_count = sum(1 for r in self.results if r.status == "warning")
        error_count = sum(1 for r in self.results if r.status == "error")

        print(f"Zusammenfassung: {ok_count} OK, {warning_count} Warnungen, {error_count} Fehler")
        print("=" * 80 + "\n")

    def save_report(self, output_path: Path):
        """
        Speichert den Health-Report als JSON.
        
        Args:
            output_path: Ausgabepfad
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "platform": {"system": platform.system(), "release": platform.release(), "python": sys.version.split()[0]},
            "results": [asdict(r) for r in self.results],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print(f"Health-Report gespeichert: {output_path}")


def main():
    """Hauptfunktion für Health-Check."""
    import argparse

    parser = argparse.ArgumentParser(description="System Health Check für Kran-Tools")
    parser.add_argument("-o", "--output", help="Speichere Report als JSON")
    parser.add_argument("--json", action="store_true", help="Ausgabe als JSON")

    args = parser.parse_args()

    checker = HealthChecker()
    checker.run_all_checks()

    if args.json:
        report = {
            "results": [asdict(r) for r in checker.results],
        }
        print(json.dumps(report, indent=2))
    else:
        checker.print_report()

    if args.output:
        checker.save_report(Path(args.output))

    # Exit-Code basierend auf Ergebnissen
    has_errors = any(r.status == "error" for r in checker.results)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
