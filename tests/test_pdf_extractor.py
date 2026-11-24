"""Unit tests for PDF extraction and product processing."""

import pytest
from pathlib import Path
from modules.pdf_extractor import PDFExtractor
from modules.product_processor import ProductProcessor


SAMPLE_PDF = Path(__file__).resolve().parent.parent / "sample_data" / "Big Banner LSI 24-30 nov 2026 copy.pdf"


def test_bundle_segmentation():
    bundle_text = "AMIDIS Botol 24x330ml // ULTRA MILK Cokelat/Strawberry/Full Cream 40x125ml"
    segmented = ProductProcessor.segment_bundle_text(bundle_text.replace(" // ", "\n"))
    assert len(segmented) == 2
    assert "AMIDIS" in segmented[0]
    assert "ULTRA MILK" in segmented[1]


def test_slash_joined_brands_not_split():
    text = "FANTA/COCA COLA/SPRITE 12x390ml"
    segmented = ProductProcessor.segment_bundle_text(text)
    assert len(segmented) == 1
    assert "FANTA/COCA COLA/SPRITE" in segmented[0]


def test_brand_detection():
    assert ProductProcessor.detect_brand("ROSE BRAND Minyak Goreng") == "ROSE BRAND"
    assert ProductProcessor.detect_brand("DELMONTE Extra Hot") == "DELMONTE"
    assert ProductProcessor.detect_brand("Random Generic Item") is None


def test_disclaimer_filtering():
    assert ProductProcessor.is_disclaimer_or_banner_header("SPESIAL MEMBER COKELAT & HIJAU") is True
    assert ProductProcessor.is_disclaimer_or_banner_header("*Berlaku kelipatan 3x") is True
    assert ProductProcessor.is_disclaimer_or_banner_header("12pcs") is True
    assert ProductProcessor.is_disclaimer_or_banner_header("ROSE BRAND Minyak Goreng 18L") is False


def test_display_name_formatting():
    formatted = ProductProcessor.format_display_name("ROSE BRAND Minyak Goreng Jerigen 18L")
    assert "–" in formatted
    assert "ROSE BRAND Minyak Goreng" in formatted
    assert "Jerigen 18L" in formatted


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="Sample PDF not found")
def test_real_pdf_extraction():
    extractor = PDFExtractor(SAMPLE_PDF)
    data = extractor.extract_all()
    assert data["total_products"] >= 20
    assert "24" in data["reporting_period"] and "November 2026" in data["reporting_period"]
    
    product_names = [p["product_name"] for p in data["products"]]
    # Verify key flagship items exist
    assert any("ROSE BRAND" in name for name in product_names)
    assert any("DELMONTE" in name for name in product_names)
    assert any("AMIDIS" in name for name in product_names)
    assert any("MAMA LEMON" in name for name in product_names)
