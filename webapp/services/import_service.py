from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple


def resolve_import_input(
    *,
    request: Any,
    base_dir: str,
    validate_upload_file: Callable[[Any], Tuple[bool, Optional[str]]],
    sanitize_filename: Callable[[str], str],
    validate_path_access: Callable[[Path, Path], bool],
) -> Dict[str, Any]:
    model_name = request.form.get("model") or request.args.get("model")
    base_input_dir = Path(base_dir) / "input"

    if "file" in request.files:
        file = request.files["file"]
        is_valid, error = validate_upload_file(file)
        if not is_valid:
            return {"ok": False, "status": 400, "error": error or "Invalid file"}

        safe_filename = sanitize_filename(file.filename)
        upload_dir = base_input_dir / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / safe_filename
        file.save(str(file_path))

        return {
            "ok": True,
            "input_file": str(file_path),
            "model_name": model_name,
        }

    if request.is_json:
        data = request.get_json(silent=True) or {}
        input_file = data.get("path")
        model_name = model_name or data.get("model")

        if not input_file:
            return {"ok": False, "status": 400, "error": "'path' required in JSON body"}

        file_path = Path(input_file)
        if not validate_path_access(file_path, base_input_dir):
            return {"ok": False, "status": 403, "error": "Invalid path"}

        if not file_path.exists():
            return {"ok": False, "status": 404, "error": "File not found"}

        return {
            "ok": True,
            "input_file": str(file_path),
            "model_name": model_name,
        }

    return {"ok": False, "status": 400, "error": "File or path required"}


def enqueue_pipeline_job_if_enabled(*, settings: Any, job_id: str, logger: Any) -> None:
    if not getattr(settings, "redis_enabled", False):
        return

    try:
        Redis = importlib.import_module("redis").Redis
        Queue = importlib.import_module("rq").Queue
        process_pipeline_task = importlib.import_module("scripts.jobs").process_pipeline_task

        redis_conn = Redis.from_url(settings.redis_url)
        queue = Queue("pipeline", connection=redis_conn)
        queue.enqueue(process_pipeline_task, job_id, job_timeout=3600)
    except Exception as error:
        logger.warning("Could not enqueue job: %s", error)
