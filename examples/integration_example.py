#!/usr/bin/env python3
"""Integration example for new performance tools."""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from tools.cache_manager import cached, get_cache_manager
from tools.parallel_processor import process_pdfs_parallel
from tools.performance_monitor import get_monitor, profile


@profile
def parse_pdf_example(pdf_path: Path) -> Dict:
    """Example: Profile a parser function."""
    import time
    time.sleep(0.1)
    return {"file": str(pdf_path), "errors": [{"code": "1A0050"}]}


@cached(ttl=3600)
@profile
def calculate_embeddings_cached(text: str) -> List[float]:
    """Example: Cache expensive calculations."""
    import time
    time.sleep(0.5)
    return [0.1, 0.2, 0.3, 0.4, 0.5]


def demo_tools():
    """Demo all new tools."""
    print("\n" + "=" * 80)
    print("DEMO: New Performance Tools")
    print("=" * 80 + "\n")

    test_files = [Path(f"test_{i}.pdf") for i in range(10)]

    # Demo 1: Profiling
    print("1. Performance Monitoring")
    for i in range(3):
        parse_pdf_example(test_files[i])

    # Demo 2: Caching
    print("\n2. Caching (first call slow, second fast)")
    calculate_embeddings_cached("test")
    calculate_embeddings_cached("test")

    # Demo 3: Parallel Processing
    print("\n3. Parallel Processing")
    results, failed = process_pdfs_parallel(test_files, parse_pdf_example, max_workers=4)
    print(f"Processed: {len(results)}, Failed: {len(failed)}")

    # Reports
    print("\n4. Reports")
    get_monitor().print_report()
    get_cache_manager().print_stats()


if __name__ == "__main__":
    demo_tools()
