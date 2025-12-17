from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

# ============================================================
# Projekt-Root sicher setzen (damit imports aus /scripts und /config funktionieren)
# webapp/app.py  ->  BASE_DIR = .../kran-tools
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ----------------------------
# Optional: Config Loader
# ----------------------------
load_config = None
try:
    from config.config_loader import load_config as _load_config  # type: ignore

    load_config = _load_config  # type: ignore
except Exception:
    load_config = None  # type: ignore

# ----------------------------
# Optional: Pipeline / Parser (nur wenn vorhanden)
# ----------------------------
try:
    from scripts.merge_knowledge import merge_all_models  # type: ignore
except Exception:
    merge_all_models = None  # type: ignore

# Optional: Export für Embeddings (wenn vorhanden)
try:
    from scripts.export_for_embeddings import export as export_chunks_jsonl  # type: ignore
except Exception:
    export_chunks_jsonl = None  # type: ignore

try:
    from scripts.build_local_embedding_index import build_index as build_embedding_index  # type: ignore
except Exception:
    build_embedding_index = None  # type: ignore

try:
    from scripts.lec_parser import process_all_lec_pdfs  # type: ignore
except Exception:
    process_all_lec_pdfs = None  # type: ignore

try:
    from scripts.bmk_parser import process_all_bmk_pdfs  # type: ignore
except Exception:
    process_all_bmk_pdfs = None  # type: ignore

try:
    from scripts.spl_parser import process_all_spl_pdfs  # type: ignore
except Exception:
    process_all_spl_pdfs = None  # type: ignore

# ----------------------------
# Semantik-Index (deine semantic_index.py)
# ----------------------------
try:
    from scripts.semantic_index import has_embedding_index, search_similar  # type: ignore
except Exception:
    has_embedding_index = None  # type: ignore
    search_similar = None  # type: ignore

# ============================================================
# Konfiguration
# ============================================================

DEFAULT_LANG = "de"


@dataclass
class AppConfig:
    models_dir: str = str(BASE_DIR / "output" / "models")
    embeddings_dir: str = str(BASE_DIR / "output" / "embeddings")


def _load_app_config() -> AppConfig:
    cfg = AppConfig()
    if load_config:
        try:
            c = load_config()
            if isinstance(c, dict):
                cfg.models_dir = str(c.get("models_dir") or c.get("output_models_dir") or cfg.models_dir)
                cfg.embeddings_dir = str(c.get("embeddings_dir") or c.get("output_embeddings_dir") or cfg.embeddings_dir)
        except Exception:
            pass
    return cfg


CONFIG = _load_app_config()

app = Flask(__name__)
app.secret_key = "kran-doc-secret-key"


def get_models_dir() -> Path:
    p = Path(CONFIG.models_dir)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    return p


# ============================================================
# Text-Cleaner
# ============================================================

_CREATOR_ID_RE = re.compile(r"\blw[a-z0-9]{3,}\b", re.IGNORECASE)  # z.B. lwenep0
_LIEBHERR_RE = re.compile(r"\bliebherr\b", re.IGNORECASE)
_STOP_MARKER_RE = re.compile(r"^\s*LSB\s*Adr\b", re.IGNORECASE)
_META_LINE_RE = re.compile(r"^\s*(Ersteller|Ausgabe)\s*:\s*", re.IGNORECASE)


def _strip_bullets(s: str) -> str:
    s = s.replace("•", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_text_field(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).replace("\r", "\n").strip()
    s = _strip_bullets(s)
    s = _LIEBHERR_RE.sub("", s)
    s = _CREATOR_ID_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" -_/|")
    return s.strip()


