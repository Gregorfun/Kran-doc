"""Tools package for Kran-Doc project."""

__version__ = "0.5.0"

# Export wichtige Funktionen für einfacheren Import
from tools.cache_manager import cached, get_cache_manager
from tools.performance_monitor import profile, print_performance_report, save_performance_report

__all__ = [
    "profile",
    "cached",
    "get_cache_manager",
    "print_performance_report",
    "save_performance_report",
]
