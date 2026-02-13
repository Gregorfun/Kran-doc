from __future__ import annotations

from typing import Any, Callable, Dict, List


def parse_limit(value: Any, default: int = 10, minimum: int = 1, maximum: int = 200) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(parsed, maximum))


def serialize_job_steps(steps: List[Any], limit: int) -> List[Dict[str, Any]]:
    if limit < len(steps):
        selected = steps[-limit:]
    else:
        selected = steps

    return [
        {
            "step": step.step,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "finished_at": step.finished_at.isoformat() if step.finished_at else None,
            "duration_ms": step.duration_ms,
            "method": step.method,
            "confidence": step.confidence,
            "error": step.error,
        }
        for step in selected
    ]


def get_job_status_payload(*, job_id: str, get_job: Callable[[str], Any]) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        return {"ok": False, "error": "Job not found", "status": 404}
    return {"ok": True, "payload": job.to_dict()}


def get_job_log_payload(*, job_id: str, raw_limit: Any, get_job: Callable[[str], Any]) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        return {"ok": False, "error": "Job not found", "status": 404}

    limit = parse_limit(raw_limit, default=10, minimum=1, maximum=200)
    return {
        "ok": True,
        "payload": {"steps": serialize_job_steps(job.steps, limit)},
    }
