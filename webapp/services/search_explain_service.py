from __future__ import annotations

from typing import Any, Dict, List


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def attach_search_explainability(*, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for result in results or []:
        if not isinstance(result, dict):
            continue
        meta = result.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            result["metadata"] = meta

        reason_parts: List[str] = []
        source_type = result.get("source_type") or meta.get("source_type")
        score = _safe_float(result.get("score"))
        if source_type:
            reason_parts.append(f"Quelle: {source_type}")
        reason_parts.append(f"Score: {score:.3f}")

        if meta.get("error_code"):
            reason_parts.append(f"Code-Match: {meta.get('error_code')}")
        elif meta.get("code"):
            reason_parts.append(f"Code-Match: {meta.get('code')}")

        if meta.get("lsb_error_key"):
            reason_parts.append(f"LSB-Key: {meta.get('lsb_error_key')}")
        elif meta.get("lsb_key"):
            reason_parts.append(f"LSB-Key: {meta.get('lsb_key')}")

        if meta.get("sensor_bmk"):
            reason_parts.append(f"BMK: {meta.get('sensor_bmk')}")

        meta["why_this_result"] = " | ".join(reason_parts)
        result["metadata"] = meta

    return results


def confidence_summary(*, results: List[Dict[str, Any]], threshold: float) -> Dict[str, Any]:
    best_score = 0.0
    if results:
        best_score = max((_safe_float(item.get("score")) for item in results if isinstance(item, dict)), default=0.0)
    confident = best_score >= float(threshold)
    return {
        "best_score": round(best_score, 4),
        "threshold": float(threshold),
        "confident": confident,
        "fallback_recommended": not confident,
    }