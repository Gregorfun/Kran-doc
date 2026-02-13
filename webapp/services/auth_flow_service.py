from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def resolve_next_param(*, form_next: str, args_next: str) -> str:
    next_param = (form_next or args_next or "").strip()
    if next_param and not next_param.startswith("/"):
        return ""
    return next_param


def evaluate_account_login(
    *,
    method: str,
    email_raw: str,
    password: str,
    users: List[Dict[str, Any]],
    normalize_email: Callable[[str], str],
    find_user_by_email: Callable[..., Optional[Dict[str, Any]]],
    check_password_hash: Callable[[str, str], bool],
    user_status: Callable[[Optional[Dict[str, Any]]], str],
) -> Dict[str, Any]:
    if method != "POST":
        return {"error": None, "user": None, "status": None}

    email = normalize_email(email_raw or "")
    user = find_user_by_email(users=users, email=email, normalize_email=normalize_email)
    if not user or not check_password_hash(user.get("password_hash") or "", password or ""):
        return {"error": "Login fehlgeschlagen. Bitte prüfen.", "user": None, "status": None}

    status = user_status(user)
    if status == "rejected":
        note = (user.get("decision_note") or "").strip()
        if note:
            return {"error": f"Account abgelehnt. Grund: {note}", "user": None, "status": status}
        return {"error": "Account abgelehnt.", "user": None, "status": status}

    return {"error": None, "user": user, "status": status}


def evaluate_registration(
    *,
    method: str,
    users: List[Dict[str, Any]],
    email_raw: str,
    password: str,
    display_name_input: str,
    real_name: str,
    normalize_email: Callable[[str], str],
    find_user_by_email: Callable[..., Optional[Dict[str, Any]]],
    generate_pseudonym: Callable[[set[str]], str],
    generate_password_hash: Callable[[str], str],
    format_ts: Callable[[], str],
    create_user_id: Callable[[], str],
) -> Dict[str, Any]:
    if method != "POST":
        return {"error": None, "user": None}

    email = normalize_email(email_raw or "")
    display_name_clean = (display_name_input or "").strip()
    real_name_clean = (real_name or "").strip()

    if not email or "@" not in email:
        return {"error": "Bitte eine gueltige Email angeben.", "user": None}
    if not password or len(password) < 6:
        return {"error": "Passwort muss mindestens 6 Zeichen lang sein.", "user": None}
    if find_user_by_email(users=users, email=email, normalize_email=normalize_email):
        return {"error": "Email ist bereits registriert.", "user": None}

    existing_names = {u.get("display_name") for u in users if u.get("display_name")}
    if display_name_clean:
        display_name = display_name_clean
        display_mode = "custom"
    else:
        display_name = generate_pseudonym(existing_names)
        display_mode = "auto"

    user = {
        "user_id": create_user_id(),
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": "user",
        "status": "pending",
        "display_name": display_name,
        "display_mode": display_mode,
        "real_name": real_name_clean,
        "created_at": format_ts(),
        "reviewed_by": None,
        "reviewed_at": None,
        "decision_note": None,
    }
    return {"error": None, "user": user}
