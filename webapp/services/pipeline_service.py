from __future__ import annotations

from typing import Callable, List, Optional, Tuple


def run_pipeline_steps(*, steps: List[Callable[[], None]]) -> Tuple[bool, Optional[str]]:
    try:
        for step in steps:
            if step:
                step()
        return True, None
    except Exception as error:
        return False, str(error)

    def pipeline_flash_payload(*, ok: bool, error: Optional[str]) -> Tuple[str, str]:
        if ok:
            return "Pipeline erfolgreich ausgeführt.", "success"
        return f"Pipeline-Fehler: {error}", "error"
