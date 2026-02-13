"""
RQ Worker
=========

Redis Queue Worker für asynchrone Job-Verarbeitung
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from redis import Redis
    from rq import Connection, Queue, Worker

    RQ_AVAILABLE = True
except ImportError:
    RQ_AVAILABLE = False
    print("Warning: RQ not installed. Install with: pip install rq")

from config.settings import settings


def start_worker():
    """Start RQ worker"""
    if not RQ_AVAILABLE:
        print("Error: RQ is not installed")
        sys.exit(1)

    if not settings.redis_enabled:
        print("Error: Redis is not enabled in settings")
        print("Set KRANDOC_REDIS_ENABLED=true in .env")
        sys.exit(1)

    try:
        redis_conn = Redis.from_url(settings.redis_url)
        redis_conn.ping()
    except Exception as e:
        print(f"Error: Cannot connect to Redis at {settings.redis_url}")
        print(f"Details: {e}")
        sys.exit(1)

    print(f"Starting RQ worker...")
    print(f"Redis URL: {settings.redis_url}")
    print(f"Queues: default, pipeline")

    with Connection(redis_conn):
        worker = Worker(["default", "pipeline"])
        worker.work()


if __name__ == "__main__":
    start_worker()
