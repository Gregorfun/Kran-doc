from __future__ import annotations

# --- NEW ---
import hmac
import json
import os
import re
import secrets
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from webapp.blueprints.admin import create_admin_blueprint
from webapp.blueprints.auth import create_auth_blueprint
from webapp.blueprints.ops import create_ops_blueprint
from webapp.blueprints.search import create_search_blueprint
from webapp.repositories.community_repository import (
    ensure_community_storage,
    load_solutions,
    load_users,
    save_solutions,
    save_users,
)
from webapp.services.auth_flow_service import evaluate_account_login, evaluate_registration, resolve_next_param
from webapp.services.bmk_component_service import build_bmk_index_for_components as svc_build_bmk_index_for_components
from webapp.services.bmk_component_service import (
    collect_bmk_components_for_model as svc_collect_bmk_components_for_model,
)
from webapp.services.bmk_index_service import get_bmk_entry as get_bmk_entry_from_index
from webapp.services.bmk_search_service import bmk_search_all_models as svc_bmk_search_all_models
from webapp.services.bmk_search_service import bmk_search_in_model as svc_bmk_search_in_model
from webapp.services.bmk_search_service import parse_bmk_search_request, validate_bmk_search_request
from webapp.services.audit_service import append_audit_event
from webapp.services.bundle_service import cleanup_temp_file, list_bundles, prepare_temp_bundle_path
from webapp.services.bundle_service import read_bundle_manifest, validate_bundle_compatibility, verify_bundle_signature
from webapp.services.community_service import (
    can_review,
    build_admin_dashboard_context,
    build_admin_list_context,
    build_submission_payload,
    execute_simple_review_action,
    execute_solution_review_action,
    filter_approved_solutions,
    normalize_status_filter,
    parse_submission_form,
    prioritize_pending_solutions,
    partition_review_lists,
    submission_access_error,
    validate_submission,
)
from webapp.services.contact_service import process_contact_submission
from webapp.services.diagnosis_service import build_diagnosis_path_from_spl
from webapp.services.document_service import resolve_input_document_path
from webapp.services.embedding_service import find_chunk_by_id
from webapp.services.ersatzteile_service import (
    load_ersatzteile_for_model,
    parse_ersatzteile_request,
    search_ersatzteile,
    validate_ersatzteile_request,
)
from webapp.services.explain_catalog_service import load_explain_catalog
from webapp.services.explain_service import attach_explain as svc_attach_explain
from webapp.services.explain_service import attach_traffic_light as svc_attach_traffic_light
from webapp.services.feedback_service import (
    append_feedback_log,
    build_feedback_telegram_message,
    process_feedback_submission,
)
from webapp.services.fusion_service import format_fusion_results, parse_fusion_request_data
from webapp.services.general_search_service import search_general as svc_search_general
from webapp.services.home_service import compute_initial_bmk_state
from webapp.services.insights_service import (
    build_feedback_insights,
    build_quick_help_cards,
    compute_coverage_kpis,
    load_feedback_entries,
)
from webapp.services.import_service import enqueue_pipeline_job_if_enabled, resolve_import_input
from webapp.services.jobs_service import get_job_log_payload, get_job_status_payload
from webapp.services.knowledge_service import (
    load_full_knowledge_model,
    load_lec_index_for_model,
    load_spl_references_for_model,
)
from webapp.services.lec_bmk_service import attach_auto_bmks, attach_lec_display_text, attach_solution_counts
from webapp.services.lec_bmk_service import direct_lec_results_for_codes as svc_direct_lec_results_for_codes
from webapp.services.lec_bmk_service import enrich_results_with_bmk as svc_enrich_results_with_bmk
from webapp.services.lsb_service import (
    extract_lsb_key_from_error_data,
    full_lsb_address,
    looks_like_lsb_query,
    lsb_keys_from_bmk_lsb,
    normalize_lsb_key,
)
from webapp.services.pipeline_service import pipeline_flash_payload, run_pipeline_steps
from webapp.services.query_service import extract_error_codes, is_pure_code_query
from webapp.services.result_service import (
    dedupe_results,
    first_non_empty_str,
    first_value,
    normalize_chunk_result,
    normalize_chunk_results,
    normalize_list_field,
)
from webapp.services.search_flow_service import run_search_flow
from webapp.services.search_explain_service import attach_search_explainability, confidence_summary
from webapp.services.security_service import get_provided_api_key, is_api_key_valid, is_rate_limited
from webapp.services.status_service import compute_system_status as svc_compute_system_status
from webapp.services.user_service import find_user_by_email, find_user_by_id, seed_admin_user
from webapp.telegram_notify import send_telegram

# ============================================================
# Projekt-Root sicher setzen (damit imports aus /scripts und /config funktionieren)
# webapp/app.py  ->  BASE_DIR = .../kran-tools
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from scripts.logger import get_logger
except Exception:
    import logging

    def get_logger(name: str):
        return logging.getLogger(name)


logger = get_logger(__name__)

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
    # Temporarily disabled for faster startup - uncomment when needed
    # from scripts.build_local_embedding_index import build_index as build_embedding_index  # type: ignore
    build_embedding_index = None  # type: ignore
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
                cfg.embeddings_dir = str(
                    c.get("embeddings_dir") or c.get("output_embeddings_dir") or cfg.embeddings_dir
                )
        except Exception:
            pass
    return cfg


CONFIG = _load_app_config()


def _required_env(*keys: str) -> str:
    for key in keys:
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    joined = " / ".join(keys)
    raise RuntimeError(f"Missing required environment variable: {joined}")


app = Flask(__name__)
app.secret_key = _required_env("SECRET_KEY", "KRANDOC_SECRET", "FLASK_SECRET_KEY")
app.permanent_session_lifetime = timedelta(hours=24)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (os.environ.get("FLASK_ENV") or "").lower() == "production"
_PIN = _required_env("PIN_CODE", "KRANDOC_PIN")
_CSRF_TOKEN_KEY = "_csrf_token"


def _get_csrf_token() -> str:
    token = session.get(_CSRF_TOKEN_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_CSRF_TOKEN_KEY] = token
    return token


def _semantic_warmup_enabled() -> bool:
    v = (os.environ.get("KRANDOC_WARMUP_SEMANTIC") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _start_semantic_warmup_background() -> None:
    if not _semantic_warmup_enabled():
        return
    if search_similar is None:
        logger.info("[SEMANTIC] Warmup übersprungen: semantic_index nicht verfügbar")
        return
    try:
        import threading

        def _run() -> None:
            try:
                from scripts.semantic_index import warmup_semantic  # type: ignore

                info = warmup_semantic(load_index=None)
                logger.info("[SEMANTIC] Warmup fertig: %s", info)
            except Exception as exc:
                logger.warning("[SEMANTIC] Warmup fehlgeschlagen: %s", exc)

        threading.Thread(target=_run, daemon=True).start()
        logger.info("[SEMANTIC] Warmup gestartet (Background)")
    except Exception as exc:
        logger.warning("[SEMANTIC] Warmup konnte nicht gestartet werden: %s", exc)


_start_semantic_warmup_background()


@app.after_request
def set_charset(response):
    ct = response.headers.get("Content-Type", "")
    if "text/html" in ct or ct == "":
        response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


# ============================================================
# Community-Storage (JSON, MVP)
# ============================================================


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


def _seed_admin_if_needed() -> None:
    users = load_users()
    admin_email = _required_env("KRANDOC_ADMIN_EMAIL")
    admin_password = _required_env("KRANDOC_ADMIN_PASSWORD")
    updated_users, action, target_email = seed_admin_user(
        users=users,
        admin_email=admin_email,
        admin_password=admin_password,
        normalize_email=_normalize_email,
        generate_password_hash=generate_password_hash,
        created_at=_format_ts(),
    )
    if action is None:
        return
    save_users(updated_users)
    if action == "created_from_env":
        logger.info("[KRAN-DOC] Admin-Account aus ENV erstellt.")
    elif action == "seeded_initial":
        logger.info("[KRAN-DOC] Admin-Seed erstellt: email=%s", target_email)


def _current_user() -> Optional[Dict[str, Any]]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return find_user_by_id(
        users=load_users(),
        user_id=user_id,
    )


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
            return redirect(url_for("auth.account_login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def _admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not can_review(user=user):
            flash("Admin-Rechte erforderlich.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)

    return wrapper


def _user_submission_count(user_id: str, since: datetime) -> int:
    count = 0
    for s in load_solutions():
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


ensure_community_storage()
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
    "pression",
    # ES
    "módulo",
    "modulo",
    "resistencias",
    "codificador",
    "ángulo",
    "angulo",
    "sensor",
    # IT
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
    r"[A-Z]\d{2,}(?:\.[A-Z0-9]{1,6})?\*?"  # A82, A81.A2, A306*
    r"|S\d{2,}\*?"  # S361
    r"|X\d{2,}\*?"  # X306*
    r"|AF\d{2,}\*?"  # AF401
    r"|B\d{2,}\*?"  # B501
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
# FULL_KNOWLEDGE Loader & Indizes
# ============================================================


def _load_explain_catalog(model: Optional[str]) -> Dict[str, Any]:
    return load_explain_catalog(base_dir=str(BASE_DIR), model=model)


# --- NEW ---
def _count_approved_solutions(model: str, error_code: str) -> int:
    if not error_code:
        return 0
    model_norm = _normalize_model(model or "")
    code_norm = _normalize_error_code(error_code)
    return len(
        filter_approved_solutions(
            solutions=load_solutions(),
            model=model_norm,
            error_code=code_norm,
            solution_status=_solution_status,
            normalize_model=_normalize_model,
            normalize_error_code=_normalize_error_code,
        )
    )


def _collect_bmk_components_for_model(model: str) -> List[Dict[str, Any]]:
    return svc_collect_bmk_components_for_model(
        models_dir=str(get_models_dir()),
        model=model,
        load_full_knowledge_model=load_full_knowledge_model,
    )


@lru_cache(maxsize=64)
def _build_bmk_index_for_model(model: str) -> Dict[str, List[Dict[str, Any]]]:
    components = _collect_bmk_components_for_model(model)
    return svc_build_bmk_index_for_components(
        components=components,
        is_probably_non_german=is_probably_non_german,
        is_valid_bmk_code=is_valid_bmk_code,
        clean_text_field=clean_text_field,
        clean_description=clean_description,
        lsb_keys_from_bmk_lsb=lsb_keys_from_bmk_lsb,
    )


# ============================================================
# LEC Direktmodus + Enrichment
# ============================================================


def _direct_lec_results_for_codes(codes: List[str], model_hint: Optional[str], top_k: int = 1) -> List[Dict[str, Any]]:
    return svc_direct_lec_results_for_codes(
        codes=codes,
        model_hint=model_hint,
        top_k=top_k,
        load_lec_index_for_model=lambda model: load_lec_index_for_model(models_dir=str(get_models_dir()), model=model),
        full_lsb_address=full_lsb_address,
    )


def _enrich_results_with_bmk(results: List[Dict[str, Any]], model_hint: Optional[str] = None) -> List[Dict[str, Any]]:
    return svc_enrich_results_with_bmk(
        results=results,
        model_hint=model_hint,
        load_lec_index_for_model=lambda model: load_lec_index_for_model(models_dir=str(get_models_dir()), model=model),
        full_lsb_address=full_lsb_address,
        extract_lsb_key_from_error_data=extract_lsb_key_from_error_data,
        build_bmk_index_for_model=_build_bmk_index_for_model,
    )


# ============================================================
# BMK Suche (deterministisch + LSB-Suche)
# ============================================================


def build_diagnosis_path(model: str, bmk_code: str) -> Dict[str, Any]:
    spl = load_spl_references_for_model(models_dir=str(get_models_dir()), model=model)
    spl_pages = spl.get("spl_pages") if isinstance(spl, dict) else None
    if not isinstance(spl_pages, list):
        spl_pages = []
    lec_idx = load_lec_index_for_model(models_dir=str(get_models_dir()), model=model)
    return build_diagnosis_path_from_spl(
        bmk_code=bmk_code,
        spl_pages=spl_pages,
        has_lec_index=bool(lec_idx),
    )


# ============================================================
# Systemstatus
# ============================================================


def compute_system_status() -> Dict[str, Any]:
    return svc_compute_system_status(
        base_dir=str(BASE_DIR),
        models_dir=str(get_models_dir()),
        embeddings_dir=str(Path(CONFIG.embeddings_dir)),
        has_embedding_index_fn=has_embedding_index,
    )


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
        "csrf_token": _get_csrf_token,
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
        # Allow API clients to authenticate via X-API-Key even when PIN-gating is enabled.
        # This keeps the browser UI protected by PIN while allowing programmatic access.
        try:
            from config.settings import get_settings

            settings = get_settings()
            if settings.api_key:
                provided_key = request.headers.get("X-API-Key") or request.args.get("api_key")
                if provided_key and provided_key == settings.api_key:
                    return None
        except Exception:
            pass
    if path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return redirect(url_for("auth.login", next=path))


@app.before_request
def csrf_protect() -> Optional[Any]:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None

    path = request.path or ""
    if path.startswith("/api/") or path.startswith("/static/"):
        return None

    session_token = session.get(_CSRF_TOKEN_KEY)
    request_token = (request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or "").strip()

    if not session_token or not request_token or not hmac.compare_digest(str(session_token), request_token):
        flash("Ungültiger Sicherheits-Token. Bitte Formular erneut senden.", "error")
        return redirect(request.referrer or url_for("index"))

    return None


def login():
    if not _pin_login_required():
        return redirect(url_for("auth.account_login", next=request.args.get("next") or ""))

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


def account_login():
    next_param = resolve_next_param(
        form_next=request.form.get("next") or "",
        args_next=request.args.get("next") or "",
    )

    error = None
    decision = evaluate_account_login(
        method=request.method,
        email_raw=request.form.get("email") or "",
        password=request.form.get("password") or "",
        users=load_users(),
        normalize_email=_normalize_email,
        find_user_by_email=find_user_by_email,
        check_password_hash=check_password_hash,
        user_status=_user_status,
    )
    error = decision.get("error")
    user = decision.get("user")
    status = decision.get("status")

    if user:
        _login_user(user)
        if status != "approved":
            flash("Dein Account wartet auf Freigabe. Du kannst noch keine Lösungen posten.", "error")
        else:
            flash("Login erfolgreich.", "success")
        return redirect(_safe_next_url(next_param))

    return render_template("auth/login.html", error=error, next_param=next_param)


def account_register():
    next_param = resolve_next_param(
        form_next=request.form.get("next") or "",
        args_next=request.args.get("next") or "",
    )

    error = None
    users = load_users()
    registration = evaluate_registration(
        method=request.method,
        users=users,
        email_raw=request.form.get("email") or "",
        password=request.form.get("password") or "",
        display_name_input=request.form.get("display_name") or "",
        real_name=request.form.get("real_name") or "",
        normalize_email=_normalize_email,
        find_user_by_email=find_user_by_email,
        generate_pseudonym=_generate_pseudonym,
        generate_password_hash=generate_password_hash,
        format_ts=_format_ts,
        create_user_id=lambda: uuid.uuid4().hex,
    )

    error = registration.get("error")
    user = registration.get("user")
    if user:
        users.append(user)
        save_users(users)

        if _telegram_configured():
            try:
                send_telegram(f"🆕 Neuer User pending: {user.get('display_name')} ({user.get('email')})")
            except Exception:
                pass

        _login_user(user)
        flash("Registrierung erfolgreich. Dein Account wartet auf Freigabe.", "success")
        return redirect(_safe_next_url(next_param or url_for("index")))

    return render_template("auth/register.html", error=error, next_param=next_param)


def account_logout():
    _logout_user()
    flash("Logout erfolgreich.", "success")
    return redirect(url_for("index"))


def register():
    return account_register()


def logout():
    return account_logout()


@app.route("/", methods=["GET"])
def index():
    ss = compute_system_status()
    bmk_query = (request.args.get("bmk_query") or "").strip()
    bmk_model = (request.args.get("bmk_model") or "").strip()
    bmk_autorun = (request.args.get("bmk_autorun") or "").strip() == "1"
    quick_help_cards = build_quick_help_cards(solutions=load_solutions(), limit=6)
    bmk_state = compute_initial_bmk_state(
        bmk_autorun=bmk_autorun,
        bmk_query=bmk_query,
        bmk_model=bmk_model,
        run_bmk_search=lambda query, model: svc_bmk_search_all_models(
            query=query,
            model_hint=model,
            list_models=lambda: [d.name for d in get_models_dir().iterdir() if d.is_dir()],
            search_in_model=lambda model_name, query_text: svc_bmk_search_in_model(
                model=model_name,
                query=query_text,
                build_bmk_index_for_model=_build_bmk_index_for_model,
                collect_bmk_components_for_model=_collect_bmk_components_for_model,
                looks_like_lsb_query=looks_like_lsb_query,
                looks_like_bmk_code_query=looks_like_bmk_code_query,
                is_probably_non_german=is_probably_non_german,
                is_valid_bmk_code=is_valid_bmk_code,
                clean_text_field=clean_text_field,
                clean_description=clean_description,
                limit=1,
            ),
            limit=1,
        ),
    )
    return render_template(
        "index.html",
        system_status=ss,
        embedding_index_available=ss.get("embedding_index_available"),
        quick_help_cards=quick_help_cards,
        initial_bmk_results=bmk_state["initial_bmk_results"],
        initial_bmk_status=bmk_state["initial_bmk_status"],
        initial_bmk_status_type=bmk_state["initial_bmk_status_type"],
    )


@app.route("/chunk/<chunk_id>", methods=["GET"])
def chunk_detail(chunk_id: str):
    chunk = find_chunk_by_id(base_dir=str(BASE_DIR), chunk_id=chunk_id)
    if chunk:
        chunk = normalize_chunk_result(chunk)
        return render_template("chunk_detail.html", chunk=chunk, chunk_id=chunk_id)
    return render_template("chunk_detail.html", chunk=None, chunk_id=chunk_id), 404


@app.route("/run/pipeline")
def run_pipeline():
    ok, error = run_pipeline_steps(
        steps=[
            process_all_lec_pdfs,
            process_all_bmk_pdfs,
            process_all_spl_pdfs,
            merge_all_models,
            export_chunks_jsonl,
            build_embedding_index,
        ]
    )
    message, category = pipeline_flash_payload(ok=ok, error=error)
    flash(message, category)

    return redirect(url_for("index"))


# ============================================================
# Community-Routen
# ============================================================


@app.route("/community/solutions/<path:model>/<path:error_code>")
def community_solutions(model: str, error_code: str):
    model_norm = _normalize_model(model)
    error_norm = _normalize_error_code(error_code)
    solutions = filter_approved_solutions(
        solutions=load_solutions(),
        model=model_norm,
        error_code=error_norm,
        solution_status=_solution_status,
        normalize_model=_normalize_model,
        normalize_error_code=_normalize_error_code,
    )
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
        return redirect(url_for("auth.account_login"))

    status = _user_status(user)
    access_error = submission_access_error(status)
    if access_error:
        flash(access_error, "error")
        return redirect(url_for("index"))

    prefill_model = _normalize_model(request.args.get("model") or "")
    prefill_code = _normalize_error_code(request.args.get("error_code") or "")

    error = None
    if request.method == "POST":
        submission = parse_submission_form(
            form_data=request.form,
            normalize_model=_normalize_model,
            normalize_error_code=_normalize_error_code,
            split_lines=_split_lines,
        )
        model = submission["model"]
        error_code = submission["error_code"]
        title = submission["title"]
        symptom = submission["symptom"]
        cause = submission["cause"]
        fix_steps = submission["fix_steps"]
        parts_tools = submission["parts_tools"]
        safety_note = submission["safety_note"]

        since = _utc_now() - timedelta(hours=24)
        submission_count = _user_submission_count(user.get("user_id"), since)
        error = validate_submission(
            model=model,
            error_code=error_code,
            title=title,
            symptom=symptom,
            cause=cause,
            fix_steps=fix_steps,
            submission_count_24h=submission_count,
        )

        if not error:
            solutions = load_solutions()
            payload = build_submission_payload(
                model=model,
                error_code=error_code,
                title=title,
                symptom=symptom,
                cause=cause,
                fix_steps=fix_steps,
                parts_tools=parts_tools,
                safety_note=safety_note,
                user=user,
                timestamp=_format_ts(),
            )
            solutions.append(payload)
            save_solutions(solutions)

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


@_admin_required
def admin_dashboard():
    context = build_admin_dashboard_context(
        users=load_users(),
        solutions=load_solutions(),
        user_status=_user_status,
        solution_status=_solution_status,
    )
    return render_template(
        "admin/dashboard.html",
        pending_users_count=context["pending_users_count"],
        pending_solutions_count=context["pending_solutions_count"],
    )


@_admin_required
def admin_users():
    context = build_admin_list_context(
        items=load_users(),
        requested_status=request.args.get("status") or "pending",
        status_resolver=_user_status,
        parse_ts=_parse_ts,
        normalize_status_filter=normalize_status_filter,
    )
    return render_template(
        "admin/users.html",
        users=context["items"],
        status_filter=context["status_filter"],
    )


@_admin_required
def admin_user_approve(user_id: str):
    users = load_users()
    admin_user = _current_user()
    result = execute_simple_review_action(
        items=users,
        id_field="user_id",
        id_value=user_id,
        decision="approved",
        raw_decision_note=request.form.get("decision_note") or "",
        reviewer_id=admin_user.get("user_id") if admin_user else None,
        reviewed_at=_format_ts(),
        form_status=request.form.get("status") or "",
        args_status=request.args.get("status") or "",
        success_message="User freigegeben.",
        not_found_message="User nicht gefunden.",
    )

    if result.get("ok"):
        save_users(users)
        try:
            append_audit_event(
                base_dir=str(BASE_DIR),
                event={
                    "event": "admin_user_approve",
                    "target_id": user_id,
                    "actor_id": admin_user.get("user_id") if admin_user else None,
                },
            )
        except Exception:
            pass
    flash(result.get("flash_message"), result.get("flash_category") or "error")
    status_filter = result.get("status_filter") or "pending"
    return redirect(url_for("admin.admin_users", status=status_filter))


@_admin_required
def admin_user_reject(user_id: str):
    users = load_users()
    admin_user = _current_user()
    result = execute_simple_review_action(
        items=users,
        id_field="user_id",
        id_value=user_id,
        decision="rejected",
        raw_decision_note=request.form.get("decision_note") or "",
        reviewer_id=admin_user.get("user_id") if admin_user else None,
        reviewed_at=_format_ts(),
        form_status=request.form.get("status") or "",
        args_status=request.args.get("status") or "",
        success_message="User abgelehnt.",
        not_found_message="User nicht gefunden.",
        require_note_for_reject=True,
    )
    if result.get("validation_error"):
        flash(result.get("validation_error"), "error")
        status_filter = result.get("status_filter") or "pending"
        return redirect(url_for("admin.admin_users", status=status_filter))

    if result.get("ok"):
        save_users(users)
        try:
            append_audit_event(
                base_dir=str(BASE_DIR),
                event={
                    "event": "admin_user_reject",
                    "target_id": user_id,
                    "actor_id": admin_user.get("user_id") if admin_user else None,
                },
            )
        except Exception:
            pass
    flash(result.get("flash_message"), result.get("flash_category") or "error")
    status_filter = result.get("status_filter") or "pending"
    return redirect(url_for("admin.admin_users", status=status_filter))


@_admin_required
def admin_solutions():
    context = build_admin_list_context(
        items=load_solutions(),
        requested_status=request.args.get("status") or "pending",
        status_resolver=_solution_status,
        parse_ts=_parse_ts,
        normalize_status_filter=normalize_status_filter,
    )
    return render_template(
        "admin/solutions.html",
        solutions=context["items"],
        status_filter=context["status_filter"],
    )


@_admin_required
def admin_solution_approve(solution_id: str):
    solutions = load_solutions()
    admin_user = _current_user()
    result = execute_simple_review_action(
        items=solutions,
        id_field="solution_id",
        id_value=solution_id,
        decision="approved",
        raw_decision_note=request.form.get("decision_note") or "",
        reviewer_id=admin_user.get("user_id") if admin_user else None,
        reviewed_at=_format_ts(),
        form_status=request.form.get("status") or "",
        args_status=request.args.get("status") or "",
        success_message="Lösung freigegeben.",
        not_found_message="Lösung nicht gefunden.",
    )

    if result.get("ok"):
        save_solutions(solutions)
        try:
            append_audit_event(
                base_dir=str(BASE_DIR),
                event={
                    "event": "admin_solution_approve",
                    "target_id": solution_id,
                    "actor_id": admin_user.get("user_id") if admin_user else None,
                },
            )
        except Exception:
            pass
    flash(result.get("flash_message"), result.get("flash_category") or "error")
    status_filter = result.get("status_filter") or "pending"
    return redirect(url_for("admin.admin_solutions", status=status_filter))


@_admin_required
def admin_solution_reject(solution_id: str):
    solutions = load_solutions()
    admin_user = _current_user()
    result = execute_simple_review_action(
        items=solutions,
        id_field="solution_id",
        id_value=solution_id,
        decision="rejected",
        raw_decision_note=request.form.get("decision_note") or "",
        reviewer_id=admin_user.get("user_id") if admin_user else None,
        reviewed_at=_format_ts(),
        form_status=request.form.get("status") or "",
        args_status=request.args.get("status") or "",
        success_message="Lösung abgelehnt.",
        not_found_message="Lösung nicht gefunden.",
        require_note_for_reject=True,
    )
    if result.get("validation_error"):
        flash(result.get("validation_error"), "error")
        status_filter = result.get("status_filter") or "pending"
        return redirect(url_for("admin.admin_solutions", status=status_filter))

    if result.get("ok"):
        save_solutions(solutions)
        try:
            append_audit_event(
                base_dir=str(BASE_DIR),
                event={
                    "event": "admin_solution_reject",
                    "target_id": solution_id,
                    "actor_id": admin_user.get("user_id") if admin_user else None,
                },
            )
        except Exception:
            pass
    flash(result.get("flash_message"), result.get("flash_category") or "error")
    status_filter = result.get("status_filter") or "pending"
    return redirect(url_for("admin.admin_solutions", status=status_filter))


@_admin_required
def community_review():
    solutions = load_solutions()
    feedback_entries = load_feedback_entries(base_dir=str(BASE_DIR), limit=5000)
    pending, approved, rejected = partition_review_lists(
        solutions=solutions,
        solution_status=_solution_status,
    )
    pending = prioritize_pending_solutions(solutions=pending, feedback_entries=feedback_entries)
    return render_template(
        "community_review.html",
        pending=pending,
        approved=approved,
        rejected=rejected,
    )


@_admin_required
def community_approve(solution_id: str):
    solutions = load_solutions()
    user = _current_user()
    result = execute_solution_review_action(
        solutions=solutions,
        solution_id=solution_id,
        decision="approved",
        raw_decision_note=request.form.get("decision_note") or "",
        reviewer_id=user.get("user_id") if user else None,
        reviewed_at=_format_ts(),
        form_data=request.form,
        normalize_model=_normalize_model,
        normalize_error_code=_normalize_error_code,
        split_lines=_split_lines,
        success_message="Lösung freigegeben.",
        not_found_message="Lösung nicht gefunden.",
    )

    if result.get("ok"):
        save_solutions(solutions)
        try:
            append_audit_event(
                base_dir=str(BASE_DIR),
                event={
                    "event": "community_solution_approve",
                    "target_id": solution_id,
                    "actor_id": user.get("user_id") if user else None,
                },
            )
        except Exception:
            pass
    flash(result.get("flash_message"), result.get("flash_category") or "error")
    return redirect(url_for("admin.community_review"))


@_admin_required
def community_reject(solution_id: str):
    solutions = load_solutions()
    user = _current_user()
    result = execute_solution_review_action(
        solutions=solutions,
        solution_id=solution_id,
        decision="rejected",
        raw_decision_note=request.form.get("decision_note") or "",
        reviewer_id=user.get("user_id") if user else None,
        reviewed_at=_format_ts(),
        form_data=request.form,
        normalize_model=_normalize_model,
        normalize_error_code=_normalize_error_code,
        split_lines=_split_lines,
        success_message="Lösung abgelehnt.",
        not_found_message="Lösung nicht gefunden.",
        require_note_for_reject=True,
    )

    if result.get("validation_error"):
        flash(result.get("validation_error"), "error")
        return redirect(url_for("admin.community_review"))

    if result.get("ok"):
        save_solutions(solutions)
        try:
            append_audit_event(
                base_dir=str(BASE_DIR),
                event={
                    "event": "community_solution_reject",
                    "target_id": solution_id,
                    "actor_id": user.get("user_id") if user else None,
                },
            )
        except Exception:
            pass
    flash(result.get("flash_message"), result.get("flash_category") or "error")
    return redirect(url_for("admin.community_review"))


# ============================================================
# JSON-APIs
# ============================================================


def api_status():
    status = compute_system_status()
    return jsonify({"ok": True, "status": status})


def health():
    return api_status()


def api_search():
    try:
        data = request.get_json(silent=True) or {}
    except Exception as json_error:
        from scripts.logger import get_logger

        logger = get_logger(__name__)
        logger.error(f"JSON parsing error in /api/search: {json_error}")
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    def enrich_primary_results(results: List[Dict[str, Any]], model: str) -> List[Dict[str, Any]]:
        results = svc_attach_explain(results=results, model=model, load_explain_catalog=_load_explain_catalog)
        results = svc_attach_traffic_light(results=results)
        results = normalize_chunk_results(results)
        results = attach_lec_display_text(
            results=results,
            model_hint=model,
            normalize_model=_normalize_model,
            load_lec_index_for_model=lambda model_name: load_lec_index_for_model(
                models_dir=str(get_models_dir()),
                model=model_name,
            ),
            first_non_empty_str=first_non_empty_str,
        )
        results = attach_auto_bmks(
            results=results,
            model_hint=model,
            normalize_model=_normalize_model,
            first_value=first_value,
            normalize_list_field=normalize_list_field,
            get_bmk_entry=lambda model_name, bmk_code: get_bmk_entry_from_index(
                base_dir=str(BASE_DIR),
                model=model_name,
                bmk_code=bmk_code,
            ),
        )
        return attach_solution_counts(results=results, count_solutions=_count_approved_solutions)

    def enrich_general_results(results: List[Dict[str, Any]], model: str) -> List[Dict[str, Any]]:
        results = svc_attach_explain(results=results, model=model, load_explain_catalog=_load_explain_catalog)
        results = svc_attach_traffic_light(results=results)
        results = dedupe_results(results)
        return normalize_chunk_results(results)

    flow_result = run_search_flow(
        data=data,
        search_similar=search_similar,
        extract_error_codes=extract_error_codes,
        is_pure_code_query=is_pure_code_query,
        direct_lec_results_for_codes=lambda codes, model_hint, top_k: _direct_lec_results_for_codes(
            codes,
            model_hint=model_hint,
            top_k=top_k,
        ),
        enrich_results_with_bmk=lambda results, model_hint: _enrich_results_with_bmk(
            results,
            model_hint=model_hint,
        ),
        search_general=lambda query, top_k: svc_search_general(
            query=query,
            top_k=top_k,
            search_similar=search_similar,
        ),
        enrich_primary_results=enrich_primary_results,
        enrich_general_results=enrich_general_results,
        logger=logger,
    )

    if not flow_result.get("ok"):
        status = int(flow_result.get("status") or 500)
        return jsonify({"ok": False, "error": flow_result.get("error") or "Unbekannter Fehler"}), status

    results = attach_search_explainability(results=flow_result.get("results") or [])
    general_results = attach_search_explainability(results=flow_result.get("general_results") or [])
    confidence = confidence_summary(results=results, threshold=0.6)
    fallback_message = None
    if confidence.get("fallback_recommended"):
        fallback_message = "Keine sichere Antwort – bitte Diagnosepfad oder Community-Lösungen prüfen."

    return jsonify(
        {
            "ok": True,
            "results": results,
            "general_results": general_results,
            "confidence": confidence,
            "fallback_message": fallback_message,
        }
    )


def api_insights_feedback():
    entries = load_feedback_entries(base_dir=str(BASE_DIR), limit=5000)
    insights = build_feedback_insights(feedback_entries=entries, solutions=load_solutions())
    return jsonify({"ok": True, "insights": insights})


def api_insights_coverage():
    models_dir = get_models_dir()
    model_names = [d.name for d in models_dir.iterdir() if d.is_dir()] if models_dir.exists() else []
    coverage = compute_coverage_kpis(
        model_names=sorted(model_names),
        solutions=load_solutions(),
        load_lec_index_for_model=lambda model_name: load_lec_index_for_model(
            models_dir=str(get_models_dir()),
            model=model_name,
        ),
    )
    return jsonify({"ok": True, "coverage": coverage})


def api_quick_help_cards():
    cards = build_quick_help_cards(solutions=load_solutions(), limit=8)
    return jsonify({"ok": True, "cards": cards})


@app.route("/api/bmk_search", methods=["POST"])
def api_bmk_search():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    parsed = parse_bmk_search_request(data)
    query = parsed["query"]
    model = parsed["model"]

    validation_error = validate_bmk_search_request(query=query, model=model)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    results = svc_bmk_search_all_models(
        query=query,
        model_hint=model,
        list_models=lambda: [d.name for d in get_models_dir().iterdir() if d.is_dir()],
        search_in_model=lambda model_name, query_text: svc_bmk_search_in_model(
            model=model_name,
            query=query_text,
            build_bmk_index_for_model=_build_bmk_index_for_model,
            collect_bmk_components_for_model=_collect_bmk_components_for_model,
            looks_like_lsb_query=looks_like_lsb_query,
            looks_like_bmk_code_query=looks_like_bmk_code_query,
            is_probably_non_german=is_probably_non_german,
            is_valid_bmk_code=is_valid_bmk_code,
            clean_text_field=clean_text_field,
            clean_description=clean_description,
            limit=1,
        ),
        limit=1,
    )
    bmk_code = ""
    if results:
        bmk_code = (results[0].get("bmk") or "").strip()
    if not bmk_code and looks_like_bmk_code_query(query):
        bmk_code = query.strip().upper()
    diagnosis = build_diagnosis_path(model, bmk_code) if bmk_code else {}
    return jsonify(
        {
            "ok": True,
            "results": results,
            "lang_mode": "de-only-heuristic",
            "result_mode": "single",
            "diagnosis_path": diagnosis,
        }
    )


@app.route("/api/ersatzteile/search", methods=["POST"])
def api_ersatzteile_search():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    parsed = parse_ersatzteile_request(data)
    model = parsed["model"]
    query = parsed["query"]
    limit = parsed["limit"]

    validation_error = validate_ersatzteile_request(model=model, query=query)
    if validation_error:
        return jsonify({"ok": False, "error": validation_error}), 400

    ersatzteile_data = load_ersatzteile_for_model(models_dir=str(get_models_dir()), model=model)
    if not ersatzteile_data:
        return jsonify({"ok": False, "error": "Keine Ersatzteile für dieses Modell vorhanden"})

    results = search_ersatzteile(
        data=ersatzteile_data,
        model=model,
        query=query,
        limit=limit,
    )

    return jsonify({"ok": True, "results": results})


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400

    result = process_feedback_submission(
        data=data,
        base_dir=str(BASE_DIR),
        append_feedback_log=append_feedback_log,
        build_feedback_telegram_message=build_feedback_telegram_message,
        send_telegram=send_telegram,
        logger=logger,
    )
    if not result.get("ok"):
        return jsonify(ok=False, error=result.get("error") or "Feedback failed"), int(result.get("status") or 500)
    return jsonify(ok=True)


@app.route("/contact", methods=["POST"])
def contact():
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify(ok=False, error="Invalid JSON"), 400

    result = process_contact_submission(data=data, send_telegram=send_telegram)
    if not result.get("ok"):
        return jsonify(ok=False, error=result.get("error") or "Kontakt fehlgeschlagen"), int(
            result.get("status") or 500
        )
    return jsonify(ok=True)


# ============================================================
# NEW: Job Queue API Endpoints
# ============================================================


def api_import():
    """
    Start import job for PDF file

    POST /api/import
    Body: multipart/form-data with 'file' or JSON with 'path'
    Returns: {"job_id": "..."}
    """
    from adapters.security import _rate_limiter, sanitize_filename, validate_path_access, validate_upload_file
    from scripts.jobs import create_job

    client_ip = request.remote_addr or "unknown"
    if is_rate_limited(rate_limiter=_rate_limiter, client_ip=client_ip, max_requests=10, window_seconds=60):
        return jsonify(error="Rate limit exceeded"), 429

    # Check API key if configured
    from config.settings import settings

    provided_key = get_provided_api_key(request=request)
    if not is_api_key_valid(configured_key=settings.api_key or "", provided_key=provided_key):
        return jsonify(error="Unauthorized"), 401

    resolved = resolve_import_input(
        request=request,
        base_dir=str(BASE_DIR),
        validate_upload_file=validate_upload_file,
        sanitize_filename=sanitize_filename,
        validate_path_access=validate_path_access,
    )
    if not resolved.get("ok"):
        return jsonify(error=resolved.get("error") or "Import input invalid"), int(resolved.get("status") or 400)

    input_file = resolved["input_file"]
    model_name = resolved.get("model_name")

    # Create job
    try:
        job = create_job(input_file, model_name)
        enqueue_pipeline_job_if_enabled(settings=settings, job_id=job.job_id, logger=logger)

        return jsonify(job_id=job.job_id)

    except Exception as e:
        return jsonify(error=str(e)), 500


def api_job_status(job_id):
    """
    Get job status

    GET /api/jobs/<job_id>
    Returns: Job status JSON
    """
    from scripts.jobs import get_job

    result = get_job_status_payload(job_id=job_id, get_job=get_job)
    if not result.get("ok"):
        return jsonify(error=result.get("error") or "Job lookup failed"), int(result.get("status") or 404)
    return jsonify(result.get("payload") or {})


def api_job_log(job_id):
    """
    Get job log (last N steps)

    GET /api/jobs/<job_id>/log?limit=10
    Returns: {"steps": [...]}
    """
    from scripts.jobs import get_job

    result = get_job_log_payload(
        job_id=job_id,
        raw_limit=request.args.get("limit", 10),
        get_job=get_job,
    )
    if not result.get("ok"):
        return jsonify(error=result.get("error") or "Job log lookup failed"), int(result.get("status") or 404)
    return jsonify(result.get("payload") or {"steps": []})


# ============================================================
# NEW: Enhanced Search API (Fusion)
# ============================================================


def api_search_fusion():
    """
    Enhanced search with Fusion Ranking

    GET /api/search?q=...&mode=auto&limit=20
    POST /api/search with JSON body

    Modes: auto (fusion), exact, fuzzy, semantic
    """
    from adapters.security import _rate_limiter
    from core.search import FusionSearchService

    # Rate limit: 60 requests per minute
    client_ip = request.remote_addr or "unknown"
    if is_rate_limited(rate_limiter=_rate_limiter, client_ip=client_ip, max_requests=60, window_seconds=60):
        return jsonify(error="Rate limit exceeded"), 429

    params = parse_fusion_request_data(
        method=request.method,
        args=request.args,
        json_data=request.get_json() or {} if request.method == "POST" else {},
    )
    query = params["query"]
    mode = params["mode"]
    limit = params["limit"]
    filters = params["filters"]

    if not query:
        return jsonify(error="Query required"), 400

    # Initialize search service
    qdrant_client = None
    try:
        from config.settings import settings

        if settings.qdrant_url:
            from qdrant_client import QdrantClient

            qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    except Exception:
        pass

    search_service = FusionSearchService(qdrant_client)

    # Search
    try:
        results = search_service.search(query, mode=mode, limit=limit, filters=filters)

        return jsonify(format_fusion_results(query=query, mode=mode, results=results))

    except Exception as e:
        return jsonify(error=str(e)), 500


# ============================================================
# NEW: Bundle API
# ============================================================


def api_bundle_import():
    """
    Import bundle from uploaded zip

    POST /api/bundles/import
    Body: multipart/form-data with 'bundle' file
    Returns: Import summary
    """
    from adapters.security import _rate_limiter
    from config.settings import settings
    from scripts.bundles.import_bundle import import_bundle

    # Rate limit
    client_ip = request.remote_addr or "unknown"
    if is_rate_limited(rate_limiter=_rate_limiter, client_ip=client_ip, max_requests=5, window_seconds=60):
        return jsonify(error="Rate limit exceeded"), 429

    # Check API key
    provided_key = get_provided_api_key(request=request)
    if not is_api_key_valid(configured_key=settings.api_key or "", provided_key=provided_key):
        return jsonify(error="Unauthorized"), 401

    if "bundle" not in request.files:
        return jsonify(error="Bundle file required"), 400

    file = request.files["bundle"]

    from adapters.security import sanitize_filename

    temp_path = prepare_temp_bundle_path(
        base_dir=str(BASE_DIR),
        filename=file.filename,
        sanitize_filename=sanitize_filename,
    )

    file.save(str(temp_path))

    try:
        dry_run = str(request.args.get("dry_run") or "").strip().lower() in {"1", "true", "yes"}
        manifest = read_bundle_manifest(bundle_path=temp_path)
        compatibility = validate_bundle_compatibility(
            manifest=manifest or {},
            app_name=str(settings.app_name),
            min_version="1.0",
        )
        if not compatibility.get("compatible"):
            return jsonify(error="Bundle inkompatibel", compatibility=compatibility), 400

        signing_secret = str(settings.api_key or "")
        provided_signature = str(request.headers.get("X-Bundle-Signature") or "").strip()
        if signing_secret and provided_signature:
            if not verify_bundle_signature(
                bundle_path=temp_path,
                secret=signing_secret,
                provided_signature=provided_signature,
            ):
                return jsonify(error="Invalid bundle signature"), 401

        if dry_run:
            return jsonify(
                {
                    "ok": True,
                    "dry_run": True,
                    "manifest": manifest,
                    "compatibility": compatibility,
                }
            )

        result = import_bundle(temp_path)
        return jsonify(result)
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        cleanup_temp_file(temp_path)


def api_bundle_list():
    """
    List available bundles

    GET /api/bundles/list
    Returns: {"bundles": [...]}
    """
    from config.settings import settings

    bundles_dir = settings.output_dir / "bundles"
    return jsonify(bundles=list_bundles(bundles_dir=bundles_dir))


# ============================================================
# NEW: PDF Viewer for Provenance
# ============================================================


def view_document(filename):
    """
    View document with page parameter

    GET /docs/<filename>?page=5
    """
    from flask import send_file

    from adapters.security import validate_path_access

    # Validate path
    doc_path = resolve_input_document_path(base_dir=str(BASE_DIR), filename=filename)

    if not validate_path_access(doc_path, BASE_DIR / "input"):
        abort(403)

    if not doc_path.exists():
        abort(404)

    # For now, just serve the PDF
    # In future, can add PDF.js viewer with page navigation
    page = request.args.get("page", type=int)

    return send_file(str(doc_path), mimetype="application/pdf")


app.register_blueprint(
    create_auth_blueprint(
        {
            "login": login,
            "account_login": account_login,
            "account_register": account_register,
            "account_logout": account_logout,
            "register": register,
            "logout": logout,
        }
    )
)

app.register_blueprint(
    create_admin_blueprint(
        {
            "admin_dashboard": admin_dashboard,
            "admin_users": admin_users,
            "admin_user_approve": admin_user_approve,
            "admin_user_reject": admin_user_reject,
            "admin_solutions": admin_solutions,
            "admin_solution_approve": admin_solution_approve,
            "admin_solution_reject": admin_solution_reject,
            "community_review": community_review,
            "community_approve": community_approve,
            "community_reject": community_reject,
        }
    )
)

app.register_blueprint(
    create_ops_blueprint(
        {
            "api_import": api_import,
            "api_job_status": api_job_status,
            "api_job_log": api_job_log,
            "api_bundle_import": api_bundle_import,
            "api_bundle_list": api_bundle_list,
            "view_document": view_document,
        }
    )
)

app.register_blueprint(
    create_search_blueprint(
        {
            "api_status": api_status,
            "health": health,
            "api_search": api_search,
            "api_search_fusion": api_search_fusion,
            "api_insights_feedback": api_insights_feedback,
            "api_insights_coverage": api_insights_coverage,
            "api_quick_help_cards": api_quick_help_cards,
        }
    )
)


def main():
    app.run(host="127.0.0.1", port=5002, debug=False)


if __name__ == "__main__":
    main()
