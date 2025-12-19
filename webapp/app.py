from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from webapp.telegram_notify import send_telegram
from flask import Flask, flash, jsonify, redirect, render_template, render_template_string, request, session, url_for

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
try:
    from config.config_loader import load_config  # type: ignore
except Exception:
    load_config = None  # type: ignore

# ----------------------------
# Optional: Pipeline / Parser (nur wenn vorhanden)
# ----------------------------
try:
    from scripts.merge_knowledge import merge_all_models  # type: ignore
except Exception:
    merge_all_models = None  # type: ignore

# Export für Embeddings (Kompatibilität: export_chunks_jsonl oder export)
export_chunks_jsonl = None
try:
    from scripts.export_for_embeddings import export_chunks_jsonl as _export_chunks_jsonl  # type: ignore
    export_chunks_jsonl = _export_chunks_jsonl  # type: ignore
except Exception:
    try:
        from scripts.export_for_embeddings import export as _export_chunks_jsonl  # type: ignore
        export_chunks_jsonl = _export_chunks_jsonl  # type: ignore
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
app.secret_key = os.environ.get("SECRET_KEY") or os.environ.get("KRANDOC_SECRET") or "kran-doc-secret-key"
app.permanent_session_lifetime = timedelta(hours=24)
_PIN = os.environ.get("PIN_CODE") or os.environ.get("KRANDOC_PIN")


def _pin_login_required() -> bool:
    return bool(_PIN)


def _parse_pin_ok_until(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1]
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _is_authenticated() -> bool:
    if not session.get("pin_authed"):
        return False
    ok_until = _parse_pin_ok_until(session.get("pin_ok_until"))
    if not ok_until:
        return False
    return datetime.utcnow() < ok_until


def _safe_next_url(value: Optional[str]) -> str:
    if not value or not value.startswith("/"):
        return url_for("index")
    return value


def get_models_dir() -> Path:
    p = Path(CONFIG.models_dir)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    return p


# ============================================================
# Text-Cleaner
# ============================================================

_CREATOR_ID_RE = re.compile(r"\blw[a-z0-9]{3,}\b", re.IGNORECASE)  # z.B. lwenep0, lweeng1
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

    # Schutz gegen Monster-Treffer
    if len(s) > 600 or s.count("....") > 2:
        s = re.split(r"\bOriginalbild\b", s, flags=re.IGNORECASE)[0].strip()

    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s


# ============================================================
# BMK Deutsch-Only Heuristik
# ============================================================

_NON_DE_MARKERS = [
    # EN
    "resistor", "module", "angle sensor", "channel", "signal", "pressure", "temperature",
    # FR
    "module de", "capteur", "canal", "résistance", "resistance", "d'angle", "température", "pression",
    # ES
    "módulo", "modulo", "resistencias", "codificador", "ángulo", "angulo", "sensor",
    # IT
    "resistenza", "sensore", "canale", "angolo",
]

_DE_MARKERS = [
    "widerstand", "winkelgeber", "kanal", "geber", "sensor", "modul", "druck", "temperatur",
]

