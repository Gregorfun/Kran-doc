"""Unit-Tests für Tools-Module."""

from __future__ import annotations

import time
from pathlib import Path

import pytest


@pytest.mark.unit
def test_performance_monitor_basic():
    """Test für grundlegende Performance-Monitoring-Funktionalität."""
    from tools.performance_monitor import PerformanceMonitor

    monitor = PerformanceMonitor()

    @monitor.profile
    def test_function():
        time.sleep(0.01)
        return 42

    result = test_function()
    assert result == 42

    stats = monitor.get_statistics()
    assert "test_function" in stats
    assert stats["test_function"]["call_count"] == 1
    assert stats["test_function"]["total_time"] > 0


@pytest.mark.unit
def test_cache_manager_basic(tmp_path):
    """Test für grundlegende Cache-Funktionalität."""
    from tools.cache_manager import CacheManager

    cache = CacheManager(cache_dir=tmp_path / "cache")

    call_count = 0

    @cache.cached(ttl=10)
    def expensive_function(x: int) -> int:
        nonlocal call_count
        call_count += 1
        return x * x

    # Erster Aufruf - Cache-Miss
    result1 = expensive_function(5)
    assert result1 == 25
    assert call_count == 1

    # Zweiter Aufruf - Cache-Hit
    result2 = expensive_function(5)
    assert result2 == 25
    assert call_count == 1  # Funktion wurde nicht erneut aufgerufen

    stats = cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1


@pytest.mark.unit
def test_parallel_processor_basic():
    """Test für grundlegende Parallel-Processing-Funktionalität."""
    from tools.parallel_processor import ParallelProcessor

    processor = ParallelProcessor(max_workers=2)

    def dummy_process(file: Path):
        return {"file": str(file), "size": 100}

    test_files = [Path(f"test_{i}.pdf") for i in range(5)]
    results = processor.process_files(
        files=test_files,
        process_func=dummy_process,
        use_processes=False,  # Threading für Tests
        show_progress=False,
    )

    assert len(results) == 5
    assert all(r.success for r in results)


@pytest.mark.unit
def test_config_loader():
    """Test für Config-Loader."""
    from scripts.config_loader import get_config

    config = get_config()
    assert config is not None
    assert hasattr(config, "input_pdf_dir")
    assert hasattr(config, "models_dir")
    assert hasattr(config, "ocr_enabled")


@pytest.mark.unit
def test_model_detection():
    """Test für Modell-Erkennung."""
    from scripts.model_detection import detect_model

    # Test mit bekannten Modellnamen
    model1 = detect_model("LTM1110-5.1")
    assert model1 == "LTM1110-5.1"

    model2 = detect_model("LTC1050-3.1 Fehlercode.pdf")
    assert "LTC1050" in model2


@pytest.mark.unit
def test_logger_module():
    """Test für Logger-Modul."""
    from scripts.logger import setup_logger

    logger = setup_logger("test_logger")
    assert logger is not None
    assert logger.name == "test_logger"
