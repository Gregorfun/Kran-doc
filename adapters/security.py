"""
Security Helpers
================

Rate limiting, upload protection, auth helpers
"""

from __future__ import annotations

import functools
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import abort, jsonify, request

# ============================================================
# Rate Limiting (In-Memory)
# ============================================================


class InMemoryRateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self):
        self.requests: Dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        """
        Check if request is allowed

        Args:
            key: Unique key (e.g., IP address)
            limit: Max requests per window
            window: Time window in seconds

        Returns:
            True if allowed, False if rate limit exceeded
        """
        now = time.time()
        cutoff = now - window

        # Clean old requests
        self.requests[key] = [ts for ts in self.requests[key] if ts > cutoff]

        # Check limit
        if len(self.requests[key]) >= limit:
            return False

        # Add request
        self.requests[key].append(now)
        return True

    def cleanup_old(self, max_age: int = 3600):
        """Cleanup old entries"""
        now = time.time()
        cutoff = now - max_age

        keys_to_delete = []
        for key, timestamps in self.requests.items():
            # Remove old timestamps
            self.requests[key] = [ts for ts in timestamps if ts > cutoff]
            # Mark empty keys for deletion
            if not self.requests[key]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.requests[key]


# Global rate limiter
_rate_limiter = InMemoryRateLimiter()


def rate_limit(limit: int = 60, window: int = 60):
    """
    Rate limit decorator

    Args:
        limit: Max requests per window
        window: Time window in seconds

    Usage:
        @rate_limit(limit=10, window=60)  # 10 requests per minute
        def my_endpoint():
            ...
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Get client identifier (IP address)
            client_ip = request.remote_addr or "unknown"

            # Check rate limit
            if not _rate_limiter.is_allowed(client_ip, limit, window):
                return (
                    jsonify({"error": "Rate limit exceeded", "message": f"Max {limit} requests per {window} seconds"}),
                    429,
                )

            return f(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# API Key Auth
# ============================================================


def require_api_key(f: Callable) -> Callable:
    """
    Require API key for endpoint

    Usage:
        @require_api_key
        def protected_endpoint():
            ...
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        from config.settings import settings

        if not settings.api_key:
            # API key not configured, allow access
            return f(*args, **kwargs)

        # Check API key in header or query param
        provided_key = request.headers.get("X-API-Key") or request.args.get("api_key")

        if not provided_key or provided_key != settings.api_key:
            return jsonify({"error": "Unauthorized", "message": "Valid API key required"}), 401

        return f(*args, **kwargs)

    return wrapper


# ============================================================
# Upload Protection
# ============================================================

ALLOWED_EXTENSIONS = {"pdf", "PDF"}
ALLOWED_MIME_TYPES = {"application/pdf", "application/x-pdf"}


def validate_upload_file(file) -> tuple[bool, Optional[str]]:
    """
    Validate uploaded file

    Returns:
        (is_valid, error_message)
    """
    from config.settings import settings

    if not file:
        return False, "No file provided"

    if file.filename == "":
        return False, "No file selected"

    # Check extension
    if "." not in file.filename:
        return False, "File has no extension"

    ext = file.filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file type. Allowed: PDF only"

    # Check MIME type
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"Invalid MIME type: {file.content_type}"

    # Check file size (read first chunk to estimate)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset

    max_size = settings.max_upload_size_mb * 1024 * 1024
    if size > max_size:
        return False, f"File too large. Max size: {settings.max_upload_size_mb} MB"

    return True, None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal

    Returns:
        Safe filename
    """
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove parent directory references
    filename = filename.replace("..", "")

    # Remove other dangerous characters
    dangerous = ["<", ">", ":", '"', "|", "?", "*", "\0"]
    for char in dangerous:
        filename = filename.replace(char, "_")

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        max_name_len = 255 - len(ext) - 1
        filename = name[:max_name_len] + "." + ext if ext else name[:255]

    return filename


def validate_path_access(requested_path: Path, allowed_base: Path) -> bool:
    """
    Validate that requested path is within allowed base directory

    Prevents path traversal attacks

    Args:
        requested_path: Path requested by user
        allowed_base: Base directory that should contain the path

    Returns:
        True if path is safe, False otherwise
    """
    try:
        requested_abs = requested_path.resolve(strict=False)
        allowed_abs = allowed_base.resolve(strict=True)

        requested_abs.relative_to(allowed_abs)
        return True

    except ValueError:
        return False
    except Exception:
        return False


# ============================================================
# Session Management
# ============================================================


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current user from session"""
    from flask import session

    user_id = session.get("user_id")
    if not user_id:
        return None

    # Load user from storage
    # (Implementation depends on your user storage)
    return {"user_id": user_id}


def require_auth(f: Callable) -> Callable:
    """
    Require authentication for endpoint

    Usage:
        @require_auth
        def protected_endpoint():
            ...
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

        return f(*args, **kwargs)

    return wrapper


def require_role(role: str):
    """
    Require specific role for endpoint

    Usage:
        @require_role('admin')
        def admin_endpoint():
            ...
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Unauthorized", "message": "Authentication required"}), 401

            user_role = user.get("role", "viewer")
            if user_role != role and user_role != "admin":
                return jsonify({"error": "Forbidden", "message": f"Role {role} required"}), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator
