"""Product data parsing, normalization, bundling segmentation, and validation."""

import re
from typing import List, Dict, Any, Optional
from utils.text_normalizer import (
    normalize_text,
    normalize_for_matching,
    extract_sku_or_code,
)


KNOWN_BRANDS = [
    "ROSE BRAND", "DELMONTE", "CHOICE L", "AMIDIS", "ULTRA MILK",
    "DUA KELINCI", "GENKI", "SELECTION", "3 AYAM", "SEGITIGA BIRU",
    "SUN KARA", "INDOFOOD", "GOOD DAY", "FANTA", "COCA COLA", "SPRITE",
    "DELFI", "APETITO", "NYAM NYAM", "INDOMILK", "MINUTE MAID",
    "CLEAR", "SIDOMUNCUL", "DAIA", "MAMA LEMON", "MAMA", "SEDAAP",
    "BIMOLI", "SANIA", "FILMA", "TROPICAL", "KRAFT", "CHITATO", "TANGO"
]

PACK_SIZE_REGEX = r"(\d+(?:[.,]\d+)?(?:\s*(?:x\s*\d+(?:[.,]\d+)?)*)?\s*(?:ml|l|kg|g|gr|pcs|box|rcg|renceng|s|’s|’S|karton|jerigen|bundle)\b)"

DISCLAIMER_KEYWORDS = [
    "spesial member", "cokelat & hijau", "grosir", "surprise", "spesial promo",
    "pedagang & horeka", "jawa, bali, sumatera", "setiap pembelian",
    "berlaku kelipatan", "spesial bundling", "berlaku untuk", "syarat & ketentuan",
    "khusus bagi pemegang", "dengan minimal belanja", "setiap kamis", "dapatkan",
    "potongan langsung", "hingga", "homecare fair", "gratis", "senilai rp",
    "maksimal", "beli 12", "beli 3", "perkarton", "perrenceng"
]


