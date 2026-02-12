#!/usr/bin/env python3
"""
Parallel Processor - Parallele Verarbeitung für PDF-Parsing.

Dieses Tool bietet:
- Multiprocessing für CPU-intensive Operationen
- Thread-Pool für I/O-intensive Operationen
- Progress-Tracking
- Error-Handling mit Retry-Logik
- Batch-Verarbeitung
"""

from __future__ import annotations

import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Ergebnis einer Verarbeitung."""

    input_file: Path
    success: bool
    result: Any = None
    error: Optional[str] = None
    duration: float = 0.0


class ParallelProcessor:
    """
    Paralleler Prozessor für PDF-Verarbeitung.
    
    Verwendung:
        processor = ParallelProcessor(max_workers=4)
        results = processor.process_files(
            files=pdf_files,
            process_func=parse_pdf,
            use_processes=True
        )
    """

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialisiert den Parallel Processor.
        
        Args:
            max_workers: Anzahl der Worker (None = CPU-Anzahl)
        """
        self.max_workers = max_workers or mp.cpu_count()
        logger.info(f"Parallel Processor initialisiert mit {self.max_workers} Workern")

    def process_files(
        self,
        files: List[Path],
        process_func: Callable[[Path], Any],
        use_processes: bool = True,
        show_progress: bool = True,
    ) -> List[ProcessingResult]:
        """
        Verarbeitet mehrere Dateien parallel.
        
        Args:
            files: Liste der zu verarbeitenden Dateien
            process_func: Funktion zur Verarbeitung einer einzelnen Datei
            use_processes: True für Multiprocessing, False für Threading
            show_progress: Zeigt Fortschrittsbalken an
            
        Returns:
            Liste der Verarbeitungsergebnisse
        """
        if not files:
            logger.warning("Keine Dateien zur Verarbeitung vorhanden")
            return []

        logger.info(f"Starte parallele Verarbeitung von {len(files)} Dateien...")

        results: List[ProcessingResult] = []
        executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

        with executor_class(max_workers=self.max_workers) as executor:
            # Submit alle Tasks
            future_to_file = {executor.submit(self._process_single, file, process_func): file for file in files}

            # Sammle Ergebnisse
            completed = 0
            for future in as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    if show_progress and completed % 10 == 0:
                        logger.info(f"Fortschritt: {completed}/{len(files)} Dateien verarbeitet")

                except Exception as e:
                    logger.error(f"Fehler bei Verarbeitung von {file}: {e}")
                    results.append(
                        ProcessingResult(
                            input_file=file,
                            success=False,
                            error=str(e),
                        )
                    )

        # Zusammenfassung
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        logger.info(f"Verarbeitung abgeschlossen: {successful} erfolgreich, {failed} fehlgeschlagen")

        return results

    def _process_single(self, file: Path, process_func: Callable[[Path], Any]) -> ProcessingResult:
        """
        Verarbeitet eine einzelne Datei.
        
        Args:
            file: Zu verarbeitende Datei
            process_func: Verarbeitungsfunktion
            
        Returns:
            Verarbeitungsergebnis
        """
        import time

        start_time = time.perf_counter()

        try:
            result = process_func(file)
            duration = time.perf_counter() - start_time

            return ProcessingResult(
                input_file=file,
                success=True,
                result=result,
                duration=duration,
            )

        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error(f"Fehler bei {file}: {e}")

            return ProcessingResult(
                input_file=file,
                success=False,
                error=str(e),
                duration=duration,
            )

    def process_in_batches(
        self,
        files: List[Path],
        process_func: Callable[[Path], Any],
        batch_size: int = 100,
        use_processes: bool = True,
    ) -> List[ProcessingResult]:
        """
        Verarbeitet Dateien in Batches.
        
        Args:
            files: Liste der Dateien
            process_func: Verarbeitungsfunktion
            batch_size: Größe der Batches
            use_processes: True für Multiprocessing
            
        Returns:
            Liste aller Ergebnisse
        """
        all_results = []

        for i in range(0, len(files), batch_size):
            batch = files[i : i + batch_size]
            logger.info(f"Verarbeite Batch {i // batch_size + 1} ({len(batch)} Dateien)...")

            batch_results = self.process_files(
                files=batch,
                process_func=process_func,
                use_processes=use_processes,
                show_progress=False,
            )

            all_results.extend(batch_results)

        return all_results


def process_pdfs_parallel(
    pdf_files: List[Path],
    parser_func: Callable[[Path], Dict[str, Any]],
    max_workers: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[Path]]:
    """
    Convenience-Funktion für parallele PDF-Verarbeitung.
    
    Args:
        pdf_files: Liste der PDF-Dateien
        parser_func: Parser-Funktion
        max_workers: Anzahl der Worker
        
    Returns:
        Tuple von (erfolgreiche Ergebnisse, fehlgeschlagene Dateien)
    """
    processor = ParallelProcessor(max_workers=max_workers)
    results = processor.process_files(files=pdf_files, process_func=parser_func, use_processes=True)

    successful_results = [r.result for r in results if r.success and r.result]
    failed_files = [r.input_file for r in results if not r.success]

    return successful_results, failed_files


if __name__ == "__main__":
    # Test-Beispiel
    import time

    def dummy_process(file: Path) -> Dict[str, Any]:
        """Dummy-Funktion für Tests."""
        time.sleep(0.1)  # Simuliere Verarbeitung
        return {"file": str(file), "lines": 100}

    # Erstelle Test-Dateien
    test_files = [Path(f"test_{i}.pdf") for i in range(20)]

    processor = ParallelProcessor(max_workers=4)
    results = processor.process_files(files=test_files, process_func=dummy_process)

    print(f"\nErgebnisse: {len(results)} Dateien verarbeitet")
    print(f"Erfolgreich: {sum(1 for r in results if r.success)}")
    print(f"Fehlgeschlagen: {sum(1 for r in results if not r.success)}")