def is_probably_non_german(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if any(m in t for m in _DE_MARKERS):
        return False
    if any(m in t for m in _NON_DE_MARKERS):
        return True
    return False


# ============================================================
# BMK Code Validierung (filtert so etwas wie 'lwenep0')
# ============================================================

_BMK_CODE_RE = re.compile(
    r"^(?:"
    r"[A-Z]\d{2,}(?:\.[A-Z0-9]{1,6})?\*?"   # A82, A81.A2, A306*
    r"|S\d{2,}\*?"                           # S361
    r"|X\d{2,}\*?"                           # X306*
    r"|AF\d{2,}\*?"                          # AF401
    r"|B\d{2,}\*?"                           # B501
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
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
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

    m = re.search(r"Adr\.?\s*([0-9]+)\s*([0-9]+)\s*[-–]\s*([0-9]+)", text, re.IGNORECASE)
    if m:
        return f"LSB{int(m.group(2))}-{int(m.group(3))}"

    return None

def lsb_keys_from_bmk_lsb(raw: Any) -> List[str]:
    if raw is None:
        return []

    s = str(raw).strip()
    if not s:
        return []

    # "2 2 - 5"  => bus=2, adr range 2..5
    m = re.match(r"^\s*([0-9]+)\s+([0-9]+)\s*[-–]\s*([0-9]+)\s*$", s)
    if m:
        bus = int(m.group(1))
        a1 = int(m.group(2))
        a2 = int(m.group(3))
        if a2 < a1:
            a1, a2 = a2, a1
        return [f"LSB{bus}-{a}" for a in range(a1, a2 + 1)]

    # "1-8 1" => bus range 1..8, adr=1
    m = re.match(r"^\s*([0-9]+)\s*[-–]\s*([0-9]+)\s+([0-9]+)\s*$", s)
    if m:
        b1 = int(m.group(1))
        b2 = int(m.group(2))
        adr = int(m.group(3))
        if b2 < b1:
            b1, b2 = b2, b1
        return [f"LSB{b}-{adr}" for b in range(b1, b2 + 1)]

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
    candidate = _find_first_existing([
        mdir / f"{model}_FULL_KNOWLEDGE.json",
        mdir / f"{model}_GPT51_FULL_KNOWLEDGE.json",
        mdir / f"{model}_FULL_KNOWLEDGE",
        mdir / f"{model}_GPT51_FULL_KNOWLEDGE",
    ])
    if not candidate:
        return {}
    try:
        data = _load_json(str(candidate))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

@lru_cache(maxsize=64)
def _load_lec_index_for_model(model: str) -> Dict[str, Dict[str, Any]]:
    """
    Fehlercode-Direktindex (schnell & sicher):
    lädt bevorzugt *_LEC_ERRORS.json
    """
    mdir = _model_dir(model)
    p = _find_first_existing([
        mdir / f"{model}_LEC_ERRORS.json",
        mdir / f"{model}_LEC_ERRORS",
    ])
    if not p:
        return {}

    try:
        data = _load_json(str(p))
    except Exception:
        return {}

    if isinstance(data, dict) and "errors" in data and isinstance(data["errors"], list):
        errors = data["errors"]
    elif isinstance(data, list):
        errors = data
    elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        errors = data["data"]
    else:
        errors = []

    idx: Dict[str, Dict[str, Any]] = {}
    for e in errors:
        if not isinstance(e, dict):
            continue
        code = (e.get("error_code") or e.get("code") or e.get("id") or "").strip()
        if not code:
            continue
        idx[code.upper()] = e
    return idx


def _collect_bmk_components_for_model(model: str) -> List[Dict[str, Any]]:
    """
    Sammle BMK-Komponenten:
      - aus FULL_KNOWLEDGE (falls enthalten)
      - fallback: separate *_BMK_OW.json / *_BMK_UW.json
    """
    data = _load_full_knowledge_model(model) or {}
    components: List[Dict[str, Any]] = []

    raw_lists = []
    bmk_lists = data.get("bmk_lists") if isinstance(data, dict) else None
    if isinstance(bmk_lists, dict):
        for wagon_key in ("oberwagen", "unterwagen"):
            w = bmk_lists.get(wagon_key)
            if isinstance(w, dict):
                raw_lists.append((wagon_key, w))

    for key in ("bmk_components", "bmk_list", "bmk", "components"):
        v = data.get(key) if isinstance(data, dict) else None
        if isinstance(v, dict):
            raw_lists.append(("unknown", v))
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, dict):
                    cc = dict(it)
                    cc.setdefault("_wagon", it.get("wagon") or "unknown")
                    components.append(cc)

    for wagon_key, raw in raw_lists:
        if not isinstance(raw, dict):
            continue

        items: List[Any] = []
        if isinstance(raw.get("components"), list):
            items = raw["components"]
        elif isinstance(raw.get("items"), list):
            items = raw["items"]
        elif isinstance(raw.get("data"), list):
            items = raw["data"]

        for it in items:
            if isinstance(it, dict):
                cc = dict(it)
                cc["_wagon"] = wagon_key
                components.append(cc)

    # Fallback: separate BMK-Files
    mdir = _model_dir(model)
    for wagon, fname in (("oberwagen", f"{model}_BMK_OW.json"), ("unterwagen", f"{model}_BMK_UW.json")):
        p = mdir / fname
        if not p.exists():
            continue
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


@lru_cache(maxsize=64)
def _build_bmk_index_for_model(model: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Index:
      key = 'LSB2-24'
      value = Liste von BMK-Einträgen, die genau diesen Bus/Adr betreffen
    """
    components = _collect_bmk_components_for_model(model)
    index: Dict[str, List[Dict[str, Any]]] = {}

    for comp in components:
        raw_title = comp.get("title") or comp.get("name") or ""
        raw_desc = comp.get("description") or ""

        # Deutsch-only Filter (wichtig!)
        lang = (comp.get("lang") or "").strip().lower()
        if lang and lang != "de":
            continue
        if is_probably_non_german(str(raw_title) + " " + str(raw_desc)):
            continue

        raw_bmk = (comp.get("bmk") or comp.get("code") or comp.get("bmk_code") or "")
        bmk = str(raw_bmk).strip()
        if bmk and not is_valid_bmk_code(bmk):
            bmk = ""

        title = clean_text_field(raw_title) or clean_text_field(raw_desc)
        desc_clean = clean_description(raw_desc)

        area = clean_text_field(comp.get("area") or "")
        group = clean_text_field(comp.get("group") or "")
        wagon = clean_text_field(comp.get("wagon") or comp.get("_wagon") or "")

        raw_lsb = comp.get("lsb_address") or comp.get("lsb") or comp.get("lsb_key") or comp.get("lsb_bmk_address")
        keys = lsb_keys_from_bmk_lsb(raw_lsb)
        if not keys:
            continue

        location = (area + (" / " + group if group else "")).strip() or None

        entry = {
            "sensor_bmk": bmk or None,
            "sensor_title": title or None,
            "sensor_description": desc_clean or None,
            "sensor_location": location,
            "sensor_area": area or None,
            "sensor_group": group or None,
            "sensor_wagon": wagon or None,
            "lsb_bmk_address": str(raw_lsb).strip() if raw_lsb else None,
            "_raw_component": comp,
        }

        for k in keys:
            index.setdefault(k, []).append(entry)

    for k in list(index.keys()):
        index[k] = sorted(index[k], key=lambda x: ((x.get("sensor_bmk") or ""), (x.get("sensor_title") or "")))

    return index


# ============================================================
# LEC Direktmodus + Enrichment
# ============================================================

ERROR_CODE_RE = re.compile(r"\b[0-9A-F]{6}\b", re.IGNORECASE)

def _extract_error_codes(text: str) -> List[str]:
    if not text:
        return []
    return [m.group(0).upper() for m in ERROR_CODE_RE.finditer(text)]

def _is_pure_code_query(question: str, codes: List[str], source_type: Optional[str]) -> bool:
    if source_type and source_type not in ("", None, "lec_error"):
        return False
    q = (question or "").strip()
    if len(codes) != 1:
        return False
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", q)
    return cleaned.upper() == codes[0]

def _extract_lsb_key_from_error_data(err: Dict[str, Any]) -> Optional[str]:
    raw = err.get("lsb_address") or err.get("lsb")
    k = normalize_lsb_key(raw)
    if k:
        return k
    text = (err.get("long_text") or "") + "\n" + (err.get("short_text") or "")
    k = normalize_lsb_key(text)
    return k

def _direct_lec_results_for_codes(codes: List[str], model_hint: Optional[str], top_k: int = 1) -> List[Dict[str, Any]]:
    if not model_hint:
        return []

    lec_index = _load_lec_index_for_model(model_hint)
    out: List[Dict[str, Any]] = []

    for c in codes:
        err = lec_index.get(c.upper())
        if not err:
            continue
        out.append(
            {
                "model": model_hint,
                "source_type": "lec_error",
                "title": f"LEC Fehler {c}",
                "text": err.get("short_text") or "",
                "score": 1.0,
                "metadata": {
                    "model": model_hint,
                    "source_type": "lec_error",
                    "error_code": c.upper(),
                    "code": c.upper(),
                    "short_text": err.get("short_text"),
                    "long_text": err.get("long_text"),
                    "lsb_address": err.get("lsb_address") or err.get("lsb"),
                },
            }
        )

    return out[:top_k]

def _enrich_results_with_bmk(results: List[Dict[str, Any]], model_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    if not results:
        return results

    for r in results:
        meta = r.get("metadata") or {}
        r["metadata"] = meta

        source_type = r.get("source_type") or meta.get("source_type") or r.get("source") or meta.get("source")
        if source_type not in ("lec_error",):
            continue

        model = r.get("model") or meta.get("model") or model_hint
        code = meta.get("error_code") or meta.get("code")
        if not model or not code:
            continue

        lec_index = _load_lec_index_for_model(model)
        err = lec_index.get(str(code).upper())
        if not err:
            continue

        meta.setdefault("short_text", err.get("short_text"))
        meta.setdefault("long_text", err.get("long_text"))
        meta.setdefault("lsb_address", err.get("lsb_address") or err.get("lsb"))

        lsb_key = _extract_lsb_key_from_error_data(err)
        if not lsb_key:
            continue

        meta["lsb_error_key"] = lsb_key

        bmk_index = _build_bmk_index_for_model(model)
        candidates = bmk_index.get(lsb_key) or []
        if not candidates:
            continue

        # ✅ NEU: nur 1 BMK-Kandidat (deterministisch)
        best = candidates[0]

        meta["sensor_bmk"] = best.get("sensor_bmk")
        meta["sensor_title"] = best.get("sensor_title")
        meta["sensor_description"] = best.get("sensor_description")
        meta["sensor_location"] = best.get("sensor_location")
        meta["bmk_candidate_count"] = len(candidates)

        # Fürs Frontend: kompakter Anzeige-Name
        bmk_code = best.get("sensor_bmk") or ""
        title = best.get("sensor_title") or ""
        desc = best.get("sensor_description") or ""

        parts = []
        if bmk_code:
            parts.append(f"BMK {bmk_code}")
        if title:
            parts.append(title)
        display = " – ".join(parts).strip()

        if desc and desc.lower() not in (title.lower(), display.lower()):
            display = (display + f" — {desc}").strip()

        meta["sensor_name"] = display or title or desc or None

        # ALT entfernt:
        # meta["bmk_candidates"] = candidates[:5]

    return results


# ============================================================
# BMK Suche (deterministisch + LSB-Suche)
# ============================================================

def _looks_like_lsb_query(q: str) -> Optional[str]:
    q = (q or "").strip()
    if not q:
        return None
    return normalize_lsb_key(q)

def _bmk_search_in_model(model: str, query: str, limit: int = 1) -> List[Dict[str, Any]]:
    """
    Hartes Verhalten: gibt immer max. 1 Ergebnis zurück.
    """
    limit = 1
    q = (query or "").strip()
    if not q:
        return []

    q_upper = q.upper()
    results: List[Dict[str, Any]] = []

    # (1) LSB-Match schnell über Index
    lsb_key = _looks_like_lsb_query(q)
    if lsb_key:
        idx = _build_bmk_index_for_model(model)
        hits = idx.get(lsb_key, [])
        if not hits:
            return []
        h = hits[0]  # ✅ nur 1

        bmk_code = h.get("sensor_bmk") or ""
        title = h.get("sensor_title") or ""
        desc = h.get("sensor_description") or ""
        display = " – ".join([p for p in [bmk_code, title] if p]).strip()
        if desc and desc.lower() not in (title.lower(), display.lower()):
            display = (display + f" — {desc}").strip()

        meta = {
            "model": model,
            "source_type": "bmk_component",
            "bmk": bmk_code or None,
            "lsb_bmk_address": h.get("lsb_bmk_address"),
            "title": title or None,
            "description": desc or None,
            "description_clean": desc or None,
            "sensor_name": display or None,
            "sensor_location": h.get("sensor_location"),
            "lsb_key": lsb_key,
            "raw": h.get("_raw_component"),
        }
        results.append(
            {
                "model": model,
                "source_type": "bmk_component",
                "title": display or (bmk_code or "BMK"),
                "text": desc or title or "",
                "score": 0.95,
                "metadata": meta,
            }
        )
        return results[:1]

    # (2) Exaktmatch BMK-Code / Textsuche
    comps = _collect_bmk_components_for_model(model)
    code_query_mode = looks_like_bmk_code_query(q_upper)

    for comp in comps:
        raw_title = comp.get("title") or comp.get("name") or ""
        raw_desc = comp.get("description") or ""

        # Deutsch-only Filter
        lang = (comp.get("lang") or "").strip().lower()
        if lang and lang != "de":
            continue
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

        raw_lsb = comp.get("lsb_address") or comp.get("lsb") or comp.get("lsb_key")

        meta = {
            "model": model,
            "source_type": "bmk_component",
            "bmk": bmk_code or None,
            "lsb_bmk_address": str(raw_lsb).strip() if raw_lsb else None,
            "title": title or None,
            "description": (comp.get("description") or None),
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

    # Dedup + nur bestes Ergebnis
    if not results:
        return []

    results_sorted = sorted(results, key=lambda x: float(x.get("score") or 0.0), reverse=True)

    seen = set()
    for r in results_sorted:
        m = r.get("metadata") or {}
        key = (r.get("model"), (m.get("bmk") or ""), (m.get("description_clean") or ""), (m.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        return [r]  # ✅ exakt 1

    return []


def _bmk_search_all_models(query: str, model_hint: Optional[str], limit: int = 1) -> List[Dict[str, Any]]:
    """
    Hartes Verhalten: gibt immer max. 1 Ergebnis zurück (modellübergreifend).
    """
    limit = 1
    models_dir = get_models_dir()
    models = [model_hint] if model_hint else [d.name for d in models_dir.iterdir() if d.is_dir()]

    best: Optional[Dict[str, Any]] = None
    for m in models:
        hits = _bmk_search_in_model(m, query, limit=1)
        if not hits:
            continue
        cand = hits[0]
        if best is None or float(cand.get("score") or 0.0) > float(best.get("score") or 0.0):
            best = cand

        # Score 1.0 ist optimal -> direkt abbrechen
        if float(cand.get("score") or 0.0) >= 1.0:
            break

    return [best] if best else []


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
        "bmk_result_mode": "single",
    }


# ============================================================
# Web-Routen
# ============================================================

_LOGIN_TEMPLATE = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Kran-Doc Login</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
  <div class="page">
    <header class="page-header">
      <h1>Kran-Doc Login</h1>
      <p>Bitte PIN eingeben.</p>
    </header>
    <main class="page-main">
      <section class="card section">
        {% if error %}
          <p class="status-warn">{{ error }}</p>
        {% endif %}
        <form method="post" action="{{ url_for('login', next=next_param) }}">
          <label for="pin" class="field-label">PIN</label>
          <input id="pin" name="pin" type="password" autocomplete="current-password">
          <button type="submit" class="btn primary">Login</button>
        </form>
      </section>
    </main>
  </div>
</body>
</html>
"""


@app.before_request
def require_pin_login():
    if not _pin_login_required():
        return None

    path = request.path or ""
    if path == "/login" or path.startswith("/static/"):
        return None
    if _is_authenticated():
        return None
    if path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return redirect(url_for("login", next=path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not _pin_login_required():
        return redirect(url_for("index"))

    error = None
    next_param = request.args.get("next") or ""
    if next_param and not next_param.startswith("/"):
        next_param = ""

    if request.method == "POST":
        pin = (request.form.get("pin") or "").strip()
        if pin and _PIN and pin == _PIN:
            session.permanent = True
            session["pin_authed"] = True
            ok_until = datetime.utcnow() + timedelta(hours=24)
            session["pin_ok_until"] = ok_until.replace(microsecond=0).isoformat() + "Z"
            return redirect(_safe_next_url(next_param))
        error = "Falscher PIN."

    return render_template_string(_LOGIN_TEMPLATE, error=error, next_param=next_param)


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

    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    question = (data.get("question") or "").strip()
    top_k = int(data.get("top_k") or 5)
    model = data.get("model") or None
    source_type = data.get("source_type") or None

    if not question:
        return jsonify({"ok": False, "error": "Bitte eine Frage eingeben."}), 400

    # ✅ Fehlercode-Direktmodus
    requested_codes = _extract_error_codes(question)
    if _is_pure_code_query(question, requested_codes, source_type):
        results = _direct_lec_results_for_codes(requested_codes, model_hint=model, top_k=1)
        results = _enrich_results_with_bmk(results, model_hint=model)
        return jsonify({"ok": True, "results": results})

    # ✅ Normale Embedding-Suche + Enrichment
    try:
        results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter=source_type)
    except TypeError:
        results = search_similar(question, top_k)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Fehler bei der Embedding-Suche: {e}"}), 500

    results = _enrich_results_with_bmk(results, model_hint=model)
    return jsonify({"ok": True, "results": results})

@app.route("/api/bmk_search", methods=["POST"])
def api_bmk_search():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    query = (data.get("query") or "").strip()
    model = data.get("model") or None

    # ✅ limit wird bewusst ignoriert -> immer 1
    if not query:
        return jsonify({"ok": False, "error": "Bitte BMK-Code oder Begriff eingeben."}), 400

    results = _bmk_search_all_models(query=query, model_hint=model, limit=1)
    return jsonify({"ok": True, "results": results, "lang_mode": "de-only-heuristic", "result_mode": "single"})

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

        # Telegram Notify (angereichert)
        try:
            ts = payload.get("timestamp") or ""
            q = (payload.get("question") or "").strip()
            note = (payload.get("note") or "").strip()

            result = payload.get("result") or {}
            meta = (result.get("metadata") or {}) if isinstance(result, dict) else {}

            model = result.get("model") or meta.get("model") or "?"
            source = result.get("source_type") or meta.get("source_type") or "?"

            code = meta.get("code") or meta.get("error_code") or meta.get("bmk") or ""
            lsb = meta.get("lsb_error_key") or meta.get("lsb_key") or meta.get("lsb_address") or meta.get("lsb_bmk_address") or ""

            title = meta.get("title") or result.get("title") or ""
            descr = meta.get("description_clean") or meta.get("sensor_description") or meta.get("description") or ""

            msg = (
                "?? Kran-Doc Fehler-Meldung\n"
                f"Zeit: {ts}\n"
                f"Modell: {model}\n"
                f"Quelle: {source}\n"
                f"Code: {code}\n"
                f"LSB: {lsb}\n\n"
                f"Treffer: {title}\n"
                f"Beschreibung: {descr}\n\n"
                f"Frage:\n{q}\n\n"
                f"Meldung:\n{note}\n"
            )
            send_telegram(msg)
        except Exception:
            pass
    except Exception as e:
        return jsonify(ok=False, error=f"Fehler beim Schreiben des Feedback-Logs: {e}")

    return jsonify(ok=True)

def main():
    app.run(host="127.0.0.1", port=5000, debug=True)

if __name__ == "__main__":
    main()
