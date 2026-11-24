"""PowerPoint report generator using fixed original REOT templates."""

import copy
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE_TYPE

from modules.template_manager import TemplateManager
from utils.helpers import get_report_output_dir


class PPTGenerator:
    """Generates customized PowerPoint reports using saved REOT presentation templates."""

    def __init__(self, template_path: Path, config: Optional[Dict[str, Any]] = None):
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"Template not found at: {template_path}")
        self.config = config or TemplateManager.load_active_config()

    def generate_report(
        self,
        report_id: int,
        week_name: str,
        reporting_period: str,
        products: List[Dict[str, Any]],
        store_name: str = "LSI MERUYA",
        flyer_image_path: Optional[Path] = None,
        custom_output_filename: Optional[str] = None,
    ) -> Path:
        """
        Generate complete presentation report with title slide, banner slide, and duplicated product slides.
        """
        prs = Presentation(str(self.template_path))
        prod_cfg = self.config.get("product_slide", {})
        title_cfg = self.config.get("title_slide", {})
        banner_cfg = self.config.get("banner_slide", {})

        products_per_slide = prod_cfg.get("products_per_slide", 8)
        total_products = len(products)
        needed_product_slides = max(1, math.ceil(total_products / products_per_slide))

        # 1. Update Title Slide (Slide 1)
        if len(prs.slides) > 0:
            self._update_title_slide(prs.slides[0], reporting_period, store_name, title_cfg)

        # 2. Update Banner Slide (Slide 2)
        if len(prs.slides) > 1:
            self._update_banner_slide(prs.slides[1], reporting_period, store_name, banner_cfg, flyer_image_path)

        # 3. Handle Product Slide(s)
        prod_slide_idx = prod_cfg.get("slide_index", 2)
        if prod_slide_idx >= len(prs.slides):
            prod_slide_idx = len(prs.slides) - 1

        base_product_slide = prs.slides[prod_slide_idx]

        # Duplicate product slide as many times as required
        product_slides = [base_product_slide]
        for _ in range(needed_product_slides - 1):
            cloned = self._duplicate_slide(prs, base_product_slide)
            product_slides.append(cloned)

        # 4. Populate each product slide
        slots = prod_cfg.get("slots", [])
        formatting = prod_cfg.get("formatting", {})

        for slide_num, slide in enumerate(product_slides):
            # Update slide header period and store
            self._update_product_slide_header(slide, reporting_period, store_name, prod_cfg)

            # Locate table on this slide
            table_shape = self._find_table_shape(slide, prod_cfg.get("table_shape_name", "Table 1"))
            if not table_shape:
                continue

            table = table_shape.table
            col_widths = [c.width for c in table.columns]
            row_heights = [r.height for r in table.rows]

            start_prod_idx = slide_num * products_per_slide
            for slot in slots:
                slot_idx = slot["slot_index"]
                current_prod_idx = start_prod_idx + slot_idx

                r_img = slot["row_image"]
                c_img = slot["col_image"]
                r_txt = slot["row_text"]
                c_txt = slot["col_text"]

                img_cell = table.cell(r_img, c_img)
                txt_cell = table.cell(r_txt, c_txt)

                if current_prod_idx < total_products:
                    product = products[current_prod_idx]
                    # Clear placeholder in image cell
                    img_cell.text = ""

                    # Insert image if present
                    img_path = product.get("image_path")
                    if img_path and Path(img_path).exists():
                        self._insert_fitted_image(
                            slide=slide,
                            image_path=Path(img_path),
                            table_left=table_shape.left,
                            table_top=table_shape.top,
                            col_widths=col_widths,
                            row_heights=row_heights,
                            row_idx=r_img,
                            col_idx=c_img,
                        )

                    # Populate text cell
                    self._populate_product_text(txt_cell, product, formatting)
                else:
                    # Clean out placeholder texts for unused slots
                    img_cell.text = ""
                    txt_cell.text = ""

        # 5. Save output PPTX
        output_dir = get_report_output_dir(report_id)
        clean_week_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in week_name)
        filename = custom_output_filename or f"REOT_{clean_week_name}.pptx"
        output_path = output_dir / filename

        prs.save(str(output_path))
        return output_path

    def _update_title_slide(self, slide, reporting_period: str, store_name: str, title_cfg: Dict[str, Any]) -> None:
        """Update period and store name in Title Slide."""
        period_name = title_cfg.get("period_shape_name", "TextBox 5")
        store_name_cfg = title_cfg.get("store_shape_name", "TextBox 8")

        for shape in slide.shapes:
            if shape.name == period_name and shape.has_text_frame:
                shape.text_frame.text = reporting_period
            elif shape.name == store_name_cfg and shape.has_text_frame:
                shape.text_frame.text = store_name

    def _update_banner_slide(
        self,
        slide,
        reporting_period: str,
        store_name: str,
        banner_cfg: Dict[str, Any],
        flyer_image_path: Optional[Path],
    ) -> None:
        """Update header and insert flyer image on Banner Slide."""
        hdr_prefix = banner_cfg.get("header_prefix", "■ GS RETAIL (")
        hdr_suffix = banner_cfg.get("header_suffix", ")")
        store_name_cfg = banner_cfg.get("store_shape_name", "TextBox 5")

        for shape in slide.shapes:
            if shape.has_text_frame:
                if "GS RETAIL" in shape.text_frame.text:
                    shape.text_frame.text = f"{hdr_prefix}{reporting_period}{hdr_suffix}"
                elif shape.name == store_name_cfg:
                    shape.text_frame.text = store_name

        # If flyer banner image provided, insert onto slide
        if flyer_image_path and flyer_image_path.exists():
            table_shape = self._find_table_shape(slide, "Table 1")
            left = table_shape.left if table_shape else Inches(0.28)
            top = table_shape.top if table_shape else Inches(0.75)
            width = table_shape.width if table_shape else Inches(9.45)
            height = table_shape.height if table_shape else Inches(6.58)

            # Fit flyer image
            self._insert_fitted_image_direct(slide, flyer_image_path, left, top, width, height)

    def _update_product_slide_header(self, slide, reporting_period: str, store_name: str, prod_cfg: Dict[str, Any]) -> None:
        """Update header date and store on product slide."""
        hdr_prefix = prod_cfg.get("header_prefix", "■ GS RETAIL (")
        hdr_suffix = prod_cfg.get("header_suffix", ")")
        store_name_cfg = prod_cfg.get("store_shape_name", "TextBox 7")

        for shape in slide.shapes:
            if shape.has_text_frame:
                if "GS RETAIL" in shape.text_frame.text:
                    shape.text_frame.text = f"{hdr_prefix}{reporting_period}{hdr_suffix}"
                elif shape.name == store_name_cfg:
                    shape.text_frame.text = store_name

    def _duplicate_slide(self, prs, source_slide):
        """
        Deep clone a slide element and relationships to replicate identical formatting and shapes.
        """
        new_slide = prs.slides.add_slide(source_slide.slide_layout)
        # Clear default shapes
        for shp in list(new_slide.shapes):
            sp = shp._element
            sp.getparent().remove(sp)

        # Deep copy all shape XML elements
        for shape in source_slide.shapes:
            new_el = copy.deepcopy(shape._element)
            new_slide.shapes._spTree.append(new_el)

        # Copy non-layout relationships
        for rel_id, rel in source_slide.part.rels.items():
            if "slideLayout" not in rel.reltype:
                new_slide.part.rels.add_relationship(rel.reltype, rel.target_ref, rel.target_mode)

        return new_slide

    def _find_table_shape(self, slide, preferred_name: str = "Table 1"):
        """Locate table shape by preferred name or first table available."""
        for shape in slide.shapes:
            if shape.has_table and shape.name == preferred_name:
                return shape
        for shape in slide.shapes:
            if shape.has_table:
                return shape
        return None

    def _insert_fitted_image(
        self,
        slide,
        image_path: Path,
        table_left: int,
        table_top: int,
        col_widths: List[int],
        row_heights: List[int],
        row_idx: int,
        col_idx: int,
        padding_ratio: float = 0.05,
    ) -> None:
        """Fit and center product image inside cell boundaries without distorting aspect ratio."""
        cell_left = table_left + sum(col_widths[:col_idx])
        cell_top = table_top + sum(row_heights[:row_idx])
        cell_w = col_widths[col_idx]
        cell_h = row_heights[row_idx]

        self._insert_fitted_image_direct(slide, image_path, cell_left, cell_top, cell_w, cell_h, padding_ratio)

    def _insert_fitted_image_direct(
        self,
        slide,
        image_path: Path,
        target_left: int,
        target_top: int,
        target_w: int,
        target_h: int,
        padding_ratio: float = 0.04,
    ) -> None:
        """Calculate aspect-ratio-preserving bounds with padding and insert image into slide."""
        try:
            with Image.open(image_path) as img:
                orig_w, orig_h = img.size
        except Exception as e:
            print(f"Error opening image {image_path}: {e}")
            return

        pad_x = int(target_w * padding_ratio)
        pad_y = int(target_h * padding_ratio)
        avail_w = target_w - (2 * pad_x)
        avail_h = target_h - (2 * pad_y)

        scale = min(avail_w / orig_w, avail_h / orig_h)
        fit_w = int(orig_w * scale)
        fit_h = int(orig_h * scale)

        offset_x = (avail_w - fit_w) // 2
        offset_y = (avail_h - fit_h) // 2

        img_left = target_left + pad_x + offset_x
        img_top = target_top + pad_y + offset_y

        slide.shapes.add_picture(str(image_path), img_left, img_top, fit_w, fit_h)

    def _populate_product_text(self, cell, product: Dict[str, Any], formatting: Dict[str, Any]) -> None:
        """Populate product name, pack size, and optional price with consistent font styling."""
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf = cell.text_frame
        tf.word_wrap = True
        tf.clear()

        prod_name = product.get("product_name", "").strip()
        sku = product.get("sku")
        promo_price = product.get("promo_price")
        include_price = formatting.get("include_price_in_card", False)

        font_name = formatting.get("font_name", "The Jamsil 3 Regular")
        font_size = formatting.get("font_size_pt", 10.5)
        bold = formatting.get("bold", False)
        color_rgb = formatting.get("color_rgb", [0, 0, 0])

        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = prod_name
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = RGBColor(*color_rgb)

        if include_price and promo_price:
            p2 = tf.add_paragraph()
            p2.alignment = PP_ALIGN.CENTER
            run2 = p2.add_run()
            run2.text = str(promo_price)
            run2.font.name = font_name
            run2.font.size = Pt(formatting.get("price_font_size_pt", 9.0))
            run2.font.bold = True
            run2.font.color.rgb = RGBColor(180, 0, 0)
