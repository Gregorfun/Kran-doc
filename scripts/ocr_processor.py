"""
OCR Integration für Kran-Doc
=============================

Integriert mehrere OCR-Engines:
- PaddleOCR (primär, beste Qualität)
- OCRmyPDF (für Vorverarbeitung)
- EasyOCR (optional, schneller)
- SURYA (optional, Vision-Transformer)

Author: Gregor
Version: 2.0
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# ENGINE AVAILABILITY CHECK
# ============================================================

try:
    from paddleocr import PaddleOCR

    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False
    logger.warning("PaddleOCR nicht verfügbar")

try:
    import ocrmypdf

    OCRMYPDF_AVAILABLE = True
except ImportError:
    OCRMYPDF_AVAILABLE = False
    logger.warning("OCRmyPDF nicht verfügbar")

try:
    import easyocr

    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR nicht verfügbar")

# SURYA ist optional
try:
    from surya.model.detection import load_model as load_det_model
    from surya.model.recognition import load_model as load_rec_model
    from surya.ocr import run_ocr

    SURYA_AVAILABLE = True
except ImportError:
    SURYA_AVAILABLE = False


class OCREngine(str, Enum):
    """Verfügbare OCR-Engines"""

    PADDLE = "paddle"
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    SURYA = "surya"


@dataclass
class OCRConfig:
    """Konfiguration für OCR"""

    primary_engine: OCREngine = OCREngine.PADDLE
    fallback_engine: Optional[OCREngine] = OCREngine.EASYOCR

    # Sprachen
    languages: List[str] = None  # Default: ['de', 'en']

    # Konfidenz-Schwellwert
    confidence_threshold: float = 0.7

    # PaddleOCR spezifisch
    paddle_use_gpu: bool = False
    paddle_show_log: bool = False

    # Performance
    enable_preprocessing: bool = True

    def __post_init__(self):
        if self.languages is None:
            self.languages = ["de", "en"]


@dataclass
class OCRResult:
    """Ergebnis einer OCR-Operation"""

    text: str
    confidence: float
    bounding_boxes: List[Dict[str, Any]]
    engine_used: str
    page_number: int = 1
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class OCRProcessor:
    """
    Haupt-OCR-Prozessor mit mehreren Engines

    Beispiel:
        ocr = OCRProcessor()
        result = ocr.process_image("scan.jpg")
        print(result.text)
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()
        self.engines = {}

        self._init_engines()
        logger.info(f"OCRProcessor initialisiert mit Engine: {self.config.primary_engine}")

    def _init_engines(self):
        """Initialisiert verfügbare OCR-Engines"""

        # PaddleOCR
        if PADDLE_AVAILABLE and self.config.primary_engine == OCREngine.PADDLE:
            try:
                self.engines["paddle"] = PaddleOCR(
                    use_angle_cls=True,
                    lang="german",  # oder 'de' je nach Version
                    use_gpu=self.config.paddle_use_gpu,
                    show_log=self.config.paddle_show_log,
                )
                logger.info("✅ PaddleOCR initialisiert")
            except Exception as e:
                logger.error(f"Fehler beim Initialisieren von PaddleOCR: {e}")

        # EasyOCR
        if EASYOCR_AVAILABLE:
            try:
                self.engines["easyocr"] = easyocr.Reader(self.config.languages, gpu=False)  # CPU-only für Stabilität
                logger.info("✅ EasyOCR initialisiert")
            except Exception as e:
                logger.error(f"Fehler beim Initialisieren von EasyOCR: {e}")

    def process_image(self, image_path: str, engine: Optional[OCREngine] = None) -> OCRResult:
        """
        Führt OCR auf Bild aus

        Args:
            image_path: Pfad zum Bild
            engine: Optionale Engine-Auswahl

        Returns:
            OCRResult mit Text und Metadaten
        """
        engine = engine or self.config.primary_engine

        if engine == OCREngine.PADDLE and "paddle" in self.engines:
            return self._process_with_paddle(image_path)

        elif engine == OCREngine.EASYOCR and "easyocr" in self.engines:
            return self._process_with_easyocr(image_path)

        else:
            # Fallback zu Tesseract
            return self._process_with_tesseract(image_path)

    def _process_with_paddle(self, image_path: str) -> OCRResult:
        """PaddleOCR Verarbeitung"""
        try:
            paddle = self.engines["paddle"]
            result = paddle.ocr(str(image_path), cls=True)

            # Extrahiere Text und Bounding Boxes
            text_lines = []
            bounding_boxes = []
            confidences = []

            if result and len(result) > 0:
                for line in result[0]:  # result[0] für erste Seite
                    if line:
                        box, (text, conf) = line
                        text_lines.append(text)
                        bounding_boxes.append({"box": box, "text": text, "confidence": conf})
                        confidences.append(conf)

            full_text = "\n".join(text_lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                bounding_boxes=bounding_boxes,
                engine_used="PaddleOCR",
                metadata={"lines_detected": len(text_lines)},
            )

        except Exception as e:
            logger.error(f"PaddleOCR Fehler: {e}")
            return OCRResult(
                text="", confidence=0.0, bounding_boxes=[], engine_used="PaddleOCR (failed)", metadata={"error": str(e)}
            )

    def _process_with_easyocr(self, image_path: str) -> OCRResult:
        """EasyOCR Verarbeitung"""
        try:
            reader = self.engines["easyocr"]
            result = reader.readtext(str(image_path))

            text_lines = []
            bounding_boxes = []
            confidences = []

            for detection in result:
                bbox, text, conf = detection
                text_lines.append(text)
                bounding_boxes.append({"box": bbox, "text": text, "confidence": conf})
                confidences.append(conf)

            full_text = "\n".join(text_lines)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                text=full_text, confidence=avg_confidence, bounding_boxes=bounding_boxes, engine_used="EasyOCR"
            )

        except Exception as e:
            logger.error(f"EasyOCR Fehler: {e}")
            return OCRResult(
                text="", confidence=0.0, bounding_boxes=[], engine_used="EasyOCR (failed)", metadata={"error": str(e)}
            )

    def _process_with_tesseract(self, image_path: str) -> OCRResult:
        """Fallback zu Tesseract (bereits im System vorhanden)"""
        import pytesseract
        from PIL import Image

        try:
            img = Image.open(image_path)

            # Text extrahieren
            text = pytesseract.image_to_string(img, lang="deu+eng")

            # Data für Bounding Boxes
            data = pytesseract.image_to_data(img, lang="deu+eng", output_type=pytesseract.Output.DICT)

            bounding_boxes = []
            confidences = []

            for i, conf in enumerate(data["conf"]):
                if int(conf) > 0:
                    bbox = {
                        "x": data["left"][i],
                        "y": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i],
                    }
                    bounding_boxes.append({"box": bbox, "text": data["text"][i], "confidence": int(conf) / 100.0})
                    confidences.append(int(conf) / 100.0)

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                text=text, confidence=avg_confidence, bounding_boxes=bounding_boxes, engine_used="Tesseract"
            )

        except Exception as e:
            logger.error(f"Tesseract Fehler: {e}")
            return OCRResult(
                text="", confidence=0.0, bounding_boxes=[], engine_used="Tesseract (failed)", metadata={"error": str(e)}
            )

    def process_pdf(self, pdf_path: str, output_path: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Verarbeitet PDF mit OCR (verwendet OCRmyPDF wenn verfügbar)

        Args:
            pdf_path: Pfad zum PDF
            output_path: Ausgabepfad für OCR-PDF (optional)

        Returns:
            (output_path, metadata)
        """
        if OCRMYPDF_AVAILABLE:
            return self._process_pdf_with_ocrmypdf(pdf_path, output_path)
        else:
            return self._process_pdf_manual(pdf_path, output_path)

    def _process_pdf_with_ocrmypdf(
        self, pdf_path: str, output_path: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Verarbeitet PDF mit OCRmyPDF"""
        import ocrmypdf

        if output_path is None:
            pdf_file = Path(pdf_path)
            output_path = str(pdf_file.parent / f"{pdf_file.stem}_ocr.pdf")

        try:
            logger.info(f"OCR für PDF: {pdf_path}")

            result = ocrmypdf.ocr(
                pdf_path,
                output_path,
                language="deu+eng",
                deskew=True,
                rotate_pages=True,
                remove_background=False,
                optimize=1,
                output_type="pdf",
                progress_bar=False,
            )

            return output_path, {"success": True, "engine": "OCRmyPDF", "output": output_path}

        except Exception as e:
            logger.error(f"OCRmyPDF Fehler: {e}")
            return pdf_path, {"success": False, "error": str(e)}

    def _process_pdf_manual(self, pdf_path: str, output_path: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """Manuelle PDF OCR (Seite für Seite)"""
        from pdf2image import convert_from_path
        from pypdf import PdfReader, PdfWriter

        logger.info("OCRmyPDF nicht verfügbar, verwende manuelle Methode")

        # Konvertiere PDF zu Bildern
        images = convert_from_path(pdf_path)

        # OCR für jedes Bild
        results = []
        for i, image in enumerate(images, 1):
            temp_img = f"temp_page_{i}.png"
            image.save(temp_img)

            ocr_result = self.process_image(temp_img)
            results.append(ocr_result)

            # Cleanup
            Path(temp_img).unlink()

        return pdf_path, {
            "success": True,
            "pages_processed": len(results),
            "avg_confidence": sum(r.confidence for r in results) / len(results),
        }


def add_ocr_to_pdf(pdf_path: str, output_path: Optional[str] = None) -> str:
    """
    Convenience-Funktion: Fügt PDF OCR-Text hinzu

    Args:
        pdf_path: Eingabe-PDF
        output_path: Ausgabe-PDF (optional)

    Returns:
        Pfad zum OCR-PDF
    """
    processor = OCRProcessor()
    result_path, metadata = processor.process_pdf(pdf_path, output_path)

    if metadata.get("success"):
        logger.info(f"✅ OCR erfolgreich: {result_path}")
    else:
        logger.error(f"❌ OCR fehlgeschlagen: {metadata.get('error')}")

    return result_path


# ============================================================
# MAIN (für Testing)
# ============================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("OCR Processor - Test")
    print("=" * 60)

    # Check verfügbare Engines
    print("\n🔍 Verfügbare OCR-Engines:")
    print(f"   PaddleOCR: {'✅' if PADDLE_AVAILABLE else '❌'}")
    print(f"   OCRmyPDF:  {'✅' if OCRMYPDF_AVAILABLE else '❌'}")
    print(f"   EasyOCR:   {'✅' if EASYOCR_AVAILABLE else '❌'}")
    print(f"   SURYA:     {'✅' if SURYA_AVAILABLE else '❌'}")

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  Bild: python ocr_processor.py image.jpg")
        print("  PDF:  python ocr_processor.py document.pdf")
        sys.exit(0)

    input_file = sys.argv[1]
    file_path = Path(input_file)

    if not file_path.exists():
        print(f"❌ Datei nicht gefunden: {input_file}")
        sys.exit(1)

    processor = OCRProcessor()

    if file_path.suffix.lower() == ".pdf":
        print(f"\n📄 Verarbeite PDF: {input_file}")
        output, metadata = processor.process_pdf(input_file)
        print(f"✅ Ergebnis: {output}")
        print(f"📊 Metadaten: {metadata}")

    else:
        print(f"\n🖼️ Verarbeite Bild: {input_file}")
        result = processor.process_image(input_file)

        print(f"\n✅ Engine: {result.engine_used}")
        print(f"📊 Konfidenz: {result.confidence:.2%}")
        print(f"📝 Text (erste 200 Zeichen):")
        print(result.text[:200])
        print("...")