def clean_description(value: Any, max_len: int = 220) -> str:
    """
    BMK description Cleaning:
    - Zeilen splitten
    - ab "LSB Adr" abschneiden
    - 'liebherr', 'Ersteller:', 'Ausgabe:' entfernen
    - creator IDs entfernen
    """
    if value is None:
        return ""
    raw = str(value).replace("\r", "\n").strip()
    if not raw:
        return ""

    lines = [ln.strip() for ln in raw.split("\n")]
    kept: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if _STOP_MARKER_RE.search(ln):
            break
        if _META_LINE_RE.search(ln):
            continue
        ln = _LIEBHERR_RE.sub("", ln)
        ln = _CREATOR_ID_RE.sub("", ln)
        ln = _strip_bullets(ln)
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            kept.append(ln)

    s = " ".join(kept).strip()

    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s


# ============================================================
# BMK Deutsch-Only Heuristik (weil BMK-Daten kein language/lang Feld haben)
# Fremdsprachen kommen später als Option dazu.
# ============================================================

_NON_DE_MARKERS = [
    # EN
    "resistor",
    "module",
    "angle sensor",
    "channel",
    "signal",
    "pressure",
    "temperature",
    # FR
    "module de",
    "capteur",
    "canal",
    "résistance",
    "resistance",
    "d'angle",
    "température",
    "temperature",
    "pression",
    # ES
    "módulo",
    "modulo",
    "resistencias",
    "codificador",
    "ángulo",
    "angulo",
    "canal",
    "sensor",
    # IT
    "modulo",
    "resistenza",
    "sensore",
    "canale",
    "angolo",
]

_DE_MARKERS = [
    "widerstand",
    "winkelgeber",
    "kanal",
    "geber",
    "sensor",
    "modul",
    "druck",
    "temperatur",
]


def is_probably_non_german(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False

    # Wenn eindeutig deutsche Marker vorhanden sind -> behalten
    if any(m in t for m in _DE_MARKERS):
        return False

    # Wenn eindeutig Fremdsprachen-Marker vorhanden sind -> raus
    if any(m in t for m in _NON_DE_MARKERS):
        return True

    return False


# ============================================================
# BMK Code Validierung
# ============================================================

_BMK_CODE_RE = re.compile(
    r"^(?:"
    r"[A-Z]\d{2,}(?:\.[A-Z0-9]{1,6})?\*?"
    r"|S\d{2,}\*?"
    r"|X\d{2,}\*?"
    r"|AF\d{2,}\*?"
    r"|B\d{2,}\*?"
    r")$",
    re.IGNORECASE,
)


def is_valid_bmk_code(code: str) -> bool:
    code = (code or "").strip()
    if not code:
        return False
    if _CREATOR_ID_RE.fullmatch(code):
        return False
    return bool(_BMK_CODE_RE.fullmatch(code))


def looks_like_bmk_code_query(q: str) -> bool:
    q = (q or "").strip().upper()
    if not q:
        return False
    return bool(_BMK_CODE_RE.fullmatch(q))


# ============================================================
# LSB Normalisierung / Parsing
# ============================================================

LSB_BUS_LETTER_MAP: Dict[str, int] = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
    "F": 6,
    "G": 7,
    "H": 8,
}


