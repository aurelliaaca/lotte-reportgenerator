"""Unit tests for automatic image matching engine."""

import pytest
from modules.image_matcher import ImageMatcher


@pytest.fixture
def sample_images():
    return [
        {"filename": "rose_brand_minyak_goreng.jpg", "path": "/path/rose_brand_minyak_goreng.jpg", "normalized_name": "rose brand minyak goreng"},
        {"filename": "delmonte_extra_hot_5kg.jpg", "path": "/path/delmonte_extra_hot_5kg.jpg", "normalized_name": "delmonte extra hot 5kg"},
        {"filename": "sku_88501234_soap.png", "path": "/path/sku_88501234_soap.png", "normalized_name": "sku 88501234 soap"},
        {"filename": "rose_brand_2l.jpg", "path": "/path/rose_brand_2l.jpg", "normalized_name": "rose brand 2l"},
        {"filename": "sun_kara_santan.png", "path": "/path/sun_kara_santan.png", "normalized_name": "sun kara santan"},
    ]


def test_exact_sku_matching(sample_images):
    matcher = ImageMatcher()
    product = {"product_name": "CHOICE L Hand Soap", "sku": "88501234"}
    matched = matcher.match_products([product], sample_images)
    assert matched[0]["matching_status"] == "matched"
    assert matched[0]["matched_filename"] == "sku_88501234_soap.png"
    assert matched[0]["matching_score"] == 100.0


def test_exact_name_matching(sample_images):
    matcher = ImageMatcher()
    product = {"product_name": "Rose Brand Minyak Goreng", "sku": None}
    matched = matcher.match_products([product], sample_images)
    assert matched[0]["matching_status"] == "matched"
    assert matched[0]["matched_filename"] == "rose_brand_minyak_goreng.jpg"
    assert matched[0]["matching_score"] == 100.0


def test_variant_mismatch_penalty(sample_images):
    matcher = ImageMatcher()
    # Product is 18L, image pool has 'rose_brand_2l.jpg'
    product = {"product_name": "Rose Brand 18L", "sku": None}
    candidates = matcher.find_candidates_for_product(product, sample_images)
    # The 2L image should receive a size mismatch penalty and not be matched as high confidence
    img_2l = next((c for c in candidates if "2l" in c["filename"]), None)
    if img_2l:
        assert img_2l["score"] < matcher.high_threshold


def test_fuzzy_matching_sun_kara(sample_images):
    matcher = ImageMatcher()
    product = {"product_name": "SUN KARA Santan Kelapa 36x65ml", "sku": None}
    matched = matcher.match_products([product], sample_images)
    assert matched[0]["matched_filename"] == "sun_kara_santan.png"
    assert matched[0]["matching_score"] >= 80.0
