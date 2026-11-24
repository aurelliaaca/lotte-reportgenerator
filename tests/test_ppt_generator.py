"""Unit tests for PowerPoint report generation and slide duplication."""

import pytest
from pathlib import Path
from pptx import Presentation
from modules.ppt_generator import PPTGenerator
from config.settings import DEFAULT_TEMPLATE_PATH


def test_dynamic_slide_duplication(tmp_path):
    assert DEFAULT_TEMPLATE_PATH.exists()
    generator = PPTGenerator(DEFAULT_TEMPLATE_PATH)

    # Test 1: 4 products -> 1 product slide -> total 3 slides (Slide 1 + Slide 2 + 1 product slide)
    prods_4 = [{"product_name": f"Product {i+1}", "image_path": None} for i in range(4)]
    out_4 = generator.generate_report(
        report_id=101,
        week_name="Test-4",
        reporting_period="1 – 7 September 2026",
        products=prods_4,
    )
    prs_4 = Presentation(str(out_4))
    assert len(prs_4.slides) == 3

    # Test 2: 10 products -> 2 product slides -> total 4 slides
    prods_10 = [{"product_name": f"Product {i+1}", "image_path": None} for i in range(10)]
    out_10 = generator.generate_report(
        report_id=102,
        week_name="Test-10",
        reporting_period="1 – 7 September 2026",
        products=prods_10,
    )
    prs_10 = Presentation(str(out_10))
    assert len(prs_10.slides) == 4

    # Test 3: 20 products -> 3 product slides (8 + 8 + 4) -> total 5 slides
    prods_20 = [{"product_name": f"Product {i+1}", "image_path": None} for i in range(20)]
    out_20 = generator.generate_report(
        report_id=103,
        week_name="Test-20",
        reporting_period="1 – 7 September 2026",
        products=prods_20,
    )
    prs_20 = Presentation(str(out_20))
    assert len(prs_20.slides) == 5

    # Test 4: 27 products -> 4 product slides (8 + 8 + 8 + 3) -> total 6 slides
    prods_27 = [{"product_name": f"Product {i+1}", "image_path": None} for i in range(27)]
    out_27 = generator.generate_report(
        report_id=104,
        week_name="Test-27",
        reporting_period="24 – 30 November 2026",
        products=prods_27,
    )
    prs_27 = Presentation(str(out_27))
    assert len(prs_27.slides) == 6
