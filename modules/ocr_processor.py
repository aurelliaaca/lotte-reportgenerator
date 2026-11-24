"""OCR processing fallback engine for scanned or image-based PDFs using Tesseract."""

import pytesseract
from PIL import Image
from pathlib import Path
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from config.settings import TESSERACT_PATH

# Configure tesseract executable if available
if TESSERACT_PATH and Path(TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)


class OCRProcessor:
    """Handles optical character recognition for scanned or rasterized documents."""

    @staticmethod
    def is_ocr_available() -> bool:
        """Check if Tesseract binary is accessible."""
        try:
            ver = pytesseract.get_tesseract_version()
            return bool(ver)
        except Exception:
            return False

    @classmethod
    def extract_text_from_image(cls, image: Image.Image, lang: str = "eng+ind") -> str:
        """Run OCR on a PIL Image object."""
        try:
            # Try with both English and Indonesian if available, fallback to eng
            try:
                return pytesseract.image_to_string(image, lang=lang)
            except Exception:
                return pytesseract.image_to_string(image, lang="eng")
        except Exception as e:
            print(f"OCR execution failed: {e}")
            return ""

    @classmethod
    def extract_data_from_image(cls, image: Image.Image, lang: str = "eng+ind") -> List[Dict[str, Any]]:
        """Run OCR and return structured word-level bounding box data."""
        try:
            try:
                data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
            except Exception:
                data = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)

            results = []
            n_boxes = len(data["text"])
            for i in range(n_boxes):
                text = data["text"][i].strip()
                conf = float(data["conf"][i])
                if text and conf > 20:
                    results.append({
                        "text": text,
                        "left": data["left"][i],
                        "top": data["top"][i],
                        "width": data["width"][i],
                        "height": data["height"][i],
                        "confidence": conf,
                    })
            return results
        except Exception as e:
            print(f"Structured OCR execution failed: {e}")
            return []

    @classmethod
    def ocr_pdf_page(cls, doc: fitz.Document, page_num: int, dpi: int = 200) -> str:
        """Render a specific PDF page to pixmap and run OCR."""
        if page_num >= len(doc):
            return ""
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return cls.extract_text_from_image(img)
