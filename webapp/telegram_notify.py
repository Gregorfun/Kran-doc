import os
import logging
import requests


logger = logging.getLogger(__name__)

def send_telegram(text: str) -> bool:
    # Prefer new env names, keep backward compatibility
    token = (
        os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        or os.getenv("KRANDOC_TELEGRAM_BOT_TOKEN", "").strip()
    )
    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID", "").strip()
        or os.getenv("KRANDOC_TELEGRAM_CHAT_ID", "").strip()
    )
    if not token or not chat_id:
        # Minimal diagnostics for live servers (visible in journalctl)
        logger.warning("[telegram] missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID (or KRANDOC_* fallbacks)")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=8)
        if r.status_code != 200:
            logger.warning("[telegram] non-200 response: %s %s", r.status_code, (r.text or "")[:200])
        return r.status_code == 200
    except Exception as e:
        logger.exception("[telegram] exception: %s", e)
        return False
