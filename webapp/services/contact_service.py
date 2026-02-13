from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple


def parse_contact_payload(data: Dict[str, Any]) -> Tuple[str, str, str]:
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip()
    message = str(data.get("message") or "").strip()
    return name, email, message


def validate_contact_message(*, message: str, max_len: int = 1500) -> Optional[str]:
    if not message:
        return "Nachricht ist erforderlich."
    if len(message) > max_len:
        return "Nachricht ist zu lang (max 1500 Zeichen)."
    return None


def build_contact_telegram_payload(*, name: str, email: str, message: str) -> str:
    safe_name = name or "Unbekannt"
    safe_email = email or "-"
    return f"[Kran-Doc Kontakt] Name: {safe_name} | Email: {safe_email} | Message: {message}"


def process_contact_submission(
    *,
    data: Dict[str, Any],
    send_telegram: Callable[[str], Any],
) -> Dict[str, Any]:
    name, email, message = parse_contact_payload(data)

    validation_error = validate_contact_message(message=message)
    if validation_error:
        return {"ok": False, "error": validation_error, "status": 400}

    payload = build_contact_telegram_payload(name=name, email=email, message=message)
    ok = send_telegram(payload)
    if not ok:
        return {"ok": False, "error": "Senden fehlgeschlagen.", "status": 500}

    return {"ok": True}
