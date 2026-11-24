"""Automatic product image matching engine powered by RapidFuzz and SKU validation."""

import re
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz
from config.settings import MATCH_HIGH_CONFIDENCE, MATCH_SUGGESTED_CONFIDENCE
from utils.text_normalizer import normalize_for_matching


class ImageMatcher:
    """Matches product records against uploaded image pool using tiered heuristics."""

    def __init__(
        self,
        high_threshold: float = MATCH_HIGH_CONFIDENCE,
        suggested_threshold: float = MATCH_SUGGESTED_CONFIDENCE,
    ):
        self.high_threshold = high_threshold
        self.suggested_threshold = suggested_threshold

    def match_products(
        self,
        products: List[Dict[str, Any]],
        images: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Match all products against available images.
        Updates product dictionaries with matched image details, score, status, and candidates.
        """
        if not images:
            for p in products:
                p["image_path"] = None
                p["matched_filename"] = None
                p["matching_score"] = 0.0
                p["matching_status"] = "unmatched"
                p["candidates"] = []
            return products

        image_usage_count: Dict[str, int] = {img["path"]: 0 for img in images}

        for prod in products:
            candidates = self.find_candidates_for_product(prod, images)
            prod["candidates"] = candidates

            if candidates:
                best = candidates[0]
                score = best["score"]
                prod["matching_score"] = score
                prod["matched_filename"] = best["filename"]
                prod["image_path"] = best["path"]

                if score >= self.high_threshold:
                    prod["matching_status"] = "matched"
                elif score >= self.suggested_threshold:
                    prod["matching_status"] = "suggested"
                    prod["needs_review"] = 1
                else:
                    prod["matching_status"] = "unmatched"
                    prod["image_path"] = None
                    prod["matched_filename"] = None

                if prod.get("image_path"):
                    image_usage_count[prod["image_path"]] += 1
            else:
                prod["matching_score"] = 0.0
                prod["matching_status"] = "unmatched"
                prod["image_path"] = None
                prod["matched_filename"] = None

        # Ambiguity check: flag if an image was matched to multiple distinct products
        for prod in products:
            img_p = prod.get("image_path")
            if img_p and image_usage_count.get(img_p, 0) > 1:
                prod["matching_status"] = "suggested"
                prod["needs_review"] = 1
                prod["ambiguity_warning"] = "Same image matched to multiple products"

        return products

    def find_candidates_for_product(
        self,
        product: Dict[str, Any],
        images: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank all images against a product and return sorted candidate matches.
        """
        prod_name = product.get("product_name", "")
        prod_sku = product.get("sku")
        prod_norm = normalize_for_matching(prod_name)
        prod_size_tokens = self._extract_size_tokens(prod_norm)

        candidates = []

        for img in images:
            img_filename = img["filename"]
            img_norm = img.get("normalized_name") or normalize_for_matching(img_filename)
            img_size_tokens = self._extract_size_tokens(img_norm)

            score, match_type = self._compute_similarity(
                prod_sku=prod_sku,
                prod_norm=prod_norm,
                prod_size_tokens=prod_size_tokens,
                img_filename=img_filename,
                img_norm=img_norm,
                img_size_tokens=img_size_tokens,
            )

            if score > 30:  # Include meaningful candidates
                candidates.append({
                    "filename": img_filename,
                    "path": img["path"],
                    "thumbnail_path": img.get("thumbnail_path"),
                    "score": round(score, 1),
                    "match_type": match_type,
                })

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates

    def _compute_similarity(
        self,
        prod_sku: Optional[str],
        prod_norm: str,
        prod_size_tokens: List[str],
        img_filename: str,
        img_norm: str,
        img_size_tokens: List[str],
    ) -> Tuple[float, str]:
        """Calculate similarity score based on tiered priority rules."""
        # 1. Exact SKU / Barcode Match
        if prod_sku and prod_sku.lower() in img_filename.lower():
            return 100.0, "exact_sku"

        # 2. Exact Normalized Filename Match
        if prod_norm == img_norm:
            return 100.0, "exact_name"

        # 3. Size / Variant Incompatibility Check
        # If both product and image specify a pack size/variant and they are completely different
        size_mismatch = False
        if prod_size_tokens and img_size_tokens:
            common = set(prod_size_tokens).intersection(set(img_size_tokens))
            if not common:
                size_mismatch = True

        # 4. Direct Substring Match
        if prod_norm in img_norm or img_norm in prod_norm:
            base_score = 96.0
            if size_mismatch:
                base_score -= 25.0
            return base_score, "substring_match"

        # 5. Fuzzy Token Matching
        token_sort = fuzz.token_sort_ratio(prod_norm, img_norm)
        token_set = fuzz.token_set_ratio(prod_norm, img_norm)
        partial = fuzz.partial_ratio(prod_norm, img_norm)

        # Weighted combination
        fuzzy_score = (token_sort * 0.4) + (token_set * 0.4) + (partial * 0.2)

        if size_mismatch:
            fuzzy_score = max(0.0, fuzzy_score - 30.0)

        return fuzzy_score, "fuzzy_match"

    @staticmethod
    def _extract_size_tokens(text: str) -> List[str]:
        """Extract size/weight/volume tokens like '18l', '500ml', '1kg', '35g'."""
        return re.findall(r"\b\d+(?:[.,]\d+)?(?:ml|l|kg|g|gr|pcs|rcg|box)\b", text, re.IGNORECASE)
