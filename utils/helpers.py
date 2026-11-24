"""General helper functions for Weekly REOT Generator."""

import shutil
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF
from config.settings import UPLOADS_DIR, OUTPUTS_DIR


def get_report_upload_dir(report_id: int) -> Path:
    """Return and create the isolated upload directory for a specific report."""
    p = UPLOADS_DIR / f"report_{report_id}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_report_output_dir(report_id: int) -> Path:
    """Return and create the isolated output directory for a specific report."""
    p = OUTPUTS_DIR / f"report_{report_id}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def delete_report_files(report_id: int) -> None:
    """Clean up uploaded and generated files associated with a report."""
    up_dir = UPLOADS_DIR / f"report_{report_id}"
    out_dir = OUTPUTS_DIR / f"report_{report_id}"
    if up_dir.exists():
        shutil.rmtree(up_dir, ignore_errors=True)
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)


def format_rupiah(amount: Optional[int]) -> str:
    """Format an integer amount to Indonesian Rupiah representation (e.g. 106000 -> Rp 106.000)."""
    if amount is None:
        return ""
    return f"Rp {amount:,.0f}".replace(",", ".")


def render_pdf_page_as_image(pdf_path: Path, output_image_path: Path, page_num: int = 0, dpi: int = 150) -> Optional[Path]:
    """Render a page of a PDF document to a high-resolution PNG image (e.g. for banner flyer slide)."""
    if not pdf_path.exists():
        return None
    try:
        doc = fitz.open(str(pdf_path))
        if page_num >= len(doc):
            return None
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        output_image_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(output_image_path))
        doc.close()
        return output_image_path
    except Exception as e:
        print(f"Error rendering PDF page to image: {e}")
        return None
