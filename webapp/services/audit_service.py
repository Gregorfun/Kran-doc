from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def append_audit_event(*, base_dir: str, event: Dict[str, Any]) -> None:
    logs_dir = Path(base_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / "audit_log.jsonl"

    payload = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        **event,
    }

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")