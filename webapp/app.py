from __future__ import annotations

import json
import os
import re
import sys
# --- NEW ---
import hashlib
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Dict, List, Optional
from webapp.telegram_notify import send_telegram
from flask import Flask, flash, jsonify, redirect, render_template, render_template_string, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

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

@app.after_request
def set_charset(response):
    ct = response.headers.get("Content-Type", "")
    if "text/html" in ct or ct == "":
        response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response

# ============================================================
# Community-Storage (JSON, MVP)
# ============================================================

COMMUNITY_DIR = BASE_DIR / "community"
USERS_PATH = COMMUNITY_DIR / "users.json"
SOLUTIONS_PATH = COMMUNITY_DIR / "solutions.json"
_community_lock = threading.Lock()

def _utc_now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)

def _format_ts(dt: Optional[datetime] = None) -> str:
    value = dt or _utc_now()
    return value.isoformat() + "Z"

def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1]
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None

def load_json_file(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json_atomic(path: Path, data: Any) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp_path.replace(path)

def _ensure_community_storage() -> None:
    COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_PATH.exists():
        save_json_atomic(USERS_PATH, [])
    if not SOLUTIONS_PATH.exists():
        save_json_atomic(SOLUTIONS_PATH, [])

def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()

def _normalize_model(value: str) -> str:
    return (value or "").strip()

def _normalize_error_code(value: str) -> str:
    return (value or "").strip().upper()

def _user_status(user: Optional[Dict[str, Any]]) -> str:
    if not user:
        return "unknown"
    status = (user.get("status") or "").strip().lower()
    if not status:
        return "approved" if user.get("role") == "admin" else "approved"
    return status

def _solution_status(solution: Dict[str, Any]) -> str:
    status = (solution.get("status") or "").strip().lower()
    return status or "approved"

def _split_lines(value: str) -> List[str]:
    if not value:
        return []
    lines = [ln.strip() for ln in value.replace("\r", "\n").split("\n")]
    return [ln for ln in lines if ln]

def _generate_pseudonym(existing: set[str]) -> str:
    for _ in range(20):
        suffix = secrets.randbelow(9000) + 1000
        name = f"KranFuchs-{suffix}"
        if name not in existing:
            return name
    return f"KranFuchs-{uuid.uuid4().hex[:6]}"

def _load_users() -> List[Dict[str, Any]]:
    with _community_lock:
        data = load_json_file(USERS_PATH, [])
    return data if isinstance(data, list) else []

def _save_users(users: List[Dict[str, Any]]) -> None:
    with _community_lock:
        save_json_atomic(USERS_PATH, users)

def _load_solutions() -> List[Dict[str, Any]]:
    with _community_lock:
        data = load_json_file(SOLUTIONS_PATH, [])
    return data if isinstance(data, list) else []

def _save_solutions(solutions: List[Dict[str, Any]]) -> None:
    with _community_lock:
        save_json_atomic(SOLUTIONS_PATH, solutions)

def _find_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    target = _normalize_email(email)
    for u in _load_users():
        if _normalize_email(u.get("email") or "") == target:
            return u
    return None

def _find_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    for u in _load_users():
        if u.get("user_id") == user_id:
            return u
    return None

def _seed_admin_if_needed() -> None:
    users = _load_users()
    admin_email = os.environ.get("KRANDOC_ADMIN_EMAIL") or ""
    admin_password = os.environ.get("KRANDOC_ADMIN_PASSWORD") or ""
    target_email = _normalize_email(admin_email) if admin_email else ""

    if target_email and _find_user_by_email(target_email):
        return

    if users:
        if target_email and admin_password:
            admin_user = {
                "user_id": uuid.uuid4().hex,
                "email": target_email,
                "password_hash": generate_password_hash(admin_password),
                "role": "admin",
                "status": "approved",
                "display_name": "Admin",
                "display_mode": "custom",
                "real_name": "",
                "created_at": _format_ts(),
                "reviewed_by": None,
                "reviewed_at": None,
                "decision_note": None,
            }
            users.append(admin_user)
            _save_users(users)
            print("[KRAN-DOC] Admin-Account aus ENV erstellt.")
        return

    default_email = target_email or "admin@local"
    default_password = admin_password or "admin123"
    admin_user = {
        "user_id": uuid.uuid4().hex,
        "email": default_email,
        "password_hash": generate_password_hash(default_password),
        "role": "admin",
        "status": "approved",
        "display_name": "Admin",
        "display_mode": "custom",
        "real_name": "",
        "created_at": _format_ts(),
        "reviewed_by": None,
        "reviewed_at": None,
        "decision_note": None,
    }
    users.append(admin_user)
    _save_users(users)
    print("[KRAN-DOC] Admin-Seed erstellt: email=%s pass=%s (bitte ändern)" % (default_email, default_password))

def _current_user() -> Optional[Dict[str, Any]]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return _find_user_by_id(user_id)

def _login_user(user: Dict[str, Any]) -> None:
    session.permanent = True
    session["user_id"] = user.get("user_id")

def _logout_user() -> None:
    session.pop("user_id", None)

def _login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not _current_user():
            flash("Bitte zuerst einloggen.", "error")
            return redirect(url_for("account_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def _admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user or user.get("role") != "admin":
            flash("Admin-Rechte erforderlich.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper

def _user_submission_count(user_id: str, since: datetime) -> int:
    count = 0
    for s in _load_solutions():
        if s.get("created_by") != user_id:
            continue
        created_at = _parse_ts(s.get("created_at"))
        if created_at and created_at >= since:
            count += 1
    return count

def _telegram_configured() -> bool:
    token = os.getenv("KRANDOC_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("KRANDOC_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
    return bool((token or "").strip() and (chat_id or "").strip())

_ensure_community_storage()
_seed_admin_if_needed()


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

def _full_lsb_address(err: Dict[str, Any]) -> Optional[str]:
    raw = err.get("raw_block") or ""
    if not raw:
        return None
    first = str(raw).splitlines()[0].strip()
    if not first:
        return None
    return first

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

_EXPLAIN_CACHE = {}

def _explain_paths_for_model(model: Optional[str]) -> List[Path]:
    paths: List[Path] = []
    if model:
        paths.append(BASE_DIR / "output" / "models" / model / "explain_catalog.json")
    paths.append(BASE_DIR / "output" / "explain_catalog_all.json")
    return paths

def _load_explain_catalog(model: Optional[str]) -> Dict[str, Any]:
    key = model or "__all__"
    if key in _EXPLAIN_CACHE:
        return _EXPLAIN_CACHE[key]
    for p in _explain_paths_for_model(model):
        try:
            if p.exists():
                with p.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    _EXPLAIN_CACHE[key] = data
                    return data
        except Exception:
            continue
    _EXPLAIN_CACHE[key] = {}
    return {}

def _extract_error_code_from_result(r: Dict[str, Any]) -> Optional[str]:
    meta = r.get("metadata") or {}
    candidates = [
        meta.get("error_code"),
        meta.get("code"),
        meta.get("bmk"),
        meta.get("id"),
        r.get("error_code"),
        r.get("code"),
        r.get("bmk"),
    ]
    for c in candidates:
        if not c:
            continue
        s = str(c).strip().upper()
        if 4 <= len(s) <= 8 and all(ch in "0123456789ABCDEF" for ch in s):
            return s
    return None

def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts: List[str] = []
        for k, v in value.items():
            if v is None:
                continue
            key = str(k).strip()
            val = _flatten_text(v).strip()
            if not val:
                continue
            if key:
                parts.append(f"{key}: {val}")
            else:
                parts.append(val)
        return " ".join(parts).strip()
    if isinstance(value, (list, tuple, set)):
        parts = [p for p in (_flatten_text(v).strip() for v in value) if p]
        return " ".join(parts).strip()
    return str(value).strip()

def _extract_explain_text(result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return ""
    explain = result.get("explain")
    if explain:
        return _flatten_text(explain).strip()
    meta = result.get("metadata") or {}
    if isinstance(meta, dict):
        explain = meta.get("explain")
        if explain:
            return _flatten_text(explain).strip()
    return ""

def _meta_to_text(meta: Any) -> str:
    if not isinstance(meta, dict):
        return ""
    return _flatten_text(meta).strip()

def classify_traffic_light(explain_text: str, meta: dict) -> Dict[str, str]:
    text = (explain_text or "").lower()
    meta_text = _meta_to_text(meta).lower()

    red_keywords = [
        "kritisch", "sofort", "not-aus", "not aus", "abschalten", "stop", "brand", "überhitz",
        "kurzschluss", "hydraulikdruck", "druck zu hoch", "brems", "lenkung", "ausfall sicherheit",
        "sicherheitsrelevant",
    ]
    yellow_keywords = [
        "warnung", "kommunikation", "can", "lsb", "datenbus", "sporadisch", "wackler",
        "teilnehmer offline", "telegramm", "feuchtigkeit", "korrosion", "kontaktproblem",
        "leitung", "abschirmung",
    ]

    def _find_match(hay: str, keywords: List[str]) -> Optional[str]:
        for kw in keywords:
            if kw in hay:
                return kw
        return None

    red_match = _find_match(text, red_keywords) or _find_match(meta_text, red_keywords)
    if red_match:
        return {
            "traffic": "red",
            "traffic_label": "KRITISCH",
            "traffic_advice": "Betrieb stoppen bzw. sofort prüfen. Fehler kann Folgeschäden verursachen.",
            "traffic_reason": red_match,
        }

    yellow_match = _find_match(text, yellow_keywords) or _find_match(meta_text, yellow_keywords)
    if yellow_match:
        return {
            "traffic": "yellow",
            "traffic_label": "WARNUNG",
            "traffic_advice": "Weiterbetrieb möglich, aber zeitnah prüfen / Service planen.",
            "traffic_reason": yellow_match,
        }

    return {
        "traffic": "green",
        "traffic_label": "OK",
        "traffic_advice": "Weiterbetrieb möglich. Beobachten.",
    }

def _attach_explain(results: List[Any], model: Optional[str]) -> List[Any]:
    catalog = _load_explain_catalog(model)
    if not catalog:
        return results
    for r in results or []:
        try:
            if isinstance(r, dict) and "explain" not in r:
                code = _extract_error_code_from_result(r)
                if code and code in catalog:
                    explain_data = catalog[code]
                    if "metadata" not in r or not isinstance(r.get("metadata"), dict):
                        r["metadata"] = {}
                    if isinstance(explain_data, dict):
                        r["metadata"].update(explain_data)
                    else:
                        r["metadata"].update({"explain": explain_data})
                    r["explain"] = explain_data
        except Exception:
            continue
    return results

def _attach_traffic_light(results: List[Any]) -> List[Any]:
    for r in results or []:
        if not isinstance(r, dict):
            continue
        explain_text = _extract_explain_text(r)
        if not explain_text:
            continue
        meta = r.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        traffic = classify_traffic_light(explain_text, meta)
        r["traffic_light"] = traffic
        if "metadata" not in r or not isinstance(r.get("metadata"), dict):
            r["metadata"] = {}
        r["metadata"]["traffic_light"] = traffic
    return results

# --- NEW ---
def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)

# --- NEW ---
def _result_dedupe_key(result: Dict[str, Any]) -> str:
    meta = result.get("metadata") or {}
    meta_id = meta.get("id")
    if meta_id:
        return f"id:{meta_id}"
    title = _safe_str(meta.get("title") or result.get("title") or "")
    text = _safe_str(result.get("text") or result.get("chunk") or "")
    payload = (title + "\n" + text).strip()
    return "hash:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()

# --- NEW ---
def _dedupe_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        key = _result_dedupe_key(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

# --- NEW ---
def _search_general(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    if search_similar is None:
        return []
    # --- NEW ---
    top_k = max(2, min(int(top_k or 3), 4))
    # --- NEW ---
    candidates_k = min(80, max(40, int(top_k) * 10))
    try:
        # --- NEW ---
        results = search_similar(query, top_k=candidates_k, model_filter="general", source_type_filter=None)
    except TypeError:
        # --- NEW ---
        results = search_similar(query, candidates_k)
    except Exception:
        return []
    filtered: List[Dict[str, Any]] = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        # --- NEW ---
        meta = r.get("metadata") or {}
        # --- NEW ---
        layer = None
        # --- NEW ---
        if isinstance(meta, dict):
            # --- NEW ---
            layer = meta.get("layer")
            # --- NEW ---
            nested = meta.get("metadata") if layer is None else None
            # --- NEW ---
            if isinstance(nested, dict):
                # --- NEW ---
                layer = nested.get("layer")
                # --- NEW ---
                if layer is not None:
                    # --- NEW ---
                    r["metadata"] = nested
        # --- NEW ---
        if layer == "liccon_general":
            # --- NEW ---
            # Friendly labels for UI (avoid showing "general · UNKNOWN")
            # --- NEW ---
            r2 = dict(r)
            # --- NEW ---
            meta2 = dict(meta)
            # --- NEW ---
            r2["model"] = "Frage / Antwort"
            # --- NEW ---
            # Normalize source_type label
            # --- NEW ---
            st = r2.get("source_type") or meta2.get("source_type") or "Diagnose"
            # --- NEW ---
            if not st or st == "UNKNOWN":
                # --- NEW ---
                st = "Antwort"
            # --- NEW ---
            r2["source_type"] = st
            # --- NEW ---
            meta2["model"] = "Frage / Antwort"
            # --- NEW ---
            if not meta2.get("source_type") or meta2.get("source_type") == "UNKNOWN":
                # --- NEW ---
                meta2["source_type"] = "antwort"
            # --- NEW ---
            r2["metadata"] = meta2
            # --- NEW ---
            filtered.append(r2)
    return filtered[:top_k]
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


@lru_cache(maxsize=64)
def _load_ersatzteile_for_model(model: str) -> Optional[Dict[str, Any]]:
    mdir = _model_dir(model)
    p = mdir / "ersatzteile.json"
    if not p.exists():
        return None
    try:
        data = _load_json(str(p))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


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
        lsb_address = _full_lsb_address(err) or err.get("lsb_address") or err.get("lsb")
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
                    "lsb_address": lsb_address,
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
        full_lsb = _full_lsb_address(err)
        if full_lsb:
            current_lsb = meta.get("lsb_address")
            if not current_lsb or (full_lsb.startswith(str(current_lsb)) and len(str(current_lsb)) < len(full_lsb)):
                meta["lsb_address"] = full_lsb

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

@app.context_processor
def inject_current_user():
    user = _current_user()
    return {
        "current_user": user,
        "is_admin": bool(user and user.get("role") == "admin"),
        "current_user_status": _user_status(user) if user else None,
    }

@app.before_request
def require_pin_login():
    if not _pin_login_required():
        return None

    path = request.path or ""
    if path in ("/login", "/contact") or path.startswith("/static/"):
        return None
    if _is_authenticated():
        return None
    if path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return redirect(url_for("login", next=path))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not _pin_login_required():
        return redirect(url_for("account_login", next=request.args.get("next") or ""))

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

    return render_template("login.html", error=error, next_param=next_param)


@app.route("/account/login", methods=["GET", "POST"])
def account_login():
    next_param = request.form.get("next") or request.args.get("next") or ""
    if next_param and not next_param.startswith("/"):
        next_param = ""

    error = None
    if request.method == "POST":
        email = _normalize_email(request.form.get("email") or "")
        password = request.form.get("password") or ""
        user = _find_user_by_email(email)
        if not user or not check_password_hash(user.get("password_hash") or "", password):
            error = "Login fehlgeschlagen. Bitte prüfen."
        else:
            status = _user_status(user)
            if status == "rejected":
                note = (user.get("decision_note") or "").strip()
                if note:
                    error = f"Account abgelehnt. Grund: {note}"
                else:
                    error = "Account abgelehnt."
            else:
                _login_user(user)
                if status != "approved":
                    flash("Dein Account wartet auf Freigabe. Du kannst noch keine Lösungen posten.", "error")
                else:
                    flash("Login erfolgreich.", "success")
                return redirect(_safe_next_url(next_param))

    return render_template("auth/login.html", error=error, next_param=next_param)


@app.route("/account/register", methods=["GET", "POST"])
def account_register():
    next_param = request.form.get("next") or request.args.get("next") or ""
    if next_param and not next_param.startswith("/"):
        next_param = ""

    error = None
    if request.method == "POST":
        email = _normalize_email(request.form.get("email") or "")
        password = request.form.get("password") or ""
        display_name_input = (request.form.get("display_name") or "").strip()
        real_name = (request.form.get("real_name") or "").strip()

        if not email or "@" not in email:
            error = "Bitte eine gueltige Email angeben."
        elif not password or len(password) < 6:
            error = "Passwort muss mindestens 6 Zeichen lang sein."
        elif _find_user_by_email(email):
            error = "Email ist bereits registriert."
        else:
            users = _load_users()
            existing_names = {u.get("display_name") for u in users if u.get("display_name")}
            if display_name_input:
                display_name = display_name_input
                display_mode = "custom"
            else:
                display_name = _generate_pseudonym(existing_names)
                display_mode = "auto"

            user = {
                "user_id": uuid.uuid4().hex,
                "email": email,
                "password_hash": generate_password_hash(password),
                "role": "user",
                "status": "pending",
                "display_name": display_name,
                "display_mode": display_mode,
                "real_name": real_name,
                "created_at": _format_ts(),
                "reviewed_by": None,
                "reviewed_at": None,
                "decision_note": None,
            }
            users.append(user)
            _save_users(users)

            if _telegram_configured():
                try:
                    send_telegram(f"🆕 Neuer User pending: {display_name} ({email})")
                except Exception:
                    pass

            _login_user(user)
            flash("Registrierung erfolgreich. Dein Account wartet auf Freigabe.", "success")
            return redirect(_safe_next_url(next_param or url_for("index")))

    return render_template("auth/register.html", error=error, next_param=next_param)


@app.route("/account/logout", methods=["POST"])
def account_logout():
    _logout_user()
    flash("Logout erfolgreich.", "success")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    return account_register()


@app.route("/logout", methods=["POST"])
def logout():
    return account_logout()


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
# Community-Routen
# ============================================================

def _filter_approved_solutions(model: str, error_code: str) -> List[Dict[str, Any]]:
    solutions = [
        s for s in _load_solutions()
        if _solution_status(s) == "approved" and _normalize_error_code(s.get("error_code") or "") == error_code
    ]
    if model:
        exact = [s for s in solutions if _normalize_model(s.get("model") or "") == model]
        if exact:
            return exact
    return solutions

@app.route("/community/solutions/<path:model>/<path:error_code>")
def community_solutions(model: str, error_code: str):
    model_norm = _normalize_model(model)
    error_norm = _normalize_error_code(error_code)
    solutions = _filter_approved_solutions(model_norm, error_norm)
    return render_template(
        "community_solutions.html",
        model=model_norm,
        error_code=error_norm,
        solutions=solutions,
    )

@app.route("/community/submit", methods=["GET", "POST"])
@_login_required
def community_submit():
    user = _current_user()
    if not user:
        return redirect(url_for("account_login"))

    status = _user_status(user)
    if status != "approved":
        if status == "pending":
            flash("Dein Account wartet auf Freigabe. Du kannst noch keine Lösungen posten.", "error")
        elif status == "rejected":
            flash("Dein Account wurde abgelehnt. Du kannst keine Lösungen posten.", "error")
        else:
            flash("Dein Account ist nicht freigegeben.", "error")
        return redirect(url_for("index"))

    prefill_model = _normalize_model(request.args.get("model") or "")
    prefill_code = _normalize_error_code(request.args.get("error_code") or "")

    error = None
    if request.method == "POST":
        model = _normalize_model(request.form.get("model") or "")
        error_code = _normalize_error_code(request.form.get("error_code") or "")
        title = (request.form.get("title") or "").strip()
        symptom = (request.form.get("symptom") or "").strip()
        cause = (request.form.get("cause") or "").strip()
        fix_steps = _split_lines(request.form.get("fix_steps") or "")
        parts_tools = _split_lines(request.form.get("parts_tools") or "")
        safety_note = (request.form.get("safety_note") or "").strip()

        if not model:
            error = "Modell ist erforderlich."
        elif not error_code:
            error = "Fehlercode ist erforderlich."
        elif not title:
            error = "Titel ist erforderlich."
        elif not symptom:
            error = "Symptom ist erforderlich."
        elif not cause:
            error = "Ursache ist erforderlich."
        elif not fix_steps:
            error = "Mindestens ein Schritt ist erforderlich."
        else:
            since = _utc_now() - timedelta(hours=24)
            if _user_submission_count(user.get("user_id"), since) >= 3:
                error = "Limit erreicht: max. 3 Einsendungen pro 24h."

        if not error:
            solutions = _load_solutions()
            payload = {
                "solution_id": uuid.uuid4().hex,
                "model": model,
                "error_code": error_code,
                "title": title,
                "symptom": symptom,
                "cause": cause,
                "fix_steps": fix_steps,
                "parts_tools": parts_tools,
                "safety_note": safety_note,
                "status": "pending",
                "created_by": user.get("user_id"),
                "created_display_name": user.get("display_name"),
                "created_at": _format_ts(),
                "reviewed_by": None,
                "reviewed_at": None,
                "decision_note": None,
            }
            solutions.append(payload)
            _save_solutions(solutions)

            if _telegram_configured():
                try:
                    msg = f"🛠 Neue Lösung pending: {model} / {error_code} - {title} von {user.get('display_name')}"
                    send_telegram(msg)
                except Exception:
                    pass

            flash("Danke! Lösung eingereicht und wartet auf Freigabe.", "success")
            return redirect(url_for("community_solutions", model=model, error_code=error_code))

    return render_template(
        "community/submit_solution.html",
        error=error,
        prefill_model=prefill_model,
        prefill_code=prefill_code,
    )


@app.route("/admin", methods=["GET"])
@_admin_required
def admin_dashboard():
    users = _load_users()
    solutions = _load_solutions()
    pending_users = [u for u in users if _user_status(u) == "pending"]
    pending_solutions = [s for s in solutions if _solution_status(s) == "pending"]
    return render_template(
        "admin/dashboard.html",
        pending_users_count=len(pending_users),
        pending_solutions_count=len(pending_solutions),
    )


@app.route("/admin/users", methods=["GET"])
@_admin_required
def admin_users():
    status_filter = (request.args.get("status") or "pending").strip().lower()
    if status_filter not in ("pending", "approved", "rejected", "all"):
        status_filter = "pending"
    users = _load_users()
    if status_filter != "all":
        users = [u for u in users if _user_status(u) == status_filter]
    users.sort(key=lambda u: _parse_ts(u.get("created_at")) or datetime.min, reverse=True)
    return render_template(
        "admin/users.html",
        users=users,
        status_filter=status_filter,
    )


@app.route("/admin/users/<user_id>/approve", methods=["POST"])
@_admin_required
def admin_user_approve(user_id: str):
    users = _load_users()
    admin_user = _current_user()
    updated = False
    for u in users:
        if u.get("user_id") != user_id:
            continue
        u["status"] = "approved"
        u["reviewed_by"] = admin_user.get("user_id") if admin_user else None
        u["reviewed_at"] = _format_ts()
        u["decision_note"] = (request.form.get("decision_note") or "").strip() or None
        updated = True
        break

    if updated:
        _save_users(users)
        flash("User freigegeben.", "success")
    else:
        flash("User nicht gefunden.", "error")

    status_filter = request.form.get("status") or request.args.get("status") or "pending"
    return redirect(url_for("admin_users", status=status_filter))


@app.route("/admin/users/<user_id>/reject", methods=["POST"])
@_admin_required
def admin_user_reject(user_id: str):
    decision_note = (request.form.get("decision_note") or "").strip()
    if not decision_note:
        flash("Ablehnung benötigt eine Begründung.", "error")
        status_filter = request.form.get("status") or request.args.get("status") or "pending"
        return redirect(url_for("admin_users", status=status_filter))

    users = _load_users()
    admin_user = _current_user()
    updated = False
    for u in users:
        if u.get("user_id") != user_id:
            continue
        u["status"] = "rejected"
        u["reviewed_by"] = admin_user.get("user_id") if admin_user else None
        u["reviewed_at"] = _format_ts()
        u["decision_note"] = decision_note
        updated = True
        break

    if updated:
        _save_users(users)
        flash("User abgelehnt.", "success")
    else:
        flash("User nicht gefunden.", "error")

    status_filter = request.form.get("status") or request.args.get("status") or "pending"
    return redirect(url_for("admin_users", status=status_filter))


@app.route("/admin/solutions", methods=["GET"])
@_admin_required
def admin_solutions():
    status_filter = (request.args.get("status") or "pending").strip().lower()
    if status_filter not in ("pending", "approved", "rejected", "all"):
        status_filter = "pending"
    solutions = _load_solutions()
    if status_filter != "all":
        solutions = [s for s in solutions if _solution_status(s) == status_filter]
    solutions.sort(key=lambda s: _parse_ts(s.get("created_at")) or datetime.min, reverse=True)
    return render_template(
        "admin/solutions.html",
        solutions=solutions,
        status_filter=status_filter,
    )


@app.route("/admin/solutions/<solution_id>/approve", methods=["POST"])
@_admin_required
def admin_solution_approve(solution_id: str):
    solutions = _load_solutions()
    admin_user = _current_user()
    updated = False
    for s in solutions:
        if s.get("solution_id") != solution_id:
            continue
        s["status"] = "approved"
        s["reviewed_by"] = admin_user.get("user_id") if admin_user else None
        s["reviewed_at"] = _format_ts()
        s["decision_note"] = (request.form.get("decision_note") or "").strip() or None
        updated = True
        break

    if updated:
        _save_solutions(solutions)
        flash("Lösung freigegeben.", "success")
    else:
        flash("Lösung nicht gefunden.", "error")

    status_filter = request.form.get("status") or request.args.get("status") or "pending"
    return redirect(url_for("admin_solutions", status=status_filter))


@app.route("/admin/solutions/<solution_id>/reject", methods=["POST"])
@_admin_required
def admin_solution_reject(solution_id: str):
    decision_note = (request.form.get("decision_note") or "").strip()
    if not decision_note:
        flash("Ablehnung benötigt eine Begründung.", "error")
        status_filter = request.form.get("status") or request.args.get("status") or "pending"
        return redirect(url_for("admin_solutions", status=status_filter))

    solutions = _load_solutions()
    admin_user = _current_user()
    updated = False
    for s in solutions:
        if s.get("solution_id") != solution_id:
            continue
        s["status"] = "rejected"
        s["reviewed_by"] = admin_user.get("user_id") if admin_user else None
        s["reviewed_at"] = _format_ts()
        s["decision_note"] = decision_note
        updated = True
        break

    if updated:
        _save_solutions(solutions)
        flash("Lösung abgelehnt.", "success")
    else:
        flash("Lösung nicht gefunden.", "error")

    status_filter = request.form.get("status") or request.args.get("status") or "pending"
    return redirect(url_for("admin_solutions", status=status_filter))


@app.route("/admin/community/review", methods=["GET"])
@_admin_required
def community_review():
    solutions = _load_solutions()
    pending = [s for s in solutions if _solution_status(s) == "pending"]
    approved = [s for s in solutions if _solution_status(s) == "approved"]
    rejected = [s for s in solutions if _solution_status(s) == "rejected"]
    return render_template(
        "community_review.html",
        pending=pending,
        approved=approved,
        rejected=rejected,
    )

def _apply_solution_updates(solution: Dict[str, Any], form: Any) -> None:
    solution["model"] = _normalize_model(form.get("model") or solution.get("model") or "")
    solution["error_code"] = _normalize_error_code(form.get("error_code") or solution.get("error_code") or "")
    solution["title"] = (form.get("title") or solution.get("title") or "").strip()
    solution["symptom"] = (form.get("symptom") or solution.get("symptom") or "").strip()
    solution["cause"] = (form.get("cause") or solution.get("cause") or "").strip()
    solution["fix_steps"] = _split_lines(form.get("fix_steps") or "\n".join(solution.get("fix_steps") or []))
    solution["parts_tools"] = _split_lines(form.get("parts_tools") or "\n".join(solution.get("parts_tools") or []))
    solution["safety_note"] = (form.get("safety_note") or solution.get("safety_note") or "").strip()

@app.route("/admin/community/approve/<solution_id>", methods=["POST"])
@_admin_required
def community_approve(solution_id: str):
    solutions = _load_solutions()
    user = _current_user()
    updated = False
    for s in solutions:
        if s.get("solution_id") != solution_id:
            continue
        _apply_solution_updates(s, request.form)
        s["status"] = "approved"
        s["reviewed_by"] = user.get("user_id") if user else None
        s["reviewed_at"] = _format_ts()
        s["decision_note"] = (request.form.get("decision_note") or "").strip() or None
        updated = True
        break

    if updated:
        _save_solutions(solutions)
        flash("Lösung freigegeben.", "success")
    else:
        flash("Lösung nicht gefunden.", "error")
    return redirect(url_for("community_review"))

@app.route("/admin/community/reject/<solution_id>", methods=["POST"])
@_admin_required
def community_reject(solution_id: str):
    decision_note = (request.form.get("decision_note") or "").strip()
    if not decision_note:
        flash("Ablehnung benötigt eine Begründung.", "error")
        return redirect(url_for("community_review"))

    solutions = _load_solutions()
    user = _current_user()
    updated = False
    for s in solutions:
        if s.get("solution_id") != solution_id:
            continue
        _apply_solution_updates(s, request.form)
        s["status"] = "rejected"
        s["reviewed_by"] = user.get("user_id") if user else None
        s["reviewed_at"] = _format_ts()
        s["decision_note"] = decision_note
        updated = True
        break

    if updated:
        _save_solutions(solutions)
        flash("Lösung abgelehnt.", "success")
    else:
        flash("Lösung nicht gefunden.", "error")
    return redirect(url_for("community_review"))


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
    model = (data.get("model") or "").strip()
    if model.lower() in ("alle", "all", "*"):
        model = ""
    source_type = (data.get("source_type") or "").strip()
    source_type_filter = source_type
    if not source_type_filter or source_type_filter.lower() in ("alle", "all", "*"):
        source_type_filter = None
    source_mode = (source_type_filter or "general").lower()

    if not question:
        return jsonify({"ok": False, "error": "Bitte eine Frage eingeben."}), 400
    if not model:
        return jsonify({"ok": False, "error": "Bitte ein Modell auswählen"}), 400

    # ✅ Fehlercode-Direktmodus (nur LEC / Combo)
    requested_codes = _extract_error_codes(question)
    if source_mode in ("lec_error", "combo") and _is_pure_code_query(question, requested_codes, "lec_error"):
        results = _direct_lec_results_for_codes(requested_codes, model_hint=model, top_k=1)
        results = _enrich_results_with_bmk(results, model_hint=model)
        results = _attach_explain(results, model)
        results = _attach_traffic_light(results)
        general_results: List[Dict[str, Any]] = []
        if source_mode == "combo":
            general_results = _search_general(question, top_k=top_k)
            print(f"[GENERAL] returned {len(general_results)} items")
            general_results = _attach_explain(general_results, model)
            general_results = _attach_traffic_light(general_results)
            general_results = _dedupe_results(general_results)
        print(f"[SEARCH] q={question!r} model={model!r} source_type_filter={source_mode!r} results={len(results)} general={len(general_results)}")
        return jsonify({"ok": True, "results": results, "general_results": general_results})

    # ✅ Normale Embedding-Suche + Enrichment
    try:
        if source_mode == "general":
            results = []
            general_results = _search_general(question, top_k=top_k)
        elif source_mode == "combo":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="lec_error")
            general_results = _search_general(question, top_k=top_k)
        elif source_mode == "lec_error":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="lec_error")
            general_results = []
        elif source_mode == "spl":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="spl")
            general_results = []
        elif source_mode == "manual":
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter="manual")
            general_results = []
        else:
            results = search_similar(question, top_k=top_k, model_filter=model, source_type_filter=source_type_filter)
            general_results = []
    except TypeError:
        results = search_similar(question, top_k)
        general_results = []
    except Exception as e:
        return jsonify({"ok": False, "error": f"Fehler bei der Embedding-Suche: {e}"}), 500

    if results:
        results = _enrich_results_with_bmk(results, model_hint=model)
        results = _attach_explain(results, model)
        results = _attach_traffic_light(results)
    if general_results:
        print(f"[GENERAL] returned {len(general_results)} items")
        general_results = _attach_explain(general_results, model)
        general_results = _attach_traffic_light(general_results)
        general_results = _dedupe_results(general_results)
    print(f"[SEARCH] q={question!r} model={model!r} source_type_filter={source_mode!r} results={len(results)} general={len(general_results)}")
    return jsonify({"ok": True, "results": results, "general_results": general_results})

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
    if not model:
        return jsonify({"ok": False, "error": "Bitte ein Modell auswählen"}), 400

    results = _bmk_search_all_models(query=query, model_hint=model, limit=1)
    return jsonify({"ok": True, "results": results, "lang_mode": "de-only-heuristic", "result_mode": "single"})

@app.route("/api/ersatzteile/search", methods=["POST"])
def api_ersatzteile_search():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    model = data.get("model") or None
    query = (data.get("query") or "").strip()
    try:
        limit = int(data.get("limit") or 10)
    except Exception:
        limit = 10

    if not model:
        return jsonify({"ok": False, "error": "Bitte ein Modell auswählen"}), 400
    if not query:
        return jsonify({"ok": False, "error": "Bitte Suchbegriff eingeben."}), 400

    limit = max(1, min(limit, 200))

    data = _load_ersatzteile_for_model(model)
    if not data:
        return jsonify({"ok": False, "error": "Keine Ersatzteile für dieses Modell vorhanden"})

    q = query.lower()

    def _matches(value: Any) -> bool:
        if value is None:
            return False
        return q in str(value).lower()

    results: List[Dict[str, Any]] = []
    remaining = limit  # limit bezieht sich auf die Anzahl der Teilepositionen (parts)
    for a in data.get("assemblies") or []:
        if remaining <= 0:
            break
        if not isinstance(a, dict):
            continue

        assembly_match = any(
            _matches(a.get(k))
            for k in ("name_de", "name_en", "assembly_article")
        )

        selected_parts: List[Dict[str, Any]] = []
        for p in a.get("parts") or []:
            if remaining <= 0:
                break
            if not isinstance(p, dict):
                continue
            part_match = assembly_match or any(
                _matches(p.get(k))
                for k in (
                    "article_no", "article",
                    "name_de", "name_en",
                    "designation_de", "designation_en",
                    "bezeichnung_de", "description_en",
                    "bezeichnung", "text",
                    "pos",
                )
            )
            if not part_match:
                continue
            article_no = p.get("article_no") or p.get("article")
            name_de = p.get("name_de") or p.get("designation_de") or p.get("bezeichnung_de") or p.get("bezeichnung") or p.get("text")
            name_en = p.get("name_en") or p.get("designation_en") or p.get("description_en")
            selected_parts.append(
                {
                    "pos": p.get("pos"),
                    "article_no": article_no,
                    "qty": p.get("qty"),
                    "name_de": name_de,
                    "name_en": name_en,
                    "model": model,
                    "source_type": "etk_part",
                }
            )
            remaining -= 1

        if not selected_parts:
            continue

        results.append(
            {
                "assembly_article": a.get("assembly_article"),
                "name_de": a.get("name_de"),
                "name_en": a.get("name_en"),
                "ref_page": a.get("ref_page"),
                "parts": selected_parts,
            }
        )

    return jsonify({"ok": True, "results": results})

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

@app.route("/contact", methods=["POST"])
def contact():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify(ok=False, error="Nachricht ist erforderlich."), 400
    if len(message) > 1500:
        return jsonify(ok=False, error="Nachricht ist zu lang (max 1500 Zeichen)."), 400

    safe_name = name or "Unbekannt"
    safe_email = email or "-"
    payload = f"[Kran-Doc Kontakt] Name: {safe_name} | Email: {safe_email} | Message: {message}"

    ok = send_telegram(payload)
    if not ok:
        return jsonify(ok=False, error="Senden fehlgeschlagen."), 500

    return jsonify(ok=True)

def main():
    app.run(host="127.0.0.1", port=5000, debug=True)

if __name__ == "__main__":
    main()
