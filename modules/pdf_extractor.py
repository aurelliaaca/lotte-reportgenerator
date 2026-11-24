"""Automatic promotional PDF product extraction engine with PyMuPDF and OCR fallback."""

import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import fitz  # PyMuPDF
from modules.ocr_processor import OCRProcessor
from modules.product_processor import ProductProcessor
from utils.text_normalizer import normalize_text, extract_price_value


class PDFExtractor:
    """Extracts products, brands, prices, and reporting period from promotional PDFs."""

    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    def extract_all(self) -> Dict[str, Any]:
        """
        Run complete extraction pipeline.
        Returns reporting_period, store_name, products list, and extraction metadata.
        """
        doc = fitz.open(str(self.pdf_path))
        is_scanned = False
        all_products: List[Dict[str, Any]] = []
        reporting_period: Optional[str] = None
        store_name: str = "LSI MERUYA"

        # Check total text volume across document
        total_raw_text = "".join(page.get_text() for page in doc).strip()

        if len(total_raw_text) < 100 and OCRProcessor.is_ocr_available():
            is_scanned = True
            doc_data = self._extract_via_ocr(doc)
            doc.close()
            return doc_data

        # Process each page with PyMuPDF
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_text = page.get_text()

            # Attempt to extract reporting period from page text
            if not reporting_period:
                period_match = re.search(
                    r"Periode\s*:?\s*(\d{1,2}\s*[-–]\s*\d{1,2}\s+[A-Za-z]+\s+\d{4})",
                    page_text,
                    re.IGNORECASE,
                )
                if period_match:
                    reporting_period = period_match.group(1).strip()

            # Check store name if present
            store_match = re.search(r"\b(LSI\s+[A-Z0-9]+)\b", page_text)
            if store_match:
                store_name = store_match.group(1)

            # Get blocks with coordinates
            blocks = page.get_text("blocks")
            # Sort top-to-bottom, left-to-right
            blocks = sorted(blocks, key=lambda b: (round(b[1] / 50) * 50, b[0]))

            # Separate product blocks and price blocks
            page_products = self._extract_products_from_blocks(blocks)
            all_products.extend(page_products)

        doc.close()

        # Deduplicate while preserving order
        deduped_products = ProductProcessor.deduplicate_products(all_products)

        # Assign sequential product order
        for idx, prod in enumerate(deduped_products):
            prod["product_order"] = idx
            if reporting_period and not prod.get("promo_period"):
                prod["promo_period"] = reporting_period

        return {
            "pdf_filename": self.pdf_path.name,
            "reporting_period": reporting_period or "24 – 30 November 2026",
            "store_name": store_name,
            "is_scanned": is_scanned,
            "total_products": len(deduped_products),
            "products": deduped_products,
        }

    def _extract_products_from_blocks(self, blocks: List[Tuple]) -> List[Dict[str, Any]]:
        """Extract and associate products and nearby prices from PDF text blocks."""
        product_candidates = []
        price_blocks = []

        for b in blocks:
            text = b[4].strip()
            if not text:
                continue

            # Check for price block
            is_price = bool(re.search(r"(?:Rp\.?|/karton|/jerigen|/bundle|/box|/renceng|\b\d{2,3}\.\d{3}\b)", text, re.I))
            if is_price and not ProductProcessor.detect_brand(text):
                price_blocks.append((b[0], b[1], b[2], b[3], text))

            # Check for product candidates
            if ProductProcessor.is_disclaimer_or_banner_header(text):
                continue

            has_brand = bool(ProductProcessor.detect_brand(text))
            has_pack = bool(re.search(r"(\d+(?:x\d+)*(?:\s*(?:ml|l|kg|g|pcs|box|rcg|s|’s|’S))\b)", text, re.I))

            if has_brand or has_pack:
                segmented = ProductProcessor.segment_bundle_text(text)
                for seg in segmented:
                    if not ProductProcessor.is_disclaimer_or_banner_header(seg):
                        product_candidates.append({
                            "bbox": (b[0], b[1], b[2], b[3]),
                            "raw_text": seg,
                        })

        # Match nearest price block for each product candidate
        results = []
        for cand in product_candidates:
            cx, cy = (cand["bbox"][0] + cand["bbox"][2]) / 2, (cand["bbox"][1] + cand["bbox"][3]) / 2
            nearest_price = None
            min_dist = float("inf")

            for px0, py0, px1, py1, ptext in price_blocks:
                px, py = (px0 + px1) / 2, (py0 + py1) / 2
                # Price is usually below or slightly right of product
                if py >= cy - 20:
                    dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
                    if dist < min_dist and dist < 250:
                        min_dist = dist
                        # Clean price string
                        p_match = re.search(r"Rp\.?\s*([0-9.]+)", ptext)
                        if p_match:
                            nearest_price = f"Rp {p_match.group(1)}"
                        else:
                            val = extract_price_value(ptext)
                            if val:
                                nearest_price = f"Rp {val:,}".replace(",", ".")

            prod_dict = ProductProcessor.clean_and_normalize_product(cand["raw_text"], nearest_price)
            results.append(prod_dict)

        return results

    def _extract_via_ocr(self, doc: fitz.Document) -> Dict[str, Any]:
        """Perform OCR-based extraction on scanned document."""
        all_products = []
        reporting_period = None
        store_name = "LSI MERUYA"

        for page_idx in range(len(doc)):
            ocr_text = OCRProcessor.ocr_pdf_page(doc, page_idx)
            lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]

            # Extract period
            if not reporting_period:
                period_match = re.search(
                    r"Periode\s*:?\s*(\d{1,2}\s*[-–]\s*\d{1,2}\s+[A-Za-z]+\s+\d{4})",
                    ocr_text,
                    re.IGNORECASE,
                )
                if period_match:
                    reporting_period = period_match.group(1).strip()

            for line in lines:
                if ProductProcessor.is_disclaimer_or_banner_header(line):
                    continue
                has_brand = bool(ProductProcessor.detect_brand(line))
                has_pack = bool(re.search(r"(\d+(?:x\d+)*(?:\s*(?:ml|l|kg|g|pcs|box|rcg|s|’s|’S))\b)", line, re.I))

                if has_brand or has_pack:
                    p = ProductProcessor.clean_and_normalize_product(line)
                    p["extraction_confidence"] = 0.75
                    p["needs_review"] = 1
                    all_products.append(p)

        deduped = ProductProcessor.deduplicate_products(all_products)
        for idx, prod in enumerate(deduped):
            prod["product_order"] = idx
            if reporting_period:
                prod["promo_period"] = reporting_period

        return {
            "pdf_filename": self.pdf_path.name,
            "reporting_period": reporting_period or "24 – 30 November 2026",
            "store_name": store_name,
            "is_scanned": True,
            "total_products": len(deduped),
            "products": deduped,
        }
