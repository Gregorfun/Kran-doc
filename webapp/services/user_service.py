from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple


def find_user_by_email(
    *,
    users: List[Dict[str, Any]],
    email: str,
    normalize_email: Callable[[str], str],
) -> Optional[Dict[str, Any]]:
    target = normalize_email(email)
    for user in users:
        if normalize_email(user.get("email") or "") == target:
            return user
    return None


def find_user_by_id(
    *,
    users: List[Dict[str, Any]],
    user_id: str,
) -> Optional[Dict[str, Any]]:
    for user in users:
        if user.get("user_id") == user_id:
            return user
    return None


def seed_admin_user(
    *,
    users: List[Dict[str, Any]],
    admin_email: str,
    admin_password: str,
    normalize_email: Callable[[str], str],
    generate_password_hash: Callable[[str], str],
    created_at: str,
) -> Tuple[List[Dict[str, Any]], Optional[str], str]:
    target_email = normalize_email(admin_email) if admin_email else ""

    if target_email and find_user_by_email(
        users=users,
        email=target_email,
        normalize_email=normalize_email,
    ):
        return users, None, target_email

    if users:
        if target_email and admin_password:
            updated = list(users)
            updated.append(_build_admin_user(target_email, admin_password, generate_password_hash, created_at))
            return updated, "created_from_env", target_email
        return users, None, target_email

    updated = list(users)
    updated.append(_build_admin_user(target_email, admin_password, generate_password_hash, created_at))
    return updated, "seeded_initial", target_email


def _build_admin_user(
    email: str,
    password: str,
    password_hasher: Callable[[str], str],
    created_at: str,
) -> Dict[str, Any]:
    return {
        "user_id": uuid.uuid4().hex,
        "email": email,
        "password_hash": password_hasher(password),
        "role": "admin",
        "status": "approved",
        "display_name": "Admin",
        "display_mode": "custom",
        "real_name": "",
        "created_at": created_at,
        "reviewed_by": None,
        "reviewed_at": None,
        "decision_note": None,
    }
