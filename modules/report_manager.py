"""Weekly report lifecycle, file processing, and execution workflow coordinator."""

import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from database.db import (
    create_report,
    get_report,
    list_reports,
    update_report_status,
    save_products,
    get_products_by_report,
    update_product,
    delete_product,
    delete_report as db_delete_report,
    get_active_template,
)
from modules.pdf_extractor import PDFExtractor
from modules.image_handler import ImageHandler
from modules.image_matcher import ImageMatcher
from modules.ppt_generator import PPTGenerator
from utils.helpers import (
    get_report_upload_dir,
    get_report_output_dir,
    delete_report_files,
    render_pdf_page_as_image,
)
from utils.file_validator import validate_file_extension, FileValidationError
from config.settings import ALLOWED_PDF_EXTENSIONS, ALLOWED_ZIP_EXTENSIONS


class ReportManager:
    """Coordinates end-to-end report workflow across PDF extraction, image matching, and PPT generation."""

    @classmethod
    def create_weekly_report(
        cls,
        week_name: str,
        reporting_period: str,
        store_name: str = "LSI MERUYA",
        pdf_file_bytes: Optional[bytes] = None,
        pdf_filename: Optional[str] = None,
        zip_file_bytes: Optional[bytes] = None,
        zip_filename: Optional[str] = None,
    ) -> int:
        """Create a new report record and store uploaded files in the isolated report folder."""
        report_id = create_report(
            week_name=week_name,
            reporting_period=reporting_period,
            store_name=store_name,
            pdf_filename=pdf_filename,
            zip_filename=zip_filename,
        )

        upload_dir = get_report_upload_dir(report_id)

        # Save PDF if provided
        if pdf_file_bytes and pdf_filename:
            if not validate_file_extension(pdf_filename, ALLOWED_PDF_EXTENSIONS):
                raise FileValidationError(f"Invalid PDF extension: {pdf_filename}")
            pdf_path = upload_dir / pdf_filename
            with open(pdf_path, "wb") as f:
                f.write(pdf_file_bytes)

        # Save ZIP if provided
        if zip_file_bytes and zip_filename:
            if not validate_file_extension(zip_filename, ALLOWED_ZIP_EXTENSIONS):
                raise FileValidationError(f"Invalid ZIP extension: {zip_filename}")
            zip_path = upload_dir / zip_filename
            with open(zip_path, "wb") as f:
                f.write(zip_file_bytes)

        return report_id

    @classmethod
    def process_weekly_files(cls, report_id: int) -> Dict[str, Any]:
        """
        Process PDF and ZIP for a given report:
        1. Extract products from PDF
        2. Extract & index images from ZIP
        3. Match images to products
        4. Save products in DB
        """
        report = get_report(report_id)
        if not report:
            raise ValueError(f"Report ID {report_id} not found.")

        upload_dir = get_report_upload_dir(report_id)
        pdf_filename = report["pdf_filename"]
        zip_filename = report["zip_filename"]

        update_report_status(report_id, "processing")

        # 1. PDF Extraction
        products = []
        extracted_period = report["reporting_period"]
        if pdf_filename:
            pdf_path = upload_dir / pdf_filename
            if pdf_path.exists():
                extractor = PDFExtractor(pdf_path)
                data = extractor.extract_all()
                products = data["products"]
                if data.get("reporting_period") and not extracted_period:
                    extracted_period = data["reporting_period"]

        # 2. Image Extraction
        images = []
        if zip_filename:
            zip_path = upload_dir / zip_filename
            if zip_path.exists():
                images = ImageHandler.process_zip_upload(report_id, zip_path)
        else:
            # Check if images already exist in directory
            images = ImageHandler.index_images(report_id)

        # 3. Image Matching
        matcher = ImageMatcher()
        matched_products = matcher.match_products(products, images)

        # 4. Save to Database
        save_products(report_id, matched_products)
        update_report_status(report_id, "reviewed", product_count=len(matched_products))

        return {
            "report_id": report_id,
            "product_count": len(matched_products),
            "image_count": len(images),
            "matched_products": matched_products,
        }

    @classmethod
    def generate_powerpoint_report(cls, report_id: int) -> Path:
        """
        Generate final PowerPoint presentation for a report:
        - Retrieves products and active template
        - Renders PDF flyer banner for Slide 2
        - Duplicates product slides as needed
        - Inserts photos & formatted names
        """
        report = get_report(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found.")

        active_tmpl = get_active_template()
        if not active_tmpl:
            raise RuntimeError("No active PowerPoint template found.")

        template_path = Path(active_tmpl["file_path"])
        products = get_products_by_report(report_id)
        upload_dir = get_report_upload_dir(report_id)

        # Render flyer banner image from PDF page 1 if available
        flyer_img_path = None
        pdf_name = report.get("pdf_filename")
        if pdf_name:
            pdf_path = upload_dir / pdf_name
            if pdf_path.exists():
                banner_out = upload_dir / "flyer_banner.png"
                flyer_img_path = render_pdf_page_as_image(pdf_path, banner_out, page_num=0, dpi=180)

        generator = PPTGenerator(template_path)
        output_path = generator.generate_report(
            report_id=report_id,
            week_name=report["week_name"],
            reporting_period=report["reporting_period"] or "Weekly Promo",
            products=products,
            store_name=report.get("store_name") or "LSI MERUYA",
            flyer_image_path=flyer_img_path,
        )

        update_report_status(
            report_id=report_id,
            status="completed",
            generated_ppt_path=str(output_path),
        )

        return output_path

    @classmethod
    def get_report_metrics(cls, report_id: int) -> Dict[str, Any]:
        """Compute matching and extraction summary statistics for review."""
        products = get_products_by_report(report_id)
        total = len(products)
        matched = sum(1 for p in products if p["matching_status"] == "matched")
        suggested = sum(1 for p in products if p["matching_status"] == "suggested")
        unmatched = sum(1 for p in products if p["matching_status"] == "unmatched")
        needs_review = sum(1 for p in products if p.get("needs_review"))

        return {
            "total_products": total,
            "matched_count": matched,
            "suggested_count": suggested,
            "unmatched_count": unmatched,
            "needs_review_count": needs_review,
            "ready_to_generate": total > 0,
        }

    @classmethod
    def extract_and_save_products_from_pdf(cls, report_id: int) -> List[Dict[str, Any]]:
        """
        Extract products directly from the uploaded promotional PDF and initialize
        them in the database for direct camera photo capture.
        """
        report = get_report(report_id)
        if not report:
            raise ValueError(f"Report ID {report_id} not found.")

        upload_dir = get_report_upload_dir(report_id)
        pdf_filename = report.get("pdf_filename")
        if not pdf_filename:
            raise ValueError("No PDF uploaded for this report.")

        pdf_path = upload_dir / pdf_filename
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        extractor = PDFExtractor(pdf_path)
        data = extractor.extract_all()
        products = data["products"]

        # Ensure matching_status is initialized as 'unmatched' (Not Captured)
        for p in products:
            p["image_path"] = None
            p["matched_filename"] = None
            p["matching_score"] = 0.0
            p["matching_status"] = "unmatched"

        save_products(report_id, products)
        update_report_status(
            report_id=report_id,
            status="awaiting_photos",
            product_count=len(products),
        )

        return get_products_by_report(report_id)

    @classmethod
    def attach_captured_photo(
        cls,
        report_id: int,
        product_id: int,
        file_bytes: bytes,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Associate a photo taken from the camera (or uploaded directly) with a specific product.
        """
        saved = ImageHandler.save_product_photo(
            report_id=report_id,
            product_id=product_id,
            file_bytes=file_bytes,
            original_filename=filename,
        )

        update_product(
            product_id=product_id,
            updates={
                "image_path": saved["path"],
                "matched_filename": saved["filename"],
                "matching_status": "captured",
                "matching_score": 100.0,
            },
        )

        return saved

    @classmethod
    def remove_product_photo(cls, report_id: int, product_id: int) -> bool:
        """Remove photo from disk and disassociate from product."""
        ImageHandler.delete_product_photo(report_id, product_id)
        update_product(
            product_id=product_id,
            updates={
                "image_path": None,
                "matched_filename": None,
                "matching_status": "unmatched",
                "matching_score": 0.0,
            },
        )
        return True

    @classmethod
    def get_capture_progress(cls, report_id: int) -> Dict[str, Any]:
        """Calculate camera photo capture progress for the product list."""
        products = get_products_by_report(report_id)
        total = len(products)
        captured = 0
        missing_names = []

        for p in products:
            img_p = p.get("image_path")
            if img_p and Path(img_p).exists():
                captured += 1
            else:
                missing_names.append(p.get("product_name", f"Product #{p['id']}"))

        missing = total - captured
        percent = (captured / total * 100.0) if total > 0 else 0.0

        return {
            "total": total,
            "captured": captured,
            "missing": missing,
            "percent": round(percent, 1),
            "all_captured": (missing == 0 and total > 0),
            "missing_products": missing_names,
        }

    @classmethod
    def delete_weekly_report(cls, report_id: int) -> bool:
        """Delete report from database and delete all associated files."""
        delete_report_files(report_id)
        return db_delete_report(report_id)
