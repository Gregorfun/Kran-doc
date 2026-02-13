from __future__ import annotations

from typing import Any


def is_rate_limited(*, rate_limiter: Any, client_ip: str, max_requests: int, window_seconds: int) -> bool:
    return not rate_limiter.is_allowed(client_ip or "unknown", max_requests, window_seconds)


def is_api_key_valid(*, configured_key: str, provided_key: str) -> bool:
    if not configured_key:
        return True
    return bool(provided_key and provided_key == configured_key)


def get_provided_api_key(*, request: Any) -> str:
    return (request.headers.get("X-API-Key") or request.args.get("api_key") or "").strip()
