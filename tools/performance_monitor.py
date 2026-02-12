#!/usr/bin/env python3
"""
Performance Monitor - Profiling und Performance-Monitoring für Kran-Tools.

Dieses Tool bietet:
- Funktions-Profiling mit Decorators
- Memory-Tracking
- Execution-Zeit-Messung
- Performance-Reports
- Bottleneck-Analyse
"""

from __future__ import annotations

import functools
import json
import logging
import time
import tracemalloc
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Einzelne Performance-Metrik."""

    function_name: str
    execution_time: float
    memory_delta: float  # in MB
    timestamp: float
    call_count: int = 1


class PerformanceMonitor:
    """
    Zentrale Klasse für Performance-Monitoring.
    
    Verwendung:
        monitor = PerformanceMonitor()
        
        @monitor.profile
        def my_function():
            pass
            
        monitor.print_report()
    """

    def __init__(self):
        self.metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        self.enabled = True
        self._memory_tracking = False

    def enable_memory_tracking(self):
        """Aktiviert Memory-Tracking (kann Performance beeinträchtigen)."""
        if not self._memory_tracking:
            tracemalloc.start()
            self._memory_tracking = True

    def disable_memory_tracking(self):
        """Deaktiviert Memory-Tracking."""
        if self._memory_tracking:
            tracemalloc.stop()
            self._memory_tracking = False

    def profile(self, func: Callable) -> Callable:
        """
        Decorator für Performance-Profiling einer Funktion.
        
        Args:
            func: Zu profilierende Funktion
            
        Returns:
            Wrapped function mit Profiling
        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self.enabled:
                return func(*args, **kwargs)

            # Memory snapshot vor Ausführung
            memory_before = 0
            if self._memory_tracking:
                memory_before = tracemalloc.get_traced_memory()[0] / 1024 / 1024

            # Zeit messen
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Ausführungszeit
                execution_time = time.perf_counter() - start_time

                # Memory snapshot nach Ausführung
                memory_delta = 0
                if self._memory_tracking:
                    memory_after = tracemalloc.get_traced_memory()[0] / 1024 / 1024
                    memory_delta = memory_after - memory_before

                # Metrik speichern
                metric = PerformanceMetric(
                    function_name=func.__name__,
                    execution_time=execution_time,
                    memory_delta=memory_delta,
                    timestamp=time.time(),
                )

                self.metrics[func.__name__].append(metric)

        return wrapper

    def get_statistics(self) -> Dict[str, Dict[str, float]]:
        """
        Berechnet Statistiken für alle profilierten Funktionen.
        
        Returns:
            Dict mit Statistiken pro Funktion
        """
        stats = {}

        for func_name, metrics in self.metrics.items():
            if not metrics:
                continue

            times = [m.execution_time for m in metrics]
            memories = [m.memory_delta for m in metrics]

            stats[func_name] = {
                "call_count": len(metrics),
                "total_time": sum(times),
                "avg_time": sum(times) / len(times),
                "min_time": min(times),
                "max_time": max(times),
                "avg_memory_mb": sum(memories) / len(memories) if memories else 0,
                "total_memory_mb": sum(memories) if memories else 0,
            }

        return stats

    def print_report(self, top_n: int = 20):
        """
        Gibt einen formatierten Performance-Report aus.
        
        Args:
            top_n: Anzahl der Top-Funktionen nach Gesamtzeit
        """
        stats = self.get_statistics()

        if not stats:
            print("Keine Performance-Metriken verfügbar.")
            return

        print("\n" + "=" * 80)
        print("PERFORMANCE REPORT")
        print("=" * 80)

        # Sortiere nach Gesamtzeit
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]["total_time"], reverse=True)

        print(f"\n{'Funktion':<40} {'Calls':<8} {'Total (s)':<12} {'Avg (s)':<12} {'Memory (MB)':<12}")
        print("-" * 80)

        for func_name, data in sorted_stats[:top_n]:
            print(
                f"{func_name:<40} "
                f"{data['call_count']:<8} "
                f"{data['total_time']:<12.4f} "
                f"{data['avg_time']:<12.4f} "
                f"{data['avg_memory_mb']:<12.2f}"
            )

        print("=" * 80 + "\n")

    def save_report(self, output_path: Path):
        """
        Speichert den Performance-Report als JSON.
        
        Args:
            output_path: Pfad zur Ausgabedatei
        """
        stats = self.get_statistics()

        report = {
            "timestamp": time.time(),
            "statistics": stats,
            "metrics": {
                func_name: [asdict(m) for m in metrics] for func_name, metrics in self.metrics.items()
            },
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Performance-Report gespeichert: {output_path}")

    def reset(self):
        """Setzt alle Metriken zurück."""
        self.metrics.clear()


# Globale Monitor-Instanz
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Liefert die globale PerformanceMonitor-Instanz."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def profile(func: Callable) -> Callable:
    """
    Convenience-Decorator für Performance-Profiling.
    
    Verwendung:
        from tools.performance_monitor import profile
        
        @profile
        def my_function():
            pass
    """
    return get_monitor().profile(func)


def print_performance_report(top_n: int = 20):
    """Gibt den globalen Performance-Report aus."""
    get_monitor().print_report(top_n)


def save_performance_report(output_path: Path):
    """Speichert den globalen Performance-Report."""
    get_monitor().save_report(output_path)


if __name__ == "__main__":
    # Test-Beispiel
    monitor = PerformanceMonitor()
    monitor.enable_memory_tracking()

    @monitor.profile
    def test_function():
        time.sleep(0.1)
        return sum(range(1000000))

    @monitor.profile
    def another_function():
        time.sleep(0.05)
        return [i * 2 for i in range(100000)]

    # Simuliere mehrere Aufrufe
    for _ in range(5):
        test_function()
    for _ in range(3):
        another_function()

    monitor.print_report()
