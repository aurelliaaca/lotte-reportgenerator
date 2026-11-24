"""File validation and safe extraction utilities."""

import os
import zipfile
from pathlib import Path
from typing import List, Tuple
from config.settings import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_PDF_EXTENSIONS,
    ALLOWED_ZIP_EXTENSIONS,
    MAX_FILE_SIZE_MB,
)


class FileValidationError(Exception):
    """Raised when file validation fails."""
    pass


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Check if filename has one of the allowed extensions."""
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


def validate_file_size(file_path: Path, max_size_mb: int = MAX_FILE_SIZE_MB) -> bool:
    """Ensure file size is within acceptable threshold."""
    if not file_path.exists():
        return False
    size_mb = file_path.stat().st_size / (1024 * 1024)
    return size_mb <= max_size_mb


def safe_extract_zip(zip_path: Path, extract_to: Path) -> List[Path]:
    """
    Safely extract a ZIP file to the destination directory.
    Protects against Zip Slip (path traversal) vulnerability.
    Filters and returns only allowed image files.
    """
    extract_to.mkdir(parents=True, exist_ok=True)
    destination_root = extract_to.resolve()
    extracted_images: List[Path] = []

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            # Skip directories and macOS hidden __MACOSX or .DS_Store files
            if member.is_dir():
                continue
            name = member.filename
            if "__MACOSX" in name or Path(name).name.startswith("."):
                continue

            target_path = (extract_to / member.filename).resolve()
            # Zip Slip check: ensure target_path is within destination_root
            if not str(target_path).startswith(str(destination_root)):
                raise FileValidationError(f"Path traversal detected in ZIP: {member.filename}")

            # Only extract allowed image formats
            if Path(member.filename).suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())
                extracted_images.append(target_path)

    return extracted_images
