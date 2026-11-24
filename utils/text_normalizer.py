"""Text normalization and cleansing utilities for PDF extraction and image matching."""

import re
import unicodedata
from typing import Optional, Tuple


def normalize_text(text: Optional[str]) -> str:
    """Basic unicode normalization and whitespace stripping."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_matching(text: Optional[str]) -> str:
    """
    Produce a normalized alphanumeric representation for fuzzy and exact matching.
    Lowercases, removes special punctuation, replaces dashes/underscores with space.
    """
    if not text:
        return ""
    text = normalize_text(text).lower()
    # Remove file extension if present (e.g. .jpg, .png)
    text = re.sub(r"\.(jpe?g|png|webp|gif|bmp)$", "", text, flags=re.IGNORECASE)
    # Replace separators with space
    text = re.sub(r"[-_–—/\\+&,.]", " ", text)
    # Remove symbols like quotes, parentheses, brackets
    text = re.sub(r"['\"`’()\[\]*!?:;]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_sku_or_code(text: str) -> Optional[str]:
    """Search for SKU, barcode, or numeric item code (e.g., 6-14 digit numbers or SKU-xxx)."""
    if not text:
        return None
    # Check for explicit SKU pattern: SKU: 123456 or SKU-12345
    match_sku = re.search(r"\b(?:SKU|ITEM|KODE)[:\s-]*([A-Z0-9]{5,14})\b", text, flags=re.IGNORECASE)
    if match_sku:
        return match_sku.group(1).upper()
    # Check for barcode (8 to 14 digits)
    match_barcode = re.search(r"\b(\d{8,14})\b", text)
    if match_barcode:
        return match_barcode.group(1)
    return None


def extract_price_value(price_text: str) -> Optional[int]:
    """
    Extract integer numeric price from Indonesian currency strings.
    E.g. 'Rp 106.000', 'Rp. 154.500', '/karton148.200' -> 106000, 154500, 148200.
    """
    if not price_text:
        return None
    cleaned = re.sub(r"[^\d.]", "", price_text)
    # Remove dot thousand separators
    cleaned = cleaned.replace(".", "")
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


def split_product_name_and_pack(full_text: str) -> Tuple[str, str]:
    """
    Separate product brand/name from pack size/variant if joined by dash or newline.
    E.g. 'ROSE BRAND Minyak Goreng – Jerigen 18L' -> ('ROSE BRAND Minyak Goreng', 'Jerigen 18L')
    """
    text = normalize_text(full_text)
    if " – " in text:
        parts = text.split(" – ", 1)
        return parts[0].strip(), parts[1].strip()
    if " - " in text:
        parts = text.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return text, ""
