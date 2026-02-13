from __future__ import annotations

from typing import Any, Callable, Dict, List


def compute_initial_bmk_state(
    *,
    bmk_autorun: bool,
    bmk_query: str,
    bmk_model: str,
    run_bmk_search: Callable[[str, str], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    initial_bmk_results: List[Dict[str, Any]] = []
    initial_bmk_status = ""
    initial_bmk_status_type = ""

    if bmk_autorun and bmk_query and bmk_model:
        initial_bmk_results = run_bmk_search(bmk_query, bmk_model)
        initial_bmk_status = f"Treffer: {len(initial_bmk_results)}"
        initial_bmk_status_type = "ok"
        if not initial_bmk_results:
            initial_bmk_status = "Keine Treffer gefunden."
            initial_bmk_status_type = "error"

    return {
        "initial_bmk_results": initial_bmk_results,
        "initial_bmk_status": initial_bmk_status,
        "initial_bmk_status_type": initial_bmk_status_type,
    }
