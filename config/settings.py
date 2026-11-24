"""Global settings and configuration paths for Weekly REOT Generator."""

from pathlib import Path
import os
import shutil

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Storage paths
CONFIG_DIR = BASE_DIR / "config"
MODULES_DIR = BASE_DIR / "modules"
DATABASE_DIR = BASE_DIR / "database"
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOADS_DIR = BASE_DIR / "uploads" / "weekly_reports"
OUTPUTS_DIR = BASE_DIR / "outputs" / "generated_reports"
UTILS_DIR = BASE_DIR / "utils"

# Ensure directories exist
for p in [CONFIG_DIR, DATABASE_DIR, TEMPLATES_DIR, UPLOADS_DIR, OUTPUTS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_PATH = DATABASE_DIR / "reot_generator.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"

# Templates
DEFAULT_TEMPLATE_PATH = TEMPLATES_DIR / "reot_template.pptx"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "template_config.json"

# File constraints
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_ZIP_EXTENSIONS = {".zip"}
MAX_FILE_SIZE_MB = 150

# OCR & Tesseract settings
TESSERACT_PATH = shutil.which("tesseract") or "/opt/homebrew/bin/tesseract"

# Fuzzy matching thresholds
MATCH_HIGH_CONFIDENCE = 95.0
MATCH_SUGGESTED_CONFIDENCE = 80.0

# Slide configuration defaults
PRODUCTS_PER_SLIDE = 8
CARDS_PER_ROW = 4
ROWS_PER_SLIDE = 2