def normalize_lsb_key(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    m = re.search(r"LSB\s*([0-9]+)\s*[-_/ ]\s*([0-9]+)", text, re.IGNORECASE)
    if m:
        return f"LSB{int(m.group(1))}-{int(m.group(2))}"

    m = re.search(r"LSB\s*_?\s*([0-9]+)\s*_+\s*([0-9]+)", text, re.IGNORECASE)
    if m:
        return f"LSB{int(m.group(1))}-{int(m.group(2))}"

    m = re.search(r"LSB\s*([A-H])\s*(?:Teilnehmer\s*)?Adr\.?\s*([0-9]+)", text, re.IGNORECASE)
    if m:
        bus = LSB_BUS_LETTER_MAP.get(m.group(1).upper())
        if bus:
            return f"LSB{bus}-{int(m.group(2))}"

    m = re.match(r"^\s*([0-9]+)\s*[- ]\s*([0-9]+)\s*$", text)
    if m:
        return f"LSB{int(m.group(1))}-{int(m.group(2))}"

    return None


def lsb_keys_from_bmk_lsb(raw: Any) -> List[str]:
    if raw is None:
        return []

    s = str(raw).strip()
    if not s:
        return []

    m = re.match(r"^\s*([0-9]+)\s+([0-9]+)\s*[-–]\s*([0-9]+)\s*$", s)
    if m:
        bus = int(m.group(1))
        a1 = int(m.group(2))
        a2 = int(m.group(3))
        if a2 < a1:
            a1, a2 = a2, a1
        return [f"LSB{bus}-{a}" for a in range(a1, a2 + 1)]

    k = normalize_lsb_key(s)
    return [k] if k else []


# ============================================================
# FULL_KNOWLEDGE Loader & Indizes
# ============================================================

def _model_dir(model: str) -> Path:
    return get_models_dir() / model


def _find_first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists() and p.is_file():
            return p
    return None


@lru_cache(maxsize=64)
def _load_json(path: str) -> Any:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=64)
def _load_full_knowledge_model(model: str) -> Dict[str, Any]:
    mdir = _model_dir(model)
    candidate = _find_first_existing(
        [
            mdir / f"{model}_FULL_KNOWLEDGE.json",
            mdir / f"{model}_GPT51_FULL_KNOWLEDGE.json",
        ]
    )
    if not candidate:
        return {}
    try:
        data = _load_json(str(candidate))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_wagon_key(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in ("oberwagen", "ow", "upper", "uppercarriage"):
        return "oberwagen"
    if s in ("unterwagen", "uw", "lower", "undercarriage"):
        return "unterwagen"
    return s or "unknown"


def _collect_bmk_components_for_model(model: str) -> List[Dict[str, Any]]:
    components: List[Dict[str, Any]] = []
    mdir = _model_dir(model)
    ow_files = list(mdir.glob("*_BMK_OW.json"))
    uw_files = list(mdir.glob("*_BMK_UW.json"))

    for wagon, files in (("oberwagen", ow_files), ("unterwagen", uw_files)):
        for p in files:
            try:
                bm = _load_json(str(p))
                if isinstance(bm, dict) and isinstance(bm.get("components"), list):
                    for it in bm["components"]:
                        if isinstance(it, dict):
                            cc = dict(it)
                            cc.setdefault("_wagon", wagon)
                            components.append(cc)
            except Exception:
                continue

    return components


def _looks_like_lsb_query(q: str) -> Optional[str]:
    q = (q or "").strip()
    if not q:
        return None
    return normalize_lsb_key(q)


def _bmk_search_in_model(model: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Deterministische BMK-Suche:
      1) Exaktmatch BMK-Code (A81, A81.A2, S987, ...)
      2) LSB-Match (LSB2-24, 2 24, ...)
      3) Textsuche (Titel/Beschreibung enthält Query)
    """
    q = (query or "").strip()
    if not q:
        return []

    q_upper = q.upper()
    results: List[Dict[str, Any]] = []

    # LSB-Match
    lsb_key = _looks_like_lsb_query(q)
    if lsb_key:
        # Für LSB-Match nehmen wir Components direkt (keine Semantik)
        comps = _collect_bmk_components_for_model(model)
        for comp in comps:
            lang = (comp.get("lang") or "").strip().lower()
            if lang and lang != "de":
                continue
            raw_title = comp.get("title") or comp.get("name") or ""
            raw_desc = comp.get("description") or ""

            # 🔒 Deutsch-only Filter (Heuristik)
            if is_probably_non_german(str(raw_title) + " " + str(raw_desc)):
                continue

            raw_lsb = comp.get("lsb_address") or comp.get("lsb") or comp.get("lsb_key")
            keys = lsb_keys_from_bmk_lsb(raw_lsb)
            if lsb_key not in keys:
                continue

            raw_bmk = (comp.get("bmk") or comp.get("code") or comp.get("bmk_code") or "")
            bmk_code = str(raw_bmk).strip()
            if bmk_code and not is_valid_bmk_code(bmk_code):
                bmk_code = ""

            title = clean_text_field(raw_title) or clean_text_field(raw_desc)
            desc_clean = clean_description(raw_desc)

            area = clean_text_field(comp.get("area") or "")
            group = clean_text_field(comp.get("group") or "")
            wagon = clean_text_field(comp.get("wagon") or comp.get("_wagon") or "")

            display = " – ".join([p for p in [bmk_code, title] if p]).strip()
            if desc_clean and desc_clean.lower() not in (title.lower(), display.lower()):
                display = (display + f" — {desc_clean}").strip()

            meta = {
                "model": model,
                "source_type": "bmk_component",
                "bmk": bmk_code or None,
                "lsb_bmk_address": str(raw_lsb).strip() if raw_lsb else None,
                "title": title or None,
                "description": raw_desc or None,
                "description_clean": desc_clean or None,
                "sensor_name": display or None,
                "sensor_location": (area + (" / " + group if group else "")).strip() or None,
                "wagon": wagon or None,
                "raw": comp,
            }

            results.append(
                {
                    "model": model,
                    "source_type": "bmk_component",
                    "title": display or title or bmk_code or "BMK",
                    "text": desc_clean or title or "",
                    "score": 0.95,
                    "metadata": meta,
                }
            )

        return results[:limit]

    comps = _collect_bmk_components_for_model(model)
    code_query_mode = looks_like_bmk_code_query(q_upper)

    for comp in comps:
        lang = (comp.get("lang") or "").strip().lower()
        if lang and lang != "de":
            continue
        raw_title = comp.get("title") or comp.get("name") or ""
        raw_desc = comp.get("description") or ""

        # 🔒 BMK aktuell nur Deutsch anzeigen (Fremdsprachen später optional)
        if is_probably_non_german(str(raw_title) + " " + str(raw_desc)):
            continue

        raw_bmk = (comp.get("bmk") or comp.get("code") or comp.get("bmk_code") or "")
        bmk_code = str(raw_bmk).strip()
        if bmk_code and not is_valid_bmk_code(bmk_code):
            bmk_code = ""

        title = clean_text_field(raw_title) or clean_text_field(raw_desc)
        desc_clean = clean_description(raw_desc)

        area = clean_text_field(comp.get("area") or "")
        group = clean_text_field(comp.get("group") or "")
        wagon = clean_text_field(comp.get("wagon") or comp.get("_wagon") or "")

        score = 0.0
        if code_query_mode:
            if bmk_code and q_upper == bmk_code.upper():
                score = 1.0
            else:
                continue
        else:
            hay = f"{bmk_code} {title} {desc_clean} {area} {group}".upper()
            if bmk_code and q_upper == bmk_code.upper():
                score = 1.0
            elif q_upper in hay:
                score = 0.65

        if score <= 0:
            continue

        display = " – ".join([p for p in [bmk_code, title] if p]).strip()
        if desc_clean and desc_clean.lower() not in (title.lower(), display.lower()):
            display = (display + f" — {desc_clean}").strip()

        meta = {
            "model": model,
            "source_type": "bmk_component",
            "bmk": bmk_code or None,
            "lsb_bmk_address": str(comp.get("lsb_address") or comp.get("lsb") or "").strip() or None,
            "title": title or None,
            "description": raw_desc or None,
            "description_clean": desc_clean or None,
            "sensor_name": display or None,
            "sensor_location": (area + (" / " + group if group else "")).strip() or None,
            "wagon": wagon or None,
            "raw": comp,
        }

        results.append(
            {
                "model": model,
                "source_type": "bmk_component",
                "title": display or title or bmk_code or "BMK",
                "text": desc_clean or title or "",
                "score": score,
                "metadata": meta,
            }
        )

    results.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    if code_query_mode:
        return results[:1]
    return results[:limit]


def _bmk_search_all_models(query: str, model_hint: Optional[str], limit: int = 20) -> List[Dict[str, Any]]:
    models_dir = get_models_dir()
    models = [model_hint] if model_hint else [d.name for d in models_dir.iterdir() if d.is_dir()]

    out: List[Dict[str, Any]] = []
    for m in models:
        out.extend(_bmk_search_in_model(m, query, limit=limit))

    out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return out[:limit]


# ============================================================
# Systemstatus
# ============================================================

def compute_system_status() -> Dict[str, Any]:
    models_dir = get_models_dir()
    model_names: List[str] = []
    if models_dir.exists():
        model_names = sorted([d.name for d in models_dir.iterdir() if d.is_dir()])

    embedding_available = False
    try:
        if has_embedding_index:
            embedding_available = bool(has_embedding_index())
    except Exception:
        embedding_available = False

    latest_report = None
    report_dir = BASE_DIR / "output" / "reports"
    if report_dir.exists():
        reports = sorted(report_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if reports:
            latest_report = reports[0].name

    num_full_knowledge = 0
    for m in model_names:
        mdir = models_dir / m
        if (mdir / f"{m}_FULL_KNOWLEDGE.json").exists() or (mdir / f"{m}_GPT51_FULL_KNOWLEDGE.json").exists():
            num_full_knowledge += 1

    return {
        "models_dir": str(models_dir),
        "num_models": len(model_names),
        "num_full_knowledge": num_full_knowledge,
        "model_names": model_names,
        "embeddings_dir": str(Path(CONFIG.embeddings_dir)),
        "embedding_index_available": embedding_available,
        "latest_report": latest_report,
        "bmk_language_mode": "heuristic:de-only",
    }


# ============================================================
# Web-Routen
# ============================================================

@app.route("/", methods=["GET"])
def index():
    ss = compute_system_status()
    return render_template("index.html", system_status=ss, embedding_index_available=ss.get("embedding_index_available"))


@app.route("/run/pipeline")
def run_pipeline():
    try:
        if process_all_lec_pdfs:
            process_all_lec_pdfs()
        if process_all_bmk_pdfs:
            process_all_bmk_pdfs()
        if process_all_spl_pdfs:
            process_all_spl_pdfs()
        if merge_all_models:
            merge_all_models()
        if export_chunks_jsonl:
            export_chunks_jsonl()
        if build_embedding_index:
            build_embedding_index()

        flash("Pipeline erfolgreich ausgeführt.", "success")
    except Exception as e:
        flash(f"Pipeline-Fehler: {e}", "error")

    return redirect(url_for("index"))


# ============================================================
# JSON-APIs
# ============================================================

@app.route("/api/status", methods=["GET"])
def api_status():
    status = compute_system_status()
    return jsonify({"ok": True, "status": status})


@app.route("/api/search", methods=["POST"])
def api_search():
    if search_similar is None:
        return jsonify({"ok": False, "error": "Embedding-Suche nicht verfügbar (semantic_index fehlt)"}), 500

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    top_k = int(data.get("top_k") or 5)
    model = data.get("model") or None
    source_type = data.get("source_type") or None

    if not question:
        return jsonify({"ok": False, "error": "Bitte eine Frage eingeben."}), 400

    try:
        results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter=source_type)
    except TypeError:
        results = search_similar(question, top_k)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Fehler bei der Embedding-Suche: {e}"}), 500

    return jsonify({"ok": True, "results": results})


@app.route("/api/bmk_search", methods=["POST"])
def api_bmk_search():
    data = request.get_json(silent=True) or {}

    query = (data.get("query") or "").strip()
    model = data.get("model") or None
    limit = int(data.get("limit") or 10)

    if not query:
        return jsonify({"ok": False, "error": "Bitte BMK-Code oder Begriff eingeben."}), 400

    results = _bmk_search_all_models(query=query, model_hint=model, limit=limit)
    return jsonify({"ok": True, "results": results, "lang_mode": "de-only-heuristic"})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": data.get("question"),
        "result": data.get("result"),
        "note": data.get("note"),
    }

    try:
        logs_dir = BASE_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        out_path = logs_dir / "feedback.jsonl"
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        return jsonify(ok=False, error=f"Fehler beim Schreiben des Feedback-Logs: {e}")

    return jsonify(ok=True)


def main():
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
