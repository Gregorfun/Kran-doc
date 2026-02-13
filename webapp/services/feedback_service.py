from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict


def build_feedback_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": data.get("question"),
        "result": data.get("result"),
        "note": data.get("note"),
    }


def append_feedback_log(*, base_dir: str, payload: Dict[str, Any]) -> None:
    logs_dir = Path(base_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    out_path = logs_dir / "feedback.jsonl"
    with out_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_feedback_telegram_message(payload: Dict[str, Any]) -> str:
    timestamp = payload.get("timestamp") or ""
    question = str(payload.get("question") or "").strip()
    note = str(payload.get("note") or "").strip()

    result = payload.get("result") or {}
    meta = (result.get("metadata") or {}) if isinstance(result, dict) else {}

    model = result.get("model") or meta.get("model") or "?"
    source = result.get("source_type") or meta.get("source_type") or "?"

    code = meta.get("code") or meta.get("error_code") or meta.get("bmk") or ""
    lsb = (
        meta.get("lsb_error_key") or meta.get("lsb_key") or meta.get("lsb_address") or meta.get("lsb_bmk_address") or ""
    )

    title = meta.get("title") or result.get("title") or ""
    description = meta.get("description_clean") or meta.get("sensor_description") or meta.get("description") or ""

    return (
        "?? Kran-Doc Fehler-Meldung\n"
        f"Zeit: {timestamp}\n"
        f"Modell: {model}\n"
        f"Quelle: {source}\n"
        f"Code: {code}\n"
        f"LSB: {lsb}\n\n"
        f"Treffer: {title}\n"
        f"Beschreibung: {description}\n\n"
        f"Frage:\n{question}\n\n"
        f"Meldung:\n{note}\n"
    )


def process_feedback_submission(
    *,
    data: Dict[str, Any],
    base_dir: str,
    append_feedback_log: Callable[..., None],
    build_feedback_telegram_message: Callable[[Dict[str, Any]], str],
    send_telegram: Callable[[str], Any],
    logger: Any,
) -> Dict[str, Any]:
    payload = build_feedback_payload(data)

    try:
        append_feedback_log(base_dir=base_dir, payload=payload)
        try:
            msg = build_feedback_telegram_message(payload)
            send_telegram(msg)
        except Exception as telegram_error:
            logger.warning(f"Telegram notification failed: {telegram_error}")
    except Exception as error:
        logger.error(f"Error writing feedback log: {error}", exc_info=True)
        return {"ok": False, "error": f"Fehler beim Schreiben des Feedback-Logs: {error}", "status": 500}

    return {"ok": True}
