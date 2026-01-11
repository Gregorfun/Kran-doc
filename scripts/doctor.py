from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    ok: bool
    message: str


def _fmt(ok: bool) -> str:
    return "OK" if ok else "FAIL"


def _print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _check_python_version(min_major: int = 3, min_minor: int = 11) -> CheckResult:
    v = sys.version_info
    ok = (v.major, v.minor) >= (min_major, min_minor)
    msg = f"Python {v.major}.{v.minor}.{v.micro} (min {min_major}.{min_minor})"
    return CheckResult("python_version", ok, msg)


def _load_config_yaml() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    cfg_path = BASE_DIR / "config" / "config.yaml"
    if not cfg_path.exists():
        return None, f"Fehlt: {cfg_path}"
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        return (data if isinstance(data, dict) else {}), None
    except Exception as e:
        return None, f"Konnte config.yaml nicht lesen: {e}"


def _check_paths() -> List[CheckResult]:
    results: List[CheckResult] = []

    expected_dirs = [
        BASE_DIR / "scripts",
        BASE_DIR / "webapp",
        BASE_DIR / "config",
        BASE_DIR / "input",
        BASE_DIR / "output",
    ]
    for p in expected_dirs:
        results.append(CheckResult(f"path_exists:{p.name}", p.exists(), str(p)))

    # write test for output
    out_dir = BASE_DIR / "output"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        test_file = out_dir / ".doctor_write_test.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        results.append(CheckResult("output_writeable", True, str(out_dir)))
    except Exception as e:
        results.append(CheckResult("output_writeable", False, f"{out_dir} ({e})"))

    return results


def _detect_tesseract_cmd(cfg: Optional[Dict[str, Any]]) -> Optional[str]:
    # env overrides
    for env_key in ("TESSERACT_CMD", "KRANDOC_TESSERACT_CMD", "TESSERACT_PATH"):
        v = (os.getenv(env_key) or "").strip()
        if v:
            return v

    if isinstance(cfg, dict):
        for k in ("tesseract_cmd", "tesseract", "tesseract_path"):
            v = cfg.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

        ocr_cfg = cfg.get("ocr")
        if isinstance(ocr_cfg, dict):
            v = ocr_cfg.get("tesseract_cmd") or ocr_cfg.get("tesseract_path")
            if isinstance(v, str) and v.strip():
                return v.strip()

    return None


def _check_tesseract(cfg: Optional[Dict[str, Any]], *, run_ocr: bool) -> List[CheckResult]:
    results: List[CheckResult] = []

    tess_cmd = _detect_tesseract_cmd(cfg)
    if tess_cmd:
        p = Path(tess_cmd)
        exists = p.exists() if p.suffix else True  # allow plain "tesseract" command
        results.append(CheckResult("tesseract_cmd", exists, tess_cmd))
        try:
            import pytesseract  # type: ignore

            pytesseract.pytesseract.tesseract_cmd = tess_cmd
        except Exception:
            pass
    else:
        results.append(CheckResult("tesseract_cmd", True, "(nicht gesetzt; Standard-Suche im PATH)"))

    try:
        import pytesseract  # type: ignore

        try:
            v = pytesseract.get_tesseract_version()
            results.append(CheckResult("tesseract_version", True, str(v)))
        except Exception as e:
            results.append(CheckResult("tesseract_version", False, f"Tesseract nicht erreichbar: {e}"))
            return results

        if run_ocr:
            try:
                from PIL import Image, ImageDraw  # type: ignore

                img = Image.new("RGB", (260, 80), color=(255, 255, 255))
                d = ImageDraw.Draw(img)
                d.text((10, 20), "TEST123", fill=(0, 0, 0))

                config = "--psm 7 -c tessedit_char_whitelist=TEST123"
                text = pytesseract.image_to_string(img, config=config)
                normalized = (text or "").strip().upper().replace(" ", "")

                # OCR ist naturgemäß nicht 100% stabil. Für den Doctor reicht:
                # - überhaupt Text erkannt, und
                # - erkennbar 'TES' (nicht zwingend perfekt 'TEST123')
                ok = bool(normalized) and ("TEST" in normalized or "TES" in normalized)
                results.append(
                    CheckResult(
                        "ocr_smoketest",
                        ok,
                        f"OCR='{(text or '').strip()}' (config={config})",
                    )
                )
            except Exception as e:
                results.append(CheckResult("ocr_smoketest", False, f"OCR-Test fehlgeschlagen: {e}"))
    except Exception as e:
        results.append(CheckResult("pytesseract_import", False, f"pytesseract import fehlgeschlagen: {e}"))

    return results


def _find_any_pdf() -> Optional[Path]:
    # Prefer real input PDFs
    candidates = [BASE_DIR / "input", BASE_DIR / "input" / "pdf"]
    for root in candidates:
        if not root.exists():
            continue
        for p in root.rglob("*.pdf"):
            return p
    return None


def _check_pdf_read(*, run_pdf: bool) -> List[CheckResult]:
    if not run_pdf:
        return [CheckResult("pdf_read", True, "(übersprungen)" )]

    pdf_path = _find_any_pdf()
    if not pdf_path:
        return [CheckResult("pdf_read", True, "Kein PDF gefunden (ok).")]

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        n = len(reader.pages)
        ok = n > 0
        return [CheckResult("pdf_read", ok, f"{pdf_path} ({n} Seiten)")]
    except Exception as e:
        return [CheckResult("pdf_read", False, f"Konnte PDF nicht lesen: {pdf_path} ({e})")]


def run_doctor(*, no_ocr: bool, no_pdf: bool) -> List[CheckResult]:
    results: List[CheckResult] = []

    cfg, cfg_err = _load_config_yaml()
    if cfg_err:
        results.append(CheckResult("config_yaml", False, cfg_err))
        cfg = None
    else:
        results.append(CheckResult("config_yaml", True, "config/config.yaml geladen"))

    results.append(_check_python_version())
    results.extend(_check_paths())
    results.extend(_check_tesseract(cfg, run_ocr=not no_ocr))
    results.extend(_check_pdf_read(run_pdf=not no_pdf))

    return results


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="PDFDoc Doctor: Systemcheck für OCR/PDF/Config")
    parser.add_argument("--no-ocr", action="store_true", help="OCR-Selftest überspringen")
    parser.add_argument("--no-pdf", action="store_true", help="PDF-Lese-Sanity überspringen")
    args = parser.parse_args(argv)

    _print_section("PDFDoc Doctor / Systemcheck")
    print(f"Projekt: {BASE_DIR}")

    results = run_doctor(no_ocr=args.no_ocr, no_pdf=args.no_pdf)

    _print_section("Checks")
    ok_all = True
    for r in results:
        ok_all = ok_all and r.ok
        print(f"[{_fmt(r.ok)}] {r.name}: {r.message}")

    _print_section("Ergebnis")
    if ok_all:
        print("Alles OK.")
        return 0

    print("Mindestens ein Check ist fehlgeschlagen.")
    print("Typische Fixes:")
    print("- Tesseract installieren und Pfad setzen (config/config.yaml oder env TESSERACT_CMD)")
    print("- `pip install -r requirements.txt` in der .venv")
    print("- Sicherstellen, dass input/ und output/ existieren")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
