"""Database connection and repository operations for Weekly REOT Generator."""

import sqlite3
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from config.settings import DATABASE_PATH, SCHEMA_PATH, DEFAULT_TEMPLATE_PATH, DEFAULT_CONFIG_PATH


def get_connection() -> sqlite3.Connection:
    """Create and return a database connection with foreign key support enabled."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Initialize database tables using schema.sql and seed default template if empty."""
    with get_connection() as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        
        # Check if default template is seeded
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM templates;")
        if cur.fetchone()["cnt"] == 0 and os.path.exists(DEFAULT_TEMPLATE_PATH):
            cur.execute(
                """
                INSERT INTO templates (template_name, file_path, config_path, is_active)
                VALUES (?, ?, ?, 1);
                """,
                (
                    "Default GS Retail Template",
                    str(DEFAULT_TEMPLATE_PATH),
                    str(DEFAULT_CONFIG_PATH),
                ),
            )
        conn.commit()


# --- Template Operations ---

def get_active_template() -> Optional[Dict[str, Any]]:
    """Retrieve the currently active template record."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM templates WHERE is_active = 1 ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        return dict(row) if row else None


def list_templates() -> List[Dict[str, Any]]:
    """Retrieve all available templates."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM templates ORDER BY uploaded_at DESC;")
        return [dict(row) for row in cur.fetchall()]


def set_active_template(template_id: int) -> bool:
    """Set a specific template as active and deactivate all others."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE templates SET is_active = 0;")
        cur.execute("UPDATE templates SET is_active = 1 WHERE id = ?;", (template_id,))
        conn.commit()
        return cur.rowcount > 0


def add_template(template_name: str, file_path: str, config_path: str, is_active: bool = True) -> int:
    """Add a new template record to the database."""
    with get_connection() as conn:
        cur = conn.cursor()
        if is_active:
            cur.execute("UPDATE templates SET is_active = 0;")
        cur.execute(
            """
            INSERT INTO templates (template_name, file_path, config_path, is_active)
            VALUES (?, ?, ?, ?);
            """,
            (template_name, file_path, config_path, 1 if is_active else 0),
        )
        conn.commit()
        return cur.lastrowid


# --- Weekly Report Operations ---

def create_report(
    week_name: str,
    reporting_period: str,
    store_name: str = "LSI MERUYA",
    pdf_filename: Optional[str] = None,
    zip_filename: Optional[str] = None,
) -> int:
    """Create a new weekly report entry."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO weekly_reports (week_name, reporting_period, store_name, pdf_filename, zip_filename, status)
            VALUES (?, ?, ?, ?, ?, 'created');
            """,
            (week_name, reporting_period, store_name, pdf_filename, zip_filename),
        )
        conn.commit()
        return cur.lastrowid


def get_report(report_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a report by ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM weekly_reports WHERE id = ?;", (report_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_reports() -> List[Dict[str, Any]]:
    """List all weekly reports ordered by creation date descending."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM weekly_reports ORDER BY id DESC;")
        return [dict(row) for row in cur.fetchall()]


def update_report_status(report_id: int, status: str, product_count: Optional[int] = None, generated_ppt_path: Optional[str] = None) -> bool:
    """Update report status, product count, and generated PPTX path."""
    with get_connection() as conn:
        cur = conn.cursor()
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [status]
        if product_count is not None:
            updates.append("product_count = ?")
            params.append(product_count)
        if generated_ppt_path is not None:
            updates.append("generated_ppt_path = ?")
            params.append(generated_ppt_path)
        params.append(report_id)
        
        query = f"UPDATE weekly_reports SET {', '.join(updates)} WHERE id = ?;"
        cur.execute(query, tuple(params))
        conn.commit()
        return cur.rowcount > 0


def delete_report(report_id: int) -> bool:
    """Delete a report and cascade delete all its products."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM weekly_reports WHERE id = ?;", (report_id,))
        conn.commit()
        return cur.rowcount > 0


# --- Product Operations ---

def save_products(report_id: int, products: List[Dict[str, Any]]) -> None:
    """Save extracted products for a report (replacing existing ones)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE report_id = ?;", (report_id,))
        
        insert_sql = """
            INSERT INTO products (
                report_id, product_order, product_name, sku, brand,
                normal_price, promo_price, promo_period, image_path,
                matched_filename, matching_score, matching_status,
                extraction_confidence, needs_review
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        records = []
        for idx, p in enumerate(products):
            records.append((
                report_id,
                p.get("product_order", idx),
                p.get("product_name", "").strip(),
                p.get("sku"),
                p.get("brand"),
                p.get("normal_price"),
                p.get("promo_price"),
                p.get("promo_period"),
                p.get("image_path"),
                p.get("matched_filename"),
                p.get("matching_score", 0.0),
                p.get("matching_status", "unmatched"),
                p.get("extraction_confidence", 1.0),
                1 if p.get("needs_review") else 0
            ))
        cur.executemany(insert_sql, records)
        cur.execute("UPDATE weekly_reports SET product_count = ? WHERE id = ?;", (len(records), report_id))
        conn.commit()


def get_products_by_report(report_id: int) -> List[Dict[str, Any]]:
    """Retrieve all products for a report ordered by product_order."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE report_id = ? ORDER BY product_order ASC;", (report_id,))
        return [dict(row) for row in cur.fetchall()]


def update_product(product_id: int, updates: Dict[str, Any]) -> bool:
    """Update fields of a specific product."""
    allowed_keys = {
        "product_name", "sku", "brand", "normal_price", "promo_price",
        "promo_period", "image_path", "matched_filename", "matching_score",
        "matching_status", "needs_review", "product_order"
    }
    filtered = {k: v for k, v in updates.items() if k in allowed_keys}
    if not filtered:
        return False
        
    set_clause = ", ".join([f"{k} = ?" for k in filtered.keys()])
    params = list(filtered.values()) + [product_id]
    
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE products SET {set_clause} WHERE id = ?;", tuple(params))
        conn.commit()
        return cur.rowcount > 0


def delete_product(product_id: int) -> bool:
    """Delete a single product record."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM products WHERE id = ?;", (product_id,))
        conn.commit()
        return cur.rowcount > 0
