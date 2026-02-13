from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List


def compute_system_status(
    *,
    base_dir: str,
    models_dir: str,
    embeddings_dir: str,
    has_embedding_index_fn: Callable[[], bool] | None,
) -> Dict[str, Any]:
    models_dir_path = Path(models_dir)
    model_names: List[str] = []
    if models_dir_path.exists():
        model_names = sorted([entry.name for entry in models_dir_path.iterdir() if entry.is_dir()])

    embedding_available = False
    try:
        if has_embedding_index_fn:
            embedding_available = bool(has_embedding_index_fn())
    except Exception:
        embedding_available = False

    latest_report = None
    report_dir = Path(base_dir) / "output" / "reports"
    if report_dir.exists():
        reports = sorted(report_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if reports:
            latest_report = reports[0].name

    num_full_knowledge = 0
    for model in model_names:
        model_dir = models_dir_path / model
        if (model_dir / f"{model}_FULL_KNOWLEDGE.json").exists() or (
            model_dir / f"{model}_GPT51_FULL_KNOWLEDGE.json"
        ).exists():
            num_full_knowledge += 1

    return {
        "models_dir": str(models_dir_path),
        "num_models": len(model_names),
        "num_full_knowledge": num_full_knowledge,
        "model_names": model_names,
        "embeddings_dir": str(embeddings_dir),
        "embedding_index_available": embedding_available,
        "latest_report": latest_report,
        "bmk_language_mode": "heuristic:de-only",
        "bmk_result_mode": "single",
    }
