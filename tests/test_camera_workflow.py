"""Unit tests for the direct camera capture and 1-to-1 product association workflow."""

import pytest
import io
from pathlib import Path
from PIL import Image
from pptx import Presentation

from modules.report_manager import ReportManager
from modules.image_handler import ImageHandler
from database.db import init_db, get_products_by_report, get_report

SAMPLE_PDF = Path(__file__).resolve().parent.parent / "sample_data" / "Big Banner LSI 24-30 nov 2026 copy.pdf"


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_pdf_extraction_initializes_camera_list(tmp_path):
    if not SAMPLE_PDF.exists():
        pytest.skip("Sample PDF not found")

    with open(SAMPLE_PDF, "rb") as f:
        pdf_bytes = f.read()

    report_id = ReportManager.create_weekly_report(
        week_name="Camera Test Report W1",
        reporting_period="24 – 30 November 2026",
        store_name="LSI MERUYA",
        pdf_file_bytes=pdf_bytes,
        pdf_filename="promo_catalog.pdf",
    )

    products = ReportManager.extract_and_save_products_from_pdf(report_id)
    assert len(products) >= 20
    assert all(p["image_path"] is None for p in products)
    assert all(p["matching_status"] == "unmatched" for p in products)

    progress = ReportManager.get_capture_progress(report_id)
    assert progress["total"] == len(products)
    assert progress["captured"] == 0
    assert progress["missing"] == len(products)
    assert progress["all_captured"] is False


def test_camera_photo_capture_and_association():
    if not SAMPLE_PDF.exists():
        pytest.skip("Sample PDF not found")

    with open(SAMPLE_PDF, "rb") as f:
        pdf_bytes = f.read()

    report_id = ReportManager.create_weekly_report(
        week_name="Camera Test Report W2",
        reporting_period="24 – 30 November 2026",
        store_name="LSI MERUYA",
        pdf_file_bytes=pdf_bytes,
        pdf_filename="promo_catalog.pdf",
    )

    products = ReportManager.extract_and_save_products_from_pdf(report_id)
    target_product = products[0]
    target_id = target_product["id"]

    # Create dummy camera photo bytes
    img = Image.new("RGB", (300, 300), color=(50, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    photo_bytes = buf.getvalue()

    # 1. Attach captured photo
    saved_info = ReportManager.attach_captured_photo(
        report_id=report_id,
        product_id=target_id,
        file_bytes=photo_bytes,
        filename="device_camera.jpg",
    )

    assert Path(saved_info["path"]).exists()
    assert f"product_{target_id}" in saved_info["filename"]

    # Verify database update
    updated_products = get_products_by_report(report_id)
    updated_target = next(p for p in updated_products if p["id"] == target_id)
    assert updated_target["matching_status"] == "captured"
    assert updated_target["image_path"] == saved_info["path"]

    # Verify progress increments
    progress = ReportManager.get_capture_progress(report_id)
    assert progress["captured"] == 1
    assert progress["missing"] == len(products) - 1

    # 2. Retake / replace photo
    new_img = Image.new("RGB", (300, 300), color=(200, 80, 50))
    new_buf = io.BytesIO()
    new_img.save(new_buf, format="JPEG")
    retake_info = ReportManager.attach_captured_photo(
        report_id=report_id,
        product_id=target_id,
        file_bytes=new_buf.getvalue(),
    )
    assert Path(retake_info["path"]).exists()

    # 3. Delete photo
    ReportManager.remove_product_photo(report_id, target_id)
    assert not Path(saved_info["path"]).exists()

    refreshed_products = get_products_by_report(report_id)
    refreshed_target = next(p for p in refreshed_products if p["id"] == target_id)
    assert refreshed_target["image_path"] is None
    assert refreshed_target["matching_status"] == "unmatched"


def test_powerpoint_generation_with_captured_photos():
    if not SAMPLE_PDF.exists():
        pytest.skip("Sample PDF not found")

    with open(SAMPLE_PDF, "rb") as f:
        pdf_bytes = f.read()

    report_id = ReportManager.create_weekly_report(
        week_name="Camera PPT Test",
        reporting_period="24 – 30 November 2026",
        store_name="LSI MERUYA",
        pdf_file_bytes=pdf_bytes,
        pdf_filename="promo_catalog.pdf",
    )

    products = ReportManager.extract_and_save_products_from_pdf(report_id)

    # Attach photo to first 2 products
    for i in range(2):
        p_id = products[i]["id"]
        img = Image.new("RGB", (250, 250), color=(40, 160, 90))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        ReportManager.attach_captured_photo(report_id, p_id, buf.getvalue())

    # Generate PowerPoint
    pptx_path = ReportManager.generate_powerpoint_report(report_id)
    assert pptx_path.exists()

    prs = Presentation(str(pptx_path))
    # Should have title (slide 1), banner (slide 2), and product slides (slides 3+)
    assert len(prs.slides) >= 3

    # Slide 3 (first product slide) should have picture shapes inserted
    slide3_pics = [s for s in prs.slides[2].shapes if s.shape_type == 13]
    assert len(slide3_pics) >= 2


def test_report_image_isolation():
    # Report A
    rep_a = ReportManager.create_weekly_report("Week A", "1-7 Nov 2026")
    # Report B
    rep_b = ReportManager.create_weekly_report("Week B", "8-14 Nov 2026")

    dir_a = ImageHandler.get_images_dir(rep_a)
    dir_b = ImageHandler.get_images_dir(rep_b)

    assert dir_a != dir_b
    assert str(rep_a) in str(dir_a)
    assert str(rep_b) in str(dir_b)
