import os
import requests

def send_telegram(text: str) -> bool:
    token = os.getenv("KRANDOC_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("KRANDOC_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=8)
        return r.status_code == 200
    except Exception:
        return False
