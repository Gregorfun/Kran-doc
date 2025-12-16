# Datei: scripts/run_report.py
"""
Erzeugt einen Markdown-Report über den aktuellen Stand der
PDFDoc-/Kran-Tools-Wissensdatenbank.

- Liest pro Modell die Datei:
    <models_dir>/<Modell>/<Modell>_GPT51_FULL_KNOWLEDGE.json
- Summarisiert:
    - Anzahl Quell-PDFs
    - Fehlercodes (LEC)
    - SPL-Referenzen (BMK-Refs + Blatt-Refs)
    - BMK-Komponenten (UW/OW)
- Schreibt Markdown-Report nach:
    <reports_dir>/pdfdoc_report_YYYY-MM-DD_HHMMSS.md
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from scripts.config_loader import get_config

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG = get_config()

_models_dir = Path(CONFIG.models_dir)
if not _models_dir.is_absolute():
    MODELS_DIR = BASE_DIR / _models_dir
else:
    MODELS_DIR = _models_dir

_reports_dir = Path(CONFIG.reports_dir)
if not _reports_dir.is_absolute():
    REPORTS_DIR = BASE_DIR / _reports_dir
else:
    REPORTS_DIR = _reports_dir

REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        return int(str(value))
    except Exception:
        return default


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def summarize_model(model_dir: Path, model_name: str) -> Dict[str, Any]:
    """
    Liest das FULL_KNOWLEDGE eines Modells und erzeugt eine kompakte
    Zusammenfassung. Fehlt die Datei, wird eine leere Struktur geliefert.
    """
    full_file = model_dir / f"{model_name}_GPT51_FULL_KNOWLEDGE.json"
    if not full_file.exists():
        return {
            "model": model_name,
            "has_full_knowledge": False,
            "source_pdfs": 0,
            "wissen_entries": 0,
            "lec_errors": 0,
            "spl_bmk_refs": 0,
            "spl_sheet_refs": 0,
            "bmk_uw_components": 0,
            "bmk_ow_components": 0,
        }

    data = _load_json(full_file)
    base = data.get("base_module") or data.get("wissen") or data.get("knowledge") or {}

    source_pdfs = base.get("source_pdfs") or []
    if not isinstance(source_pdfs, list):
        source_pdfs = []

    wissen_entries = _safe_int(base.get("entry_count"), default=0)

    lec = data.get("lec_errors") or {}
    lec_errors = _safe_int(lec.get("error_count"), default=0)

    spl = data.get("spl_references") or {}
    spl_bmk_refs = _safe_int(spl.get("bmk_ref_count"), default=0)
    spl_sheet_refs = _safe_int(spl.get("sheet_ref_count"), default=0)

    bmk_lists = data.get("bmk_lists") or {}
    uw = bmk_lists.get("unterwagen") or {}
    ow = bmk_lists.get("oberwagen") or {}

    uw_components = _safe_int(
        uw.get("component_count") if isinstance(uw, dict) else 0,
        default=0,
    )
    ow_components = _safe_int(
        ow.get("component_count") if isinstance(ow, dict) else 0,
        default=0,
    )

    return {
        "model": model_name,
        "has_full_knowledge": True,
        "source_pdfs": len(source_pdfs),
        "wissen_entries": wissen_entries,
        "lec_errors": lec_errors,
        "spl_bmk_refs": spl_bmk_refs,
        "spl_sheet_refs": spl_sheet_refs,
        "bmk_uw_components": uw_components,
        "bmk_ow_components": ow_components,
    }


def build_run_report() -> Path:
    """
    Durchläuft alle Modell-Ordner, sammelt Statistiken
    und schreibt einen Markdown-Report.
    """
    model_summaries: List[Dict[str, Any]] = []

    if not MODELS_DIR.exists():
        print(f"MODELS_DIR existiert nicht: {MODELS_DIR}")
        # Trotzdem Report schreiben (leer)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)

    for model_dir in sorted(MODELS_DIR.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name
        summary = summarize_model(model_dir, model_name)
        model_summaries.append(summary)

    # Gesamtzahlen
    total_models = len(model_summaries)
    total_lec_errors = sum(s["lec_errors"] for s in model_summaries)
    total_bmk_uw = sum(s["bmk_uw_components"] for s in model_summaries)
    total_bmk_ow = sum(s["bmk_ow_components"] for s in model_summaries)
    total_spl_bmk = sum(s["spl_bmk_refs"] for s in model_summaries)
    total_spl_sheet = sum(s["spl_sheet_refs"] for s in model_summaries)

    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_path = REPORTS_DIR / f"pdfdoc_report_{ts}.md"

    lines: List[str] = []
    lines.append(f"# PDFDoc / Kran-Tools Report – {ts}")
    lines.append("")
    lines.append(f"- Models-Ordner: `{MODELS_DIR}`")
    lines.append(f"- Reports-Ordner: `{REPORTS_DIR}`")
    lines.append("")
    lines.append("## Übersicht")
    lines.append("")
    lines.append(f"- Anzahl Modelle: **{total_models}**")
    lines.append(f"- Gesamt Fehlercodes (LEC): **{total_lec_errors}**")
    lines.append(
        f"- Gesamt BMK-Komponenten: **{total_bmk_uw + total_bmk_ow}** "
        f"(UW: {total_bmk_uw}, OW: {total_bmk_ow})"
    )
    lines.append(
        f"- Gesamt SPL-Referenzen: **{total_spl_bmk} BMK-Refs**, "
        f"**{total_spl_sheet} Blatt-Refs**"
    )
    lines.append("")

    # Hinweis auf globale Indizes, falls vorhanden
    global_error_index = REPORTS_DIR / "global_error_index.json"
    global_bmk_index = REPORTS_DIR / "global_bmk_index.json"

    if global_error_index.exists() or global_bmk_index.exists():
        lines.append("## Globale Indizes")
        lines.append("")
        if global_error_index.exists():
            try:
                gei = _load_json(global_error_index)
                ec = _safe_int(gei.get("error_count"), 0)
                mc = _safe_int(gei.get("model_count"), 0)
                lines.append(
                    f"- Fehlercode-Index: `{global_error_index.name}` "
                    f"(Modelle: {mc}, Fehlercodes: {ec})"
                )
            except Exception as e:
                lines.append(
                    f"- Fehlercode-Index: `{global_error_index.name}` "
                    f"(Fehler beim Lesen: {e})"
                )
        if global_bmk_index.exists():
            try:
                gbi = _load_json(global_bmk_index)
                bc = _safe_int(gbi.get("bmk_count"), 0)
                mc = _safe_int(gbi.get("model_count"), 0)
                lines.append(
                    f"- BMK-Index: `{global_bmk_index.name}` "
                    f"(Modelle: {mc}, BMKs: {bc})"
                )
            except Exception as e:
                lines.append(
                    f"- BMK-Index: `{global_bmk_index.name}` "
                    f"(Fehler beim Lesen: {e})"
                )
        lines.append("")

    # Detailtabelle pro Modell
    if model_summaries:
        lines.append("## Modelle im Detail")
        lines.append("")
        lines.append(
            "| Modell | Wissensmodul | Quell-PDFs | Wissen-Einträge | "
            "Fehlercodes | BMK-Refs SPL | Blatt-Refs SPL | BMK UW | BMK OW |"
        )
        lines.append(
            "|--------|-------------|-----------:|----------------:|-----------:|"
            "-------------:|----------------:|--------:|--------:|"
        )
        for s in model_summaries:
            status = "✅" if s["has_full_knowledge"] else "⚠️"
            lines.append(
                f"| {s['model']} | {status} | {s['source_pdfs']} | "
                f"{s['wissen_entries']} | {s['lec_errors']} | "
                f"{s['spl_bmk_refs']} | {s['spl_sheet_refs']} | "
                f"{s['bmk_uw_components']} | {s['bmk_ow_components']} |"
            )
        lines.append("")
    else:
        lines.append("## Modelle im Detail")
        lines.append("")
        lines.append("_Keine Modell-Daten gefunden._")
        lines.append("")

    with report_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Report erstellt: {report_path}")
    return report_path


def main() -> None:
    print("=== RUN REPORT BUILDER ===")
    path = build_run_report()
    print(f"=== FERTIG – Report: {path} ===")


if __name__ == "__main__":
    main()
