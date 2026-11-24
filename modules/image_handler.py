"""Image storage, ZIP extraction, validation, and thumbnail generation."""

import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
from config.settings import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_ZIP_EXTENSIONS,
    MAX_FILE_SIZE_MB,
)
from utils.file_validator import safe_extract_zip, validate_file_extension, FileValidationError
from utils.helpers import get_report_upload_dir
from utils.text_normalizer import normalize_for_matching


class ImageHandler:
    """Manages product image uploads and storage isolated by weekly report."""

    @classmethod
    def get_images_dir(cls, report_id: int) -> Path:
        """Get the images directory for a report."""
        p = get_report_upload_dir(report_id) / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_thumbnails_dir(cls, report_id: int) -> Path:
        """Get the thumbnail preview directory for a report."""
        p = get_report_upload_dir(report_id) / "thumbnails"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def process_zip_upload(cls, report_id: int, zip_file_path: Path) -> List[Dict[str, Any]]:
        """
        Safely extract ZIP upload into the report's image directory.
        Generates thumbnails and returns list of image descriptors.
        """
        dest_dir = cls.get_images_dir(report_id)
        extracted_paths = safe_extract_zip(zip_file_path, dest_dir)
        return cls.index_images(report_id)

    @classmethod
    def save_single_image(cls, report_id: int, filename: str, file_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Save a single uploaded image directly."""
        if not validate_file_extension(filename, ALLOWED_IMAGE_EXTENSIONS):
            raise FileValidationError(f"Unsupported image file format: {filename}")

        dest_dir = cls.get_images_dir(report_id)
        # Avoid collision
        dest_path = dest_dir / Path(filename).name
        counter = 1
        stem = Path(filename).stem
        ext = Path(filename).suffix
        while dest_path.exists():
            dest_path = dest_dir / f"{stem}_{counter}{ext}"
            counter += 1

        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        thumb_path = cls.generate_thumbnail(report_id, dest_path)
        return {
            "filename": dest_path.name,
            "path": str(dest_path),
            "thumbnail_path": str(thumb_path) if thumb_path else None,
            "normalized_name": normalize_for_matching(dest_path.stem),
        }

    @classmethod
    def index_images(cls, report_id: int) -> List[Dict[str, Any]]:
        """List and index all images in the report's image folder."""
        images_dir = cls.get_images_dir(report_id)
        indexed: List[Dict[str, Any]] = []

        # Recursively find all images (handles subfolders inside ZIP)
        for p in images_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                if not p.name.startswith("."):
                    thumb_p = cls.generate_thumbnail(report_id, p)
                    indexed.append({
                        "filename": p.name,
                        "relative_path": str(p.relative_to(images_dir)),
                        "path": str(p),
                        "thumbnail_path": str(thumb_p) if thumb_p else None,
                        "normalized_name": normalize_for_matching(p.stem),
                    })

        indexed.sort(key=lambda x: x["filename"].lower())
        return indexed

    @classmethod
    def generate_thumbnail(cls, report_id: int, image_path: Path, size: tuple = (150, 150)) -> Optional[Path]:
        """Generate a small thumbnail image for fast UI rendering."""
        try:
            thumbs_dir = cls.get_thumbnails_dir(report_id)
            thumb_path = thumbs_dir / f"thumb_{image_path.name}"
            if thumb_path.exists():
                return thumb_path

            with Image.open(image_path) as img:
                # Convert RGBA or CMYK to RGB
                if img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = bg
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.save(thumb_path, "JPEG", quality=85)
                return thumb_path
        except Exception as e:
            print(f"Error creating thumbnail for {image_path}: {e}")
            return None

    @classmethod
    def save_product_photo(
        cls,
        report_id: int,
        product_id: int,
        file_bytes: bytes,
        original_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save a photo captured directly from camera or uploaded for a specific product.
        Isolates photo in the report's image folder with a deterministic product filename.
        """
        dest_dir = cls.get_images_dir(report_id)
        ext = ".jpg"
        if original_filename:
            candidate_ext = Path(original_filename).suffix.lower()
            if candidate_ext in ALLOWED_IMAGE_EXTENSIONS:
                ext = candidate_ext

        filename = f"product_{product_id}{ext}"
        dest_path = dest_dir / filename

        with open(dest_path, "wb") as f:
            f.write(file_bytes)

        # Remove old cached thumbnail if exists
        thumbs_dir = cls.get_thumbnails_dir(report_id)
        thumb_candidate = thumbs_dir / f"thumb_{filename}"
        if thumb_candidate.exists():
            thumb_candidate.unlink()

        thumb_path = cls.generate_thumbnail(report_id, dest_path)

        return {
            "filename": filename,
            "path": str(dest_path),
            "thumbnail_path": str(thumb_path) if thumb_path else None,
        }

    @classmethod
    def delete_product_photo(cls, report_id: int, product_id: int) -> bool:
        """Delete image file and thumbnail for a product."""
        images_dir = cls.get_images_dir(report_id)
        thumbs_dir = cls.get_thumbnails_dir(report_id)
        deleted = False

        for ext in ALLOWED_IMAGE_EXTENSIONS:
            p = images_dir / f"product_{product_id}{ext}"
            if p.exists():
                p.unlink()
                deleted = True
            t = thumbs_dir / f"thumb_product_{product_id}{ext}"
            if t.exists():
                t.unlink()

        return deleted

