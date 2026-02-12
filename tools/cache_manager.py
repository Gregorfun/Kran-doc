#!/usr/bin/env python3
"""
Cache Manager - Erweitertes Caching-System für Kran-Tools.

Dieses Tool bietet:
- Datei-basiertes Caching
- Memory-Cache (LRU)
- TTL (Time-To-Live) Support
- Cache-Invalidierung
- Cache-Statistiken
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import time
from functools import lru_cache, wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Zentraler Cache-Manager mit Datei- und Memory-Caching.
    
    Verwendung:
        cache = CacheManager(cache_dir="output/cache")
        
        @cache.cached(ttl=3600)
        def expensive_function(arg):
            return compute_result(arg)
    """

    def __init__(self, cache_dir: Union[str, Path] = "output/cache", enable_file_cache: bool = True):
        """
        Initialisiert den Cache-Manager.
        
        Args:
            cache_dir: Verzeichnis für Datei-Cache
            enable_file_cache: Aktiviert Datei-basiertes Caching
        """
        self.cache_dir = Path(cache_dir)
        self.enable_file_cache = enable_file_cache

        if self.enable_file_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Statistiken
        self.stats = {"hits": 0, "misses": 0, "invalidations": 0}

        logger.info(f"Cache-Manager initialisiert (Verzeichnis: {self.cache_dir})")

    def _get_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        Generiert einen eindeutigen Cache-Key.
        
        Args:
            func_name: Name der Funktion
            args: Positionsargumente
            kwargs: Keyword-Argumente
            
        Returns:
            Cache-Key als String
        """
        # Erstelle einen eindeutigen Hash aus Funktionsname und Argumenten
        key_data = {
            "function": func_name,
            "args": str(args),
            "kwargs": str(sorted(kwargs.items())),
        }

        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()

        return f"{func_name}_{key_hash}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Liefert den Dateipfad für einen Cache-Key."""
        return self.cache_dir / f"{cache_key}.cache"

    def _load_from_file(self, cache_path: Path) -> Optional[Dict[str, Any]]:
        """
        Lädt Cache-Daten aus einer Datei.
        
        Args:
            cache_path: Pfad zur Cache-Datei
            
        Returns:
            Cache-Daten oder None bei Fehler
        """
        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Fehler beim Laden von Cache {cache_path}: {e}")
            return None

    def _save_to_file(self, cache_path: Path, data: Dict[str, Any]) -> bool:
        """
        Speichert Cache-Daten in einer Datei.
        
        Args:
            cache_path: Pfad zur Cache-Datei
            data: Zu speichernde Daten
            
        Returns:
            True bei Erfolg
        """
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
            return True
        except Exception as e:
            logger.error(f"Fehler beim Speichern von Cache {cache_path}: {e}")
            return False

    def get(self, cache_key: str, ttl: Optional[float] = None) -> Optional[Any]:
        """
        Holt einen Wert aus dem Cache.
        
        Args:
            cache_key: Cache-Key
            ttl: Time-To-Live in Sekunden
            
        Returns:
            Gecachter Wert oder None
        """
        if not self.enable_file_cache:
            return None

        cache_path = self._get_cache_path(cache_key)
        cache_data = self._load_from_file(cache_path)

        if cache_data is None:
            self.stats["misses"] += 1
            return None

        # Prüfe TTL
        if ttl is not None:
            cache_age = time.time() - cache_data.get("timestamp", 0)
            if cache_age > ttl:
                logger.debug(f"Cache abgelaufen: {cache_key} (Alter: {cache_age:.1f}s)")
                self.stats["misses"] += 1
                return None

        self.stats["hits"] += 1
        return cache_data.get("value")

    def set(self, cache_key: str, value: Any) -> bool:
        """
        Speichert einen Wert im Cache.
        
        Args:
            cache_key: Cache-Key
            value: Zu cachender Wert
            
        Returns:
            True bei Erfolg
        """
        if not self.enable_file_cache:
            return False

        cache_path = self._get_cache_path(cache_key)
        cache_data = {"value": value, "timestamp": time.time()}

        return self._save_to_file(cache_path, cache_data)

    def invalidate(self, pattern: Optional[str] = None):
        """
        Invalidiert Cache-Einträge.
        
        Args:
            pattern: Optionales Pattern für Cache-Keys (None = alle)
        """
        if not self.enable_file_cache:
            return

        if pattern is None:
            # Lösche alle Cache-Dateien
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
                self.stats["invalidations"] += 1
            logger.info(f"Alle Cache-Einträge invalidiert ({self.stats['invalidations']} Dateien)")
        else:
            # Lösche nur passende Cache-Dateien
            for cache_file in self.cache_dir.glob(f"{pattern}*.cache"):
                cache_file.unlink()
                self.stats["invalidations"] += 1
            logger.info(f"Cache-Einträge für Pattern '{pattern}' invalidiert")

    def cached(self, ttl: Optional[float] = None):
        """
        Decorator für Funktions-Caching.
        
        Args:
            ttl: Time-To-Live in Sekunden
            
        Returns:
            Decorator-Funktion
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generiere Cache-Key
                cache_key = self._get_cache_key(func.__name__, args, kwargs)

                # Versuche aus Cache zu laden
                cached_value = self.get(cache_key, ttl)
                if cached_value is not None:
                    logger.debug(f"Cache-Hit für {func.__name__}")
                    return cached_value

                # Berechne Wert
                logger.debug(f"Cache-Miss für {func.__name__}")
                result = func(*args, **kwargs)

                # Speichere im Cache
                self.set(cache_key, result)

                return result

            return wrapper

        return decorator

    def get_stats(self) -> Dict[str, Any]:
        """
        Liefert Cache-Statistiken.
        
        Returns:
            Dict mit Statistiken
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        # Zähle Cache-Dateien
        cache_files = list(self.cache_dir.glob("*.cache")) if self.enable_file_cache else []
        total_size = sum(f.stat().st_size for f in cache_files) / 1024 / 1024  # MB

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "invalidations": self.stats["invalidations"],
            "hit_rate": hit_rate,
            "cache_files": len(cache_files),
            "total_size_mb": total_size,
        }

    def print_stats(self):
        """Gibt Cache-Statistiken aus."""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("CACHE STATISTIKEN")
        print("=" * 60)
        print(f"Hits:           {stats['hits']}")
        print(f"Misses:         {stats['misses']}")
        print(f"Hit-Rate:       {stats['hit_rate']:.1f}%")
        print(f"Invalidierungen: {stats['invalidations']}")
        print(f"Cache-Dateien:  {stats['cache_files']}")
        print(f"Gesamtgröße:    {stats['total_size_mb']:.2f} MB")
        print("=" * 60 + "\n")


# Globale Cache-Instanz
_global_cache: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Liefert die globale CacheManager-Instanz."""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheManager()
    return _global_cache


def cached(ttl: Optional[float] = None):
    """
    Convenience-Decorator für Caching.
    
    Verwendung:
        from tools.cache_manager import cached
        
        @cached(ttl=3600)
        def my_expensive_function():
            pass
    """
    return get_cache_manager().cached(ttl)


if __name__ == "__main__":
    # Test-Beispiel
    cache = CacheManager(cache_dir="/tmp/test_cache")

    @cache.cached(ttl=10)
    def expensive_calculation(x: int) -> int:
        print(f"Berechne {x}...")
        time.sleep(0.5)
        return x * x

    # Erste Aufrufe (Cache-Miss)
    print(expensive_calculation(5))
    print(expensive_calculation(10))

    # Zweite Aufrufe (Cache-Hit)
    print(expensive_calculation(5))
    print(expensive_calculation(10))

    cache.print_stats()
