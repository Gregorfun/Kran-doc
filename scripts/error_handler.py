"""
Error-Handling Utilities für PDFDoc / Kran-Tools

Bietet Dekoratoren und Funktionen für robustes Error-Handling.

Verwendung:
    from scripts.error_handler import safe_execute, retry_on_failure
    
    @retry_on_failure(max_attempts=3)
    def risky_operation():
        # Code der fehlschlagen könnte
        pass
"""

from __future__ import annotations

import functools
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Optional, Type, TypeVar, Union, Tuple

from scripts.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def safe_execute(
    func: Callable[..., T],
    *args: Any,
    default: Optional[T] = None,
    log_error: bool = True,
    **kwargs: Any
) -> Optional[T]:
    """
    Führt eine Funktion sicher aus und fängt Exceptions ab.
    
    Args:
        func: Auszuführende Funktion
        *args: Positionelle Argumente für func
        default: Rückgabewert bei Fehler
        log_error: Ob Fehler geloggt werden sollen
        **kwargs: Keyword-Argumente für func
        
    Returns:
        Rückgabewert der Funktion oder default bei Fehler
        
    Example:
        >>> result = safe_execute(int, "123", default=0)
        >>> result
        123
        >>> result = safe_execute(int, "abc", default=0)
        >>> result
        0
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_error:
            logger.error(f"Fehler in {func.__name__}: {e}")
            logger.debug(traceback.format_exc())
        return default


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (IOError, ConnectionError, TimeoutError)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Dekorator der eine Funktion bei Fehler wiederholt.
    
    Args:
        max_attempts: Maximale Anzahl Versuche
        delay: Initiale Wartezeit zwischen Versuchen (Sekunden)
        backoff: Multiplikator für Delay nach jedem Versuch
        exceptions: Tuple von Exceptions die zu Retry führen
        
    Returns:
        Dekorierte Funktion
        
    Example:
        >>> @retry_on_failure(max_attempts=3, delay=1.0)
        ... def flaky_api_call():
        ...     response = requests.get("https://api.example.com/data")
        ...     return response.json()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} fehlgeschlagen nach {max_attempts} Versuchen: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"{func.__name__} fehlgeschlagen (Versuch {attempt}/{max_attempts}). "
                        f"Warte {current_delay:.1f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # Dieser Code sollte nie erreicht werden
            raise RuntimeError(f"{func.__name__}: Unerreichbarer Code")
        
        return wrapper
    return decorator


def validate_file_exists(file_path: Union[str, Path]) -> Path:
    """
    Validiert dass eine Datei existiert.
    
    Args:
        file_path: Pfad zur Datei
        
    Returns:
        Path-Objekt wenn Datei existiert
        
    Raises:
        FileNotFoundError: Wenn Datei nicht existiert
        
    Example:
        >>> path = validate_file_exists("config/config.yaml")
        >>> print(path)
        config/config.yaml
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Datei nicht gefunden: {path}")
    if not path.is_file():
        raise ValueError(f"Pfad ist keine Datei: {path}")
    return path


def validate_dir_exists(dir_path: Union[str, Path]) -> Path:
    """
    Validiert dass ein Verzeichnis existiert.
    
    Args:
        dir_path: Pfad zum Verzeichnis
        
    Returns:
        Path-Objekt wenn Verzeichnis existiert
        
    Raises:
        FileNotFoundError: Wenn Verzeichnis nicht existiert
        
    Example:
        >>> path = validate_dir_exists("input/lec")
        >>> print(path)
        input/lec
    """
    path = Path(dir_path)
    if not path.exists():
        raise FileNotFoundError(f"Verzeichnis nicht gefunden: {path}")
    if not path.is_dir():
        raise ValueError(f"Pfad ist kein Verzeichnis: {path}")
    return path


def ensure_dir_exists(dir_path: Union[str, Path]) -> Path:
    """
    Stellt sicher dass ein Verzeichnis existiert, erstellt es falls nötig.
    
    Args:
        dir_path: Pfad zum Verzeichnis
        
    Returns:
        Path-Objekt zum Verzeichnis
        
    Example:
        >>> path = ensure_dir_exists("output/models")
        >>> print(path.exists())
        True
    """
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


class PDFDocError(Exception):
    """Basis-Exception für PDFDoc-spezifische Fehler."""
    pass


class ParsingError(PDFDocError):
    """Fehler beim Parsen von PDF-Dokumenten."""
    pass


class ConfigurationError(PDFDocError):
    """Fehler in der Konfiguration."""
    pass


class ValidationError(PDFDocError):
    """Fehler bei der Validierung von Daten."""
    pass


def handle_errors(
    error_message: str = "Fehler aufgetreten",
    reraise: bool = False
) -> Callable[[Callable[..., T]], Callable[..., Optional[T]]]:
    """
    Dekorator für einheitliches Error-Handling.
    
    Args:
        error_message: Nachricht die bei Fehler geloggt wird
        reraise: Ob Exception nach Logging erneut geworfen werden soll
        
    Returns:
        Dekorierte Funktion
        
    Example:
        >>> @handle_errors("Fehler beim Lesen der Datei")
        ... def read_file(path):
        ...     with open(path) as f:
        ...         return f.read()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"{error_message} in {func.__name__}: {e}")
                logger.debug(traceback.format_exc())
                
                if reraise:
                    raise
                return None
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # Demo der Error-Handling Funktionen
    
    # safe_execute Demo
    logger.info("=== safe_execute Demo ===")
    result = safe_execute(int, "123", default=0)
    logger.info(f"Erfolgreich: {result}")
    
    result = safe_execute(int, "abc", default=0)
    logger.info(f"Mit Fehler (default): {result}")
    
    # retry_on_failure Demo
    logger.info("\n=== retry_on_failure Demo ===")
    
    attempt_counter = 0
    
    @retry_on_failure(max_attempts=3, delay=0.5)
    def flaky_function():
        global attempt_counter
        attempt_counter += 1
        if attempt_counter < 3:
            raise ValueError("Simulierter Fehler")
        return "Erfolg!"
    
    try:
        result = flaky_function()
        logger.info(f"Ergebnis nach {attempt_counter} Versuchen: {result}")
    except Exception as e:
        logger.error(f"Fehlgeschlagen: {e}")
    
    # handle_errors Demo
    logger.info("\n=== handle_errors Demo ===")
    
    @handle_errors("Fehler beim Teilen")
    def divide(a: int, b: int) -> float:
        return a / b
    
    result = divide(10, 2)
    logger.info(f"10 / 2 = {result}")
    
    result = divide(10, 0)
    logger.info(f"10 / 0 = {result} (None wegen Error)")