class ProductProcessor:
    """Parses and refines raw text into clean product records."""

    @classmethod
    def clean_and_normalize_product(cls, raw_name: str, raw_price: Optional[str] = None) -> Dict[str, Any]:
        """Convert a single product text candidate into a structured dictionary."""
        name = normalize_text(raw_name)
        # Fix double units like mlml -> ml
        name = re.sub(r"mlml\b", "ml", name, flags=re.IGNORECASE)
        # Fix accidental dash in fractional weights e.g. 70/ - 72g -> 70/72g
        name = re.sub(r"/\s*[-–]\s*", "/", name)

        formatted_name = cls.format_display_name(name)
        brand = cls.detect_brand(formatted_name)
        sku = extract_sku_or_code(formatted_name)

        return {
            "product_name": formatted_name,
            "sku": sku,
            "brand": brand,
            "normal_price": None,
            "promo_price": raw_price,
            "promo_period": None,
            "image_path": None,
            "matched_filename": None,
            "matching_score": 0.0,
            "matching_status": "unmatched",
            "extraction_confidence": 0.95 if brand else 0.85,
            "needs_review": 0,
        }

    @classmethod
    def format_display_name(cls, text: str) -> str:
        """
        Standardize display name formatting:
        e.g. 'ROSE BRAND Minyak Goreng Jerigen 18L' -> 'ROSE BRAND Minyak Goreng – Jerigen 18L'
        """
        text = text.replace("–", "-").replace("—", "-")
        # If already formatted with dash, clean spaces around dash
        if " - " in text:
            parts = text.split(" - ", 1)
            return f"{parts[0].strip()} – {parts[1].strip()}"

        # If has slash in packaging like 70/72g, do not add dash across slash
        # Check for trailing pack size or packaging variant
        match = re.search(
            r"\b(Jerigen\s+\d+L|Karton\s+\d+|Pouch\s+\d+|Botol\s+\d+|\d+x\d+.*|\d+,\d+/\d+,\d+kg|\d+/\d+g|\d+\s*(?:ml|l|kg|g|’s))\b",
            text,
            re.IGNORECASE,
        )
        if match and match.start() > 2:
            prefix = text[:match.start()].strip()
            suffix = text[match.start():].strip()
            # Do not split if prefix is just another variant e.g. '70' in '70/72g'
            if prefix and suffix and not prefix.endswith("/"):
                return f"{prefix} – {suffix}"

        return text

    @classmethod
    def detect_brand(cls, text: str) -> Optional[str]:
        """Identify matching brand name from knowledge base."""
        upper = text.upper()
        for brand in KNOWN_BRANDS:
            if re.search(r"\b" + re.escape(brand) + r"\b", upper):
                return brand
        return None

    @classmethod
    def is_disclaimer_or_banner_header(cls, text: str) -> bool:
        """Check if text line is marketing banner copy rather than a product name."""
        lower = text.lower().strip()
        if len(lower) < 3:
            return True
        # Pure quantity like '12pcs', '6box', '20rcg'
        if re.fullmatch(r"[\*\-\+]?\s*\d+\s*(?:pcs|box|rcg|renceng|karton)", lower):
            return True
        # Disclaimers like *Maksimal 6 Box
        if re.search(r"\b(?:maksimal\s+\d+|beli\s+\d+|senilai\s+rp|syarat\s+&\s+ketentuan)\b", lower):
            return True
        # Pure price line
        if re.search(r"^(?:rp\.?|luar jawa|batam|\*jabodetabek|\*jawa)", lower):
            return True
        # Check disclaimers
        for kw in DISCLAIMER_KEYWORDS:
            if kw in lower and not any(b.lower() in lower for b in KNOWN_BRANDS):
                return True
        return False

    @classmethod
    def segment_bundle_text(cls, text: str) -> List[str]:
        """
        Split bundled promotions containing multiple products into individual items.
        E.g. 'AMIDIS Botol 24x330ml // ULTRA MILK 40x125ml' -> ['AMIDIS Botol 24x330ml', 'ULTRA MILK 40x125ml']
        Respects slash-joined brands like FANTA/COCA COLA/SPRITE.
        """
        # If text is slash joined brands like FANTA/COCA COLA/SPRITE, do NOT split
        if re.search(r"FANTA\s*/\s*COCA\s*COLA\s*/\s*SPRITE", text, re.I):
            return [re.sub(r"\s+", " ", text).strip()]

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return []

        items: List[str] = []
        current_chunk: List[str] = []

        for line in lines:
            has_brand = bool(cls.detect_brand(line))
            if has_brand and current_chunk:
                combined_prev = " ".join(current_chunk)
                if cls.detect_brand(combined_prev) or re.search(PACK_SIZE_REGEX, combined_prev, re.I):
                    items.append(combined_prev)
                    current_chunk = [line]
                    continue
            current_chunk.append(line)

        if current_chunk:
            items.append(" ".join(current_chunk))

        final_items = []
        for it in items:
            # Check for multiple distinct brands that are NOT separated by slashes
            detected_brands = []
            for b in KNOWN_BRANDS:
                for m in re.finditer(r"\b" + re.escape(b) + r"\b", it, re.I):
                    # verify it's not immediately preceded or followed by a slash
                    start = m.start()
                    end = m.end()
                    pre_char = it[start - 1] if start > 0 else " "
                    post_char = it[end] if end < len(it) else " "
                    if pre_char != "/" and post_char != "/":
                        detected_brands.append((start, m.group()))

            detected_brands.sort(key=lambda x: x[0])
            if len(detected_brands) > 1:
                cut_points = [idx for idx, _ in detected_brands] + [len(it)]
                for i in range(len(cut_points) - 1):
                    sub = it[cut_points[i]:cut_points[i + 1]].strip()
                    if sub:
                        final_items.append(sub)
            else:
                final_items.append(it)

        return final_items

    @classmethod
    def deduplicate_products(cls, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove exact and near-duplicate product entries while preserving order."""
        seen = set()
        deduped = []
        for p in products:
            norm = normalize_for_matching(p["product_name"])
            if norm and norm not in seen:
                seen.add(norm)
                deduped.append(p)
        return deduped
