-- Weekly REOT Generator Database Schema

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    config_path TEXT NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS weekly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_name TEXT NOT NULL,
    reporting_period TEXT,
    store_name TEXT DEFAULT 'LSI MERUYA',
    pdf_filename TEXT,
    zip_filename TEXT,
    generated_ppt_path TEXT,
    product_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'created',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES weekly_reports(id) ON DELETE CASCADE,
    product_order INTEGER DEFAULT 0,
    product_name TEXT NOT NULL,
    sku TEXT,
    brand TEXT,
    normal_price TEXT,
    promo_price TEXT,
    promo_period TEXT,
    image_path TEXT,
    matched_filename TEXT,
    matching_score REAL DEFAULT 0.0,
    matching_status TEXT DEFAULT 'unmatched',
    extraction_confidence REAL DEFAULT 1.0,
    needs_review INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_report_id ON products(report_id);
CREATE INDEX IF NOT EXISTS idx_products_order ON products(report_id, product_order);
CREATE INDEX IF NOT EXISTS idx_reports_created ON weekly_reports(created_at DESC);
