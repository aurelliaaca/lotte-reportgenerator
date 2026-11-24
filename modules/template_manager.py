"""Template management, slide structure inspection, and configuration mapping."""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from config.settings import TEMPLATES_DIR, CONFIG_DIR, DEFAULT_CONFIG_PATH
from database.db import add_template, get_active_template


class TemplateManager:
    """Manages PowerPoint templates, schema inspection, and placeholder mapping."""

    @staticmethod
    def inspect_template(pptx_path: Path) -> Dict[str, Any]:
        """
        Analyze all slides and elements of a PowerPoint template.
        Identifies text placeholders, tables, shapes, and potential product slide layouts.
        """
        prs = Presentation(str(pptx_path))
        info = {
            "slide_width_inches": round(prs.slide_width.inches, 2),
            "slide_height_inches": round(prs.slide_height.inches, 2),
            "total_slides": len(prs.slides),
            "slides": [],
            "suggested_product_slide_index": 2 if len(prs.slides) >= 3 else (len(prs.slides) - 1),
        }

        for idx, slide in enumerate(prs.slides):
            slide_data = {
                "slide_index": idx,
                "slide_layout_name": slide.slide_layout.name,
                "shapes": [],
                "has_product_table": False,
                "table_details": None,
            }

            for shape in slide.shapes:
                text = shape.text_frame.text.strip().replace("\n", " ") if shape.has_text_frame else ""
                shape_data = {
                    "shape_id": shape.shape_id,
                    "name": shape.name,
                    "type": str(shape.shape_type),
                    "left_inches": round(shape.left.inches, 2),
                    "top_inches": round(shape.top.inches, 2),
                    "width_inches": round(shape.width.inches, 2),
                    "height_inches": round(shape.height.inches, 2),
                    "text": text[:100],
                }

                if shape.has_table:
                    t = shape.table
                    rows = len(t.rows)
                    cols = len(t.columns)
                    table_texts = []
                    foto_count = 0
                    nama_count = 0
                    for r in range(rows):
                        r_texts = []
                        for c in range(cols):
                            ct = t.cell(r, c).text.strip()
                            r_texts.append(ct)
                            if "foto" in ct.lower():
                                foto_count += 1
                            if "nama" in ct.lower() or "produk" in ct.lower():
                                nama_count += 1
                        table_texts.append(r_texts)

                    shape_data["table_summary"] = {
                        "rows": rows,
                        "cols": cols,
                        "foto_cells": foto_count,
                        "nama_cells": nama_count,
                    }
                    if foto_count >= 4 or nama_count >= 4 or (rows >= 4 and cols >= 3):
                        slide_data["has_product_table"] = True
                        info["suggested_product_slide_index"] = idx

                    slide_data["table_details"] = shape_data["table_summary"]

                slide_data["shapes"].append(shape_data)

            info["slides"].append(slide_data)

        return info

    @staticmethod
    def load_active_config() -> Dict[str, Any]:
        """Load configuration for the active template."""
        active = get_active_template()
        if active and active.get("config_path") and Path(active["config_path"]).exists():
            with open(active["config_path"], "r", encoding="utf-8") as f:
                return json.load(f)
        if DEFAULT_CONFIG_PATH.exists():
            with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        raise FileNotFoundError("Template configuration file not found.")

    @staticmethod
    def save_template_config(config_data: Dict[str, Any], config_path: Path) -> None:
        """Save template configuration to JSON."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

    @classmethod
    def register_new_template(
        cls,
        uploaded_file_path: Path,
        template_name: str,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Store a new PPTX template, generate its JSON mapping, and register in database.
        """
        dest_filename = f"template_{Path(uploaded_file_path).stem}_{Path(uploaded_file_path).name}"
        dest_pptx = TEMPLATES_DIR / dest_filename
        shutil.copy2(uploaded_file_path, dest_pptx)

        # Inspect and build config
        inspection = cls.inspect_template(dest_pptx)
        config = custom_config or cls.build_default_config_from_inspection(template_name, inspection)

        config_filename = f"config_{Path(dest_pptx).stem}.json"
        dest_config = CONFIG_DIR / config_filename
        cls.save_template_config(config, dest_config)

        # Register and set as active in DB
        return add_template(
            template_name=template_name,
            file_path=str(dest_pptx),
            config_path=str(dest_config),
            is_active=True,
        )

    @staticmethod
    def build_default_config_from_inspection(template_name: str, inspection: Dict[str, Any]) -> Dict[str, Any]:
        """Generate default configuration mapping based on inspection data."""
        prod_slide_idx = inspection.get("suggested_product_slide_index", 2)
        return {
            "template_name": template_name,
            "version": "1.0",
            "slide_dimensions": {
                "width_inches": inspection.get("slide_width_inches", 10.0),
                "height_inches": inspection.get("slide_height_inches", 7.5),
            },
            "title_slide": {
                "slide_index": 0,
                "title_shape_name": "Rectangle 1",
                "period_shape_name": "TextBox 5",
                "store_shape_name": "TextBox 8",
            },
            "banner_slide": {
                "slide_index": 1,
                "header_shape_name": "Rectangle 2",
                "header_prefix": "■ GS RETAIL (",
                "header_suffix": ")",
                "store_shape_name": "TextBox 5",
                "banner_table_shape_id": 2,
            },
            "product_slide": {
                "slide_index": prod_slide_idx,
                "header_shape_name": "Rectangle 3",
                "header_prefix": "■ GS RETAIL (",
                "header_suffix": ")",
                "store_shape_name": "TextBox 7",
                "table_shape_name": "Table 1",
                "products_per_slide": 8,
                "slots": [
                    {"slot_index": 0, "row_image": 1, "col_image": 0, "row_text": 2, "col_text": 0},
                    {"slot_index": 1, "row_image": 1, "col_image": 1, "row_text": 2, "col_text": 1},
                    {"slot_index": 2, "row_image": 1, "col_image": 2, "row_text": 2, "col_text": 2},
                    {"slot_index": 3, "row_image": 1, "col_image": 3, "row_text": 2, "col_text": 3},
                    {"slot_index": 4, "row_image": 4, "col_image": 0, "row_text": 5, "col_text": 0},
                    {"slot_index": 5, "row_image": 4, "col_image": 1, "row_text": 5, "col_text": 1},
                    {"slot_index": 6, "row_image": 4, "col_image": 2, "row_text": 5, "col_text": 2},
                    {"slot_index": 7, "row_image": 4, "col_image": 3, "row_text": 5, "col_text": 3},
                ],
                "formatting": {
                    "font_name": "The Jamsil 3 Regular",
                    "fallback_font": "Arial",
                    "font_size_pt": 10.5,
                    "bold": False,
                    "color_rgb": [0, 0, 0],
                    "alignment": "CENTER",
                    "include_price_in_card": False,
                    "price_font_size_pt": 9.0,
                },
            },
        }
