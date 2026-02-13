"""
Docling Integration für Kran-Doc
=================================

Integriert Docling für fortgeschrittenes PDF-Parsing mit:
- Layout-Erkennung
- Tabellen-Extraktion
- Strukturierte Ausgabe

Author: Gregor
Version: 2.0
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling nicht installiert. Bitte installieren: pip install docling")


logger = logging.getLogger(__name__)


@dataclass
class DoclingConfig:
    """Konfiguration für Docling-Parser"""

    enable_table_structure: bool = True
    enable_ocr: bool = True
    ocr_engine: str = "easyocr"  # oder "tesseract"
    generate_picture_images: bool = False
    generate_page_images: bool = False
    do_cell_matching: bool = True

    # Performance
    max_workers: int = 4
    verbose: bool = False


class DoclingProcessor:
    """
    Haupt-Parser für PDF-Dokumente mit Docling

    Beispiel:
        processor = DoclingProcessor()
        result = processor.process_pdf("manual.pdf")
    """

    def __init__(self, config: Optional[DoclingConfig] = None):
        if not DOCLING_AVAILABLE:
            raise ImportError("Docling ist nicht installiert. " "Installieren Sie es mit: pip install docling")

        self.config = config or DoclingConfig()
        self.converter = self._init_converter()
        logger.info("DoclingProcessor initialisiert")

    def _init_converter(self) -> DocumentConverter:
        """Initialisiert Docling DocumentConverter"""
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = self.config.enable_table_structure
        pipeline_options.do_ocr = self.config.enable_ocr
        pipeline_options.generate_picture_images = self.config.generate_picture_images
        pipeline_options.generate_page_images = self.config.generate_page_images

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pipeline_options,
            }
        )

        return converter

    def process_pdf(self, pdf_path: str, output_format: str = "markdown") -> Dict[str, Any]:
        """
        Verarbeitet PDF mit Docling

        Args:
            pdf_path: Pfad zur PDF-Datei
            output_format: Ausgabeformat ("markdown", "json", "docling_document")

        Returns:
            Dict mit geparsten Daten und Metadaten
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF nicht gefunden: {pdf_path}")

        logger.info(f"Verarbeite PDF mit Docling: {pdf_path.name}")

        try:
            # Dokument konvertieren
            result = self.converter.convert(str(pdf_path))

            # Ergebnis extrahieren
            parsed_data = self._extract_content(result, output_format)

            # Metadaten
            metadata = {
                "source_file": pdf_path.name,
                "page_count": len(result.document.pages) if hasattr(result.document, "pages") else 0,
                "has_tables": self._has_tables(result),
                "has_images": self._has_images(result),
                "processing_time": result.metadata.get("processing_time", 0) if hasattr(result, "metadata") else 0,
            }

            return {
                "content": parsed_data,
                "metadata": metadata,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Fehler beim Parsen mit Docling: {e}")
            return {
                "content": None,
                "metadata": {"error": str(e)},
                "success": False,
            }

    def _extract_content(self, result, output_format: str) -> Any:
        """Extrahiert Inhalt im gewünschten Format"""

        if output_format == "markdown":
            return result.document.export_to_markdown()

        elif output_format == "json":
            return result.document.export_to_dict()

        elif output_format == "docling_document":
            return result.document

        else:
            raise ValueError(f"Unbekanntes Format: {output_format}")

    def _has_tables(self, result) -> bool:
        """Prüft ob Tabellen im Dokument vorhanden sind"""
        try:
            doc = result.document
            if hasattr(doc, "tables"):
                return len(doc.tables) > 0
            return False
        except:
            return False

    def _has_images(self, result) -> bool:
        """Prüft ob Bilder im Dokument vorhanden sind"""
        try:
            doc = result.document
            if hasattr(doc, "pictures"):
                return len(doc.pictures) > 0
            return False
        except:
            return False

    def extract_tables(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extrahiert nur Tabellen aus PDF

        Returns:
            Liste von Tabellen mit Struktur
        """
        result = self.process_pdf(pdf_path, output_format="docling_document")

        if not result["success"]:
            return []

        doc = result["content"]
        tables = []

        if hasattr(doc, "tables"):
            for i, table in enumerate(doc.tables):
                tables.append(
                    {
                        "table_id": i,
                        "page": table.page if hasattr(table, "page") else None,
                        "data": self._parse_table(table),
                        "cells": len(table.cells) if hasattr(table, "cells") else 0,
                    }
                )

        return tables

    def _parse_table(self, table) -> List[List[str]]:
        """Konvertiert Docling-Tabelle zu 2D-Liste"""
        # Vereinfachte Implementierung
        # In der Praxis würde man table.cells iterieren
        try:
            if hasattr(table, "export_to_dataframe"):
                df = table.export_to_dataframe()
                return df.values.tolist()
        except:
            pass

        return []

    def extract_text_by_page(self, pdf_path: str) -> Dict[int, str]:
        """
        Extrahiert Text seitenweise

        Returns:
            Dict {page_number: text_content}
        """
        result = self.process_pdf(pdf_path, output_format="docling_document")

        if not result["success"]:
            return {}

        doc = result["content"]
        pages = {}

        if hasattr(doc, "pages"):
            for i, page in enumerate(doc.pages, 1):
                if hasattr(page, "text"):
                    pages[i] = page.text
                elif hasattr(page, "export_to_text"):
                    pages[i] = page.export_to_text()

        return pages


class DoclingNormalizer:
    """
    Normalisiert Docling-Output zu einheitlichem Format

    Konvertiert Docling-Strukturen in Kran-Doc-spezifische
    Formate (JSON, Chunks, etc.)
    """

    @staticmethod
    def normalize_to_chunks(
        markdown_content: str, metadata: Dict[str, Any], chunk_size: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Teilt Markdown in Chunks für Embeddings

        Args:
            markdown_content: Markdown vom Docling
            metadata: Metadaten des Dokuments
            chunk_size: Maximale Chunk-Größe in Zeichen

        Returns:
            Liste von Chunks mit Metadaten
        """
        chunks = []

        # Einfache Chunking-Strategie (kann später mit Docling-Agent ersetzt werden)
        paragraphs = markdown_content.split("\n\n")

        current_chunk = ""
        chunk_id = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) > chunk_size:
                if current_chunk:
                    chunks.append(
                        {
                            "chunk_id": f"{metadata.get('source_file', 'unknown')}_{chunk_id}",
                            "text": current_chunk.strip(),
                            "metadata": {
                                **metadata,
                                "chunk_index": chunk_id,
                            },
                        }
                    )
                    chunk_id += 1
                current_chunk = para
            else:
                current_chunk += "\n\n" + para

        # Letzter Chunk
        if current_chunk:
            chunks.append(
                {
                    "chunk_id": f"{metadata.get('source_file', 'unknown')}_{chunk_id}",
                    "text": current_chunk.strip(),
                    "metadata": {
                        **metadata,
                        "chunk_index": chunk_id,
                    },
                }
            )

        return chunks

    @staticmethod
    def normalize_table_to_dict(table_data: List[List[str]]) -> Dict[str, List[str]]:
        """
        Konvertiert Tabelle zu strukturiertem Dict

        Nimmt erste Zeile als Header
        """
        if not table_data or len(table_data) < 2:
            return {}

        headers = table_data[0]
        result = {header: [] for header in headers}

        for row in table_data[1:]:
            for i, header in enumerate(headers):
                if i < len(row):
                    result[header].append(row[i])
                else:
                    result[header].append("")

        return result


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def process_pdf_with_docling(pdf_path: str, config: Optional[DoclingConfig] = None) -> Dict[str, Any]:
    """
    Convenience-Funktion für schnelles PDF-Processing

    Beispiel:
        result = process_pdf_with_docling("manual.pdf")
        print(result["content"])
    """
    processor = DoclingProcessor(config)
    return processor.process_pdf(pdf_path)


def check_docling_available() -> bool:
    """Prüft ob Docling verfügbar ist"""
    return DOCLING_AVAILABLE


# ============================================================
# MAIN (für Testing)
# ============================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if not DOCLING_AVAILABLE:
        print("❌ Docling nicht installiert!")
        print("   Installieren mit: pip install docling")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python docling_processor.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]

    print(f"📄 Verarbeite: {pdf_file}")
    print("-" * 60)

    processor = DoclingProcessor()
    result = processor.process_pdf(pdf_file, output_format="markdown")

    if result["success"]:
        print("✅ Erfolgreich geparst!")
        print(f"\n📊 Metadaten:")
        for key, value in result["metadata"].items():
            print(f"   {key}: {value}")

        print(f"\n📝 Inhalt (erste 500 Zeichen):")
        print(result["content"][:500])
        print("...")
    else:
        print(f"❌ Fehler: {result['metadata'].get('error')}")
