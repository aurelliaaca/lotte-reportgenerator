"""Weekly REOT Generator - Automated PDF-to-PowerPoint Report Generation System.
Streamlit Web Application Interface with Direct Device Camera Integration.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from PIL import Image
import streamlit as st

# Application modules
from config.settings import (
    BASE_DIR,
    DEFAULT_TEMPLATE_PATH,
    DEFAULT_CONFIG_PATH,
    MATCH_HIGH_CONFIDENCE,
    MATCH_SUGGESTED_CONFIDENCE,
    TESSERACT_PATH,
)
from database.db import (
    init_db,
    get_active_template,
    list_templates,
    set_active_template,
    list_reports,
    get_report,
    get_products_by_report,
    update_product,
    delete_product,
    save_products,
)
from modules.template_manager import TemplateManager
from modules.report_manager import ReportManager
from modules.image_handler import ImageHandler
from modules.ocr_processor import OCRProcessor
from utils.helpers import format_rupiah, get_report_output_dir, get_report_upload_dir

# Initialize database
init_db()

# Streamlit Page Configuration
st.set_page_config(
    page_title="Weekly REOT Generator",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS Styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1.0rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .step-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1F2937;
        margin-top: 1.2rem;
        margin-bottom: 0.5rem;
    }
    .product-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.8rem;
    }
    .badge-captured {
        background-color: #DCFCE7;
        color: #15803D;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-missing {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 700;
        display: inline-block;
    }
    .camera-box {
        background-color: #EFF6FF;
        border: 2px dashed #3B82F6;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 0.5rem;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_sidebar():
    """Render sidebar navigation."""
    with st.sidebar:
        st.markdown("### 📸 REOT GENERATOR")
        st.markdown("**Automated Report System**")
        st.markdown("---")

        active_tmpl = get_active_template()
        if active_tmpl:
            st.success(f"Template: **{active_tmpl['template_name']}**")
        else:
            st.warning("No active template loaded.")

        nav = st.radio(
            "Navigation",
            [
                "Dashboard",
                "Create Weekly Report",
                "Product Review",
                "Template Management",
                "Report History",
                "Settings",
            ],
            index=0,
        )

        st.markdown("---")
        st.caption("Version 2.0 • Device Camera & REOT Automation")
        return nav


def view_dashboard():
    """Render main dashboard overview."""
    st.markdown('<div class="main-title">WEEKLY REOT GENERATOR</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Extract promotional catalog data and capture product photos directly using your device camera.</div>',
        unsafe_allow_html=True,
    )

    reports = list_reports()
    active_tmpl = get_active_template()

    # KPI Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Reports", len(reports))
    with col2:
        latest_week = reports[0]["week_name"] if reports else "None"
        st.metric("Latest Report", latest_week)
    with col3:
        latest_status = reports[0]["status"].upper() if reports else "N/A"
        st.metric("Latest Status", latest_status)
    with col4:
        template_status = "Active" if active_tmpl else "Missing"
        st.metric("Template Status", template_status)

    st.markdown("---")

    # Quick Action Banner
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("#### Ready to create this week's REOT report?")
        st.write("Upload your promotional PDF, take product display photos directly from your smartphone or webcam, and generate the PowerPoint report.")
    with c2:
        if st.button("🚀 Create New Report", type="primary", use_container_width=True):
            st.session_state["nav"] = "Create Weekly Report"
            st.rerun()

    st.markdown("### Recent Weekly Reports")
    if not reports:
        st.info("No reports created yet. Click 'Create New Report' to start your first weekly report.")
    else:
        table_data = []
        for r in reports[:5]:
            table_data.append({
                "ID": r["id"],
                "Week Name": r["week_name"],
                "Period": r["reporting_period"],
                "Store": r["store_name"],
                "Products": r["product_count"],
                "Status": r["status"].upper(),
                "Created At": r["created_at"][:16],
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)


def view_create_report():
    """Weekly report generation wizard with direct camera capture."""
    st.markdown('<div class="main-title">Create Weekly Report</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Extract product names from PDF, take photos directly with your camera, and generate the presentation.</div>',
        unsafe_allow_html=True,
    )

    if "current_report_id" not in st.session_state:
        st.session_state["current_report_id"] = None
    if "active_camera_id" not in st.session_state:
        st.session_state["active_camera_id"] = None
    if "active_upload_id" not in st.session_state:
        st.session_state["active_upload_id"] = None
    if "filter_status" not in st.session_state:
        st.session_state["filter_status"] = "All"

    # Step 1: Reporting Period and Store
    st.markdown('<div class="step-header">STEP 1: Report Information</div>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        week_name = st.text_input("Week / Title Name", value="Week 48 November 2026")
    with col2:
        reporting_period = st.text_input("Reporting Period", value="24 – 30 November 2026", help="Automatically extracted from PDF if present.")
    with col3:
        store_name = st.text_input("Store Name", value="LSI MERUYA")

    st.markdown("---")

    # Step 2: PDF Upload
    st.markdown('<div class="step-header">STEP 2: Upload Promotional PDF Catalog</div>', unsafe_allow_html=True)
    pdf_file = st.file_uploader(
        "Upload Promotional PDF",
        type=["pdf"],
        help="Text or scanned PDF containing weekly promotional products and prices.",
    )
    if pdf_file:
        st.success(f"Loaded PDF: **{pdf_file.name}** ({pdf_file.size / (1024*1024):.2f} MB)")

    # Optional bulk ZIP uploader
    with st.expander("📁 (Optional) Upload bulk product images ZIP instead of camera"):
        zip_file = st.file_uploader("ZIP containing product images", type=["zip"], key="optional_zip")
        if zip_file and st.button("Extract and Auto-Match from ZIP"):
            try:
                rep_id = ReportManager.create_weekly_report(
                    week_name=week_name,
                    reporting_period=reporting_period,
                    store_name=store_name,
                    pdf_file_bytes=pdf_file.getvalue() if pdf_file else None,
                    pdf_filename=pdf_file.name if pdf_file else None,
                    zip_file_bytes=zip_file.getvalue(),
                    zip_filename=zip_file.name,
                )
                res = ReportManager.process_weekly_files(rep_id)
                st.session_state["current_report_id"] = rep_id
                st.success(f"Processed {res['product_count']} products and auto-matched {res['image_count']} images.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # Step 3: Extract Products & Initialize Camera Workflow
    st.markdown('<div class="step-header">STEP 3: Extract Products & Open Camera List</div>', unsafe_allow_html=True)
    if st.button("⚡ Extract Products from PDF & Start Camera Workflow", type="primary", use_container_width=True):
        if not pdf_file:
            st.error("Please upload the promotional PDF catalog first.")
            return

        with st.spinner("Extracting products and initializing report..."):
            try:
                rep_id = ReportManager.create_weekly_report(
                    week_name=week_name,
                    reporting_period=reporting_period,
                    store_name=store_name,
                    pdf_file_bytes=pdf_file.getvalue(),
                    pdf_filename=pdf_file.name,
                )
                prods = ReportManager.extract_and_save_products_from_pdf(rep_id)
                st.session_state["current_report_id"] = rep_id
                st.success(f"Extracted {len(prods)} products successfully! You can now take photos for each product below.")
                st.rerun()
            except Exception as e:
                st.error(f"Extraction error: {e}")

    curr_id = st.session_state.get("current_report_id")

    # Step 4: Product Camera List & Image Review
    if curr_id:
        report = get_report(curr_id)
        products = get_products_by_report(curr_id)
        prog = ReportManager.get_capture_progress(curr_id)

        st.markdown("---")
        st.markdown(f'<div class="step-header">STEP 4: Product Photos & Camera Capture (Report #{curr_id})</div>', unsafe_allow_html=True)

        # Progress bar & metrics
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            st.metric("Total Products", prog["total"])
        with p_col2:
            st.metric("Photos Captured", f"{prog['captured']} / {prog['total']}")
        with p_col3:
            st.metric("Remaining", prog["missing"])

        st.progress(prog["percent"] / 100.0)
        st.caption(f"**Progress:** {prog['captured']} of {prog['total']} products captured ({prog['percent']}%)")

        # Filter radio
        filter_opt = st.radio(
            "Filter Product List",
            [f"All Products ({prog['total']})", f"Missing Photo ({prog['missing']})", f"Captured ({prog['captured']})"],
            horizontal=True,
        )

        filtered_products = products
        if "Missing Photo" in filter_opt:
            filtered_products = [p for p in products if not p.get("image_path") or not Path(p["image_path"]).exists()]
        elif "Captured" in filter_opt:
            filtered_products = [p for p in products if p.get("image_path") and Path(p["image_path"]).exists()]

        st.markdown("---")

        # Product cards with direct camera integration
        for idx, p in enumerate(filtered_products):
            has_photo = bool(p.get("image_path") and Path(p["image_path"]).exists())
            status_badge = '<span class="badge-captured">🟢 CAPTURED</span>' if has_photo else '<span class="badge-missing">🔴 NOT CAPTURED</span>'

            with st.container():
                st.markdown(f"**#{p['product_order']+1} — {p['product_name']}** &nbsp; {status_badge}", unsafe_allow_html=True)
                c_info, c_preview, c_actions = st.columns([3, 2, 3])

                with c_info:
                    st.write(f"**Brand:** {p.get('brand') or 'N/A'}")
                    st.write(f"**Price:** {p.get('promo_price') or 'N/A'}")
                    if p.get("sku"):
                        st.write(f"**SKU:** `{p['sku']}`")

                with c_preview:
                    if has_photo:
                        st.image(p["image_path"], width=140, caption="Captured Photo")
                    else:
                        st.info("No photo captured yet.")

                with c_actions:
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if not has_photo:
                            if st.button("📸 Take Photo", key=f"btn_cam_{p['id']}", type="primary"):
                                st.session_state["active_camera_id"] = p["id"]
                                st.session_state["active_upload_id"] = None
                                st.rerun()
                        else:
                            if st.button("📸 Retake Photo", key=f"btn_retake_{p['id']}"):
                                st.session_state["active_camera_id"] = p["id"]
                                st.session_state["active_upload_id"] = None
                                st.rerun()

                    with btn_col2:
                        if st.button("📁 Upload File", key=f"btn_up_{p['id']}"):
                            st.session_state["active_upload_id"] = p["id"]
                            st.session_state["active_camera_id"] = None
                            st.rerun()

                    if has_photo:
                        if st.button("🗑️ Delete Photo", key=f"btn_del_{p['id']}"):
                            ReportManager.remove_product_photo(curr_id, p["id"])
                            st.success(f"Photo deleted for {p['product_name']}.")
                            st.rerun()

                # Active Camera Capture Box for this product
                if st.session_state.get("active_camera_id") == p["id"]:
                    st.markdown(
                        f"""
                        <div class="camera-box">
                            <strong>📷 Live Camera Viewfinder: {p['product_name']}</strong><br>
                            <small>Allow browser camera permission. On smartphones, point at the promotional display on the shelf.</small>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    cam_image = st.camera_input(
                        label=f"Take photo for #{p['product_order']+1}: {p['product_name']}",
                        key=f"cam_input_{p['id']}",
                        help="Click 'Take Photo' to snap the frame.",
                    )

                    if cam_image is not None:
                        st.image(cam_image, width=200, caption="Preview Snapped Photo")
                        save_col, cancel_col = st.columns(2)
                        with save_col:
                            if st.button("✅ Use & Save Photo", key=f"confirm_save_{p['id']}", type="primary"):
                                ReportManager.attach_captured_photo(
                                    report_id=curr_id,
                                    product_id=p["id"],
                                    file_bytes=cam_image.getvalue(),
                                    filename=f"camera_{p['id']}.jpg",
                                )
                                st.session_state["active_camera_id"] = None
                                st.success("Photo saved and associated successfully!")
                                st.rerun()
                        with cancel_col:
                            if st.button("🔄 Discard & Retake", key=f"retake_cam_{p['id']}"):
                                st.rerun()

                    if st.button("❌ Close Camera", key=f"close_cam_{p['id']}"):
                        st.session_state["active_camera_id"] = None
                        st.rerun()

                # Active Upload Box for this product
                if st.session_state.get("active_upload_id") == p["id"]:
                    st.markdown(f"**Upload Image File for: {p['product_name']}**")
                    up_single = st.file_uploader(
                        "Choose image file",
                        type=["jpg", "jpeg", "png", "webp"],
                        key=f"single_file_{p['id']}",
                    )
                    if up_single is not None:
                        if st.button("✅ Save Uploaded Image", key=f"save_up_{p['id']}", type="primary"):
                            ReportManager.attach_captured_photo(
                                report_id=curr_id,
                                product_id=p["id"],
                                file_bytes=up_single.getvalue(),
                                filename=up_single.name,
                            )
                            st.session_state["active_upload_id"] = None
                            st.success("Uploaded photo associated successfully!")
                            st.rerun()

                    if st.button("❌ Cancel Upload", key=f"close_up_{p['id']}"):
                        st.session_state["active_upload_id"] = None
                        st.rerun()

                st.markdown("---")

        # Step 5 & 6: Generation & Download
        st.markdown('<div class="step-header">STEP 5: Generate PowerPoint Presentation</div>', unsafe_allow_html=True)

        if prog["all_captured"]:
            st.success(f"🎉 Great job! All {prog['total']} products have captured photos. Ready to generate presentation.")
        else:
            missing_sample = ", ".join(prog["missing_products"][:3])
            st.warning(
                f"⚠️ Note: **{prog['missing']} of {prog['total']} products** do not have photos yet (e.g. {missing_sample}...). "
                "You can still generate the presentation now — the uncaptured slots will remain clean in the report."
            )

        if st.button("📊 Generate PowerPoint Report", type="primary", use_container_width=True):
            with st.spinner("Generating PowerPoint using original REOT template and captured photos..."):
                try:
                    ppt_path = ReportManager.generate_powerpoint_report(curr_id)
                    st.session_state["generated_pptx_path"] = str(ppt_path)
                    st.success(f"Report generated successfully: **{ppt_path.name}**")
                except Exception as e:
                    st.error(f"Error generating presentation: {e}")

        gen_path = st.session_state.get("generated_pptx_path")
        if gen_path and Path(gen_path).exists():
            st.markdown('<div class="step-header">STEP 6: Download Completed Report</div>', unsafe_allow_html=True)
            with open(gen_path, "rb") as f:
                pptx_data = f.read()
            st.download_button(
                label=f"📥 Download {Path(gen_path).name}",
                data=pptx_data,
                file_name=Path(gen_path).name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
                use_container_width=True,
            )


def view_product_review():
    """Dedicated product review with camera retake support."""
    st.markdown('<div class="main-title">Product Data Review</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Review product names, prices, or take/retake product photos using your camera.</div>',
        unsafe_allow_html=True,
    )

    reports = list_reports()
    if not reports:
        st.info("No reports created yet.")
        return

    report_options = {f"#{r['id']} - {r['week_name']} ({r['reporting_period']})": r["id"] for r in reports}
    selected_label = st.selectbox("Select Report to Review", list(report_options.keys()))
    report_id = report_options[selected_label]

    products = get_products_by_report(report_id)
    prog = ReportManager.get_capture_progress(report_id)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Products", prog["total"])
    c2.metric("Photos Captured", f"{prog['captured']} / {prog['total']}")
    c3.metric("Missing Photos", prog["missing"])

    filter_choice = st.radio("Filter Products", ["All", "Missing Photos", "Captured Photos"], horizontal=True)
    filtered = products
    if filter_choice == "Missing Photos":
        filtered = [p for p in products if not p.get("image_path") or not Path(p["image_path"]).exists()]
    elif filter_choice == "Captured Photos":
        filtered = [p for p in products if p.get("image_path") and Path(p["image_path"]).exists()]

    st.markdown(f"**Showing {len(filtered)} products**")

    for p in filtered:
        has_photo = bool(p.get("image_path") and Path(p["image_path"]).exists())
        with st.container():
            col_order, col_data, col_img, col_act = st.columns([1, 4, 2, 3])
            with col_order:
                st.markdown(f"### #{p['product_order']+1}")
                st.caption(f"ID: {p['id']}")
            with col_data:
                e_name = st.text_input("Product Name", value=p["product_name"], key=f"rev_name_{p['id']}")
                e_price = st.text_input("Price", value=p["promo_price"] or "", key=f"rev_price_{p['id']}")
                if st.button("Save Text", key=f"rev_save_txt_{p['id']}"):
                    update_product(p["id"], {"product_name": e_name, "promo_price": e_price})
                    st.success("Updated text!")
                    st.rerun()

            with col_img:
                if has_photo:
                    st.image(p["image_path"], width=130, caption=p.get("matched_filename"))
                else:
                    st.warning("No photo")

            with col_act:
                cam_pic = st.camera_input(f"Camera #{p['product_order']+1}", key=f"rev_cam_{p['id']}")
                if cam_pic:
                    if st.button("✅ Save Camera Photo", key=f"rev_save_cam_{p['id']}", type="primary"):
                        ReportManager.attach_captured_photo(report_id, p["id"], cam_pic.getvalue())
                        st.success("Saved!")
                        st.rerun()

                if has_photo:
                    if st.button("🗑️ Delete Photo", key=f"rev_del_{p['id']}"):
                        ReportManager.remove_product_photo(report_id, p["id"])
                        st.rerun()

            st.markdown("---")

    if st.button("📊 Re-Generate PowerPoint with Updated Data", type="primary", use_container_width=True):
        with st.spinner("Re-generating PowerPoint presentation..."):
            out = ReportManager.generate_powerpoint_report(report_id)
            st.success(f"Generated: {out.name}")
            with open(out, "rb") as f:
                st.download_button(
                    label=f"📥 Download {out.name}",
                    data=f.read(),
                    file_name=out.name,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    type="primary",
                )


def view_template_management():
    """Template inspection and management."""
    st.markdown('<div class="main-title">Template Management</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Inspect PowerPoint slide layouts, configure placeholders, or upload a new permanent template.</div>',
        unsafe_allow_html=True,
    )

    active_tmpl = get_active_template()
    templates = list_templates()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Active Template Details")
        if active_tmpl:
            tmpl_path = Path(active_tmpl["file_path"])
            st.write(f"**Name:** {active_tmpl['template_name']}")
            st.write(f"**File Location:** `{active_tmpl['file_path']}`")
            st.write(f"**Config Location:** `{active_tmpl['config_path']}`")
            st.write(f"**Uploaded At:** {active_tmpl['uploaded_at']}")

            if tmpl_path.exists():
                inspection = TemplateManager.inspect_template(tmpl_path)
                st.markdown(
                    f"**Dimensions:** {inspection['slide_width_inches']} × {inspection['slide_height_inches']} inches | **Total Slides:** {inspection['total_slides']}"
                )
                for slide in inspection["slides"]:
                    st.markdown(f"**Slide {slide['slide_index']+1}** ({slide['slide_layout_name']})")
                    if slide.get("has_product_table"):
                        t_info = slide.get("table_details")
                        st.success(
                            f"Identified Product Slide Layout: Table with {t_info['rows']} rows × {t_info['cols']} columns ({t_info['foto_cells']} image cells, {t_info['nama_cells']} product name cells)"
                        )
                    with st.expander(f"View Slide {slide['slide_index']+1} Shapes ({len(slide['shapes'])} elements)"):
                        st.json(slide["shapes"])
        else:
            st.warning("No template is currently active.")

    with col2:
        st.markdown("### Upload New Template")
        new_name = st.text_input("New Template Name", placeholder="e.g. GS Retail 2026 Template")
        new_file = st.file_uploader("Upload PPTX Template", type=["pptx"])
        if st.button("Upload and Set Active", type="primary") and new_file:
            temp_path = BASE_DIR / "uploads" / new_file.name
            with open(temp_path, "wb") as f:
                f.write(new_file.getvalue())

            new_id = TemplateManager.register_new_template(temp_path, new_name or new_file.name)
            st.success(f"New template registered and activated! (ID: {new_id})")
            st.rerun()

        st.markdown("---")
        st.markdown("### Available Templates")
        for t in templates:
            st.write(f"**#{t['id']} {t['template_name']}** {'*(Active)*' if t['is_active'] else ''}")
            if not t["is_active"]:
                if st.button(f"Activate #{t['id']}", key=f"act_{t['id']}"):
                    set_active_template(t["id"])
                    st.success(f"Activated template #{t['id']}")
                    st.rerun()


def view_report_history():
    """Historical archive of all generated reports with downloads and deletion."""
    st.markdown('<div class="main-title">Report History</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Browse, download, or manage previously generated weekly REOT reports.</div>',
        unsafe_allow_html=True,
    )

    reports = list_reports()
    if not reports:
        st.info("No reports generated yet.")
        return

    for r in reports:
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 4, 3, 2])
            with col1:
                st.markdown(f"### #{r['id']}")
            with col2:
                st.markdown(f"**{r['week_name']}**")
                st.write(f"Period: `{r['reporting_period']}` | Store: `{r['store_name']}`")
                st.caption(f"Created: {r['created_at']}")
            with col3:
                st.write(f"Products: **{r['product_count']}**")
                st.write(f"Status: `{r['status'].upper()}`")
                if r.get("pdf_filename"):
                    st.caption(f"PDF: {r['pdf_filename']}")
            with col4:
                ppt_p = r.get("generated_ppt_path")
                if ppt_p and Path(ppt_p).exists():
                    with open(ppt_p, "rb") as f:
                        st.download_button(
                            label="📥 Download PPTX",
                            data=f.read(),
                            file_name=Path(ppt_p).name,
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            key=f"dl_hist_{r['id']}",
                        )
                if st.button("🗑️ Delete", key=f"del_rep_{r['id']}"):
                    ReportManager.delete_weekly_report(r["id"])
                    st.success(f"Deleted report #{r['id']}")
                    st.rerun()

            st.markdown("---")


def view_settings():
    """Application settings, thresholds, and OCR diagnostics."""
    st.markdown('<div class="main-title">Settings & Diagnostics</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitle">Configure matching thresholds, OCR settings, and inspect system environment.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Fuzzy Matching Thresholds")
        high_t = st.slider("High Confidence Match (Auto-accept)", 80, 100, int(MATCH_HIGH_CONFIDENCE))
        sugg_t = st.slider("Suggested Match (Requires confirmation)", 50, 94, int(MATCH_SUGGESTED_CONFIDENCE))
        st.info(
            f"Scores >= {high_t}% are automatically matched.\nScores between {sugg_t}% and {high_t-1}% are flagged as suggested."
        )

    with col2:
        st.markdown("### OCR Configuration (Tesseract)")
        ocr_ok = OCRProcessor.is_ocr_available()
        if ocr_ok:
            st.success(f"Tesseract OCR is available at: `{TESSERACT_PATH}`")
        else:
            st.warning("Tesseract binary not detected. Scanned PDF fallback will use PyMuPDF only.")

        st.markdown("### System Paths")
        st.write(f"**Base Directory:** `{BASE_DIR}`")
        st.write(f"**Active Template:** `{DEFAULT_TEMPLATE_PATH}`")


def main():
    """Main routing controller."""
    selected_view = render_sidebar()

    if selected_view == "Dashboard":
        view_dashboard()
    elif selected_view == "Create Weekly Report":
        view_create_report()
    elif selected_view == "Product Review":
        view_product_review()
    elif selected_view == "Template Management":
        view_template_management()
    elif selected_view == "Report History":
        view_report_history()
    elif selected_view == "Settings":
        view_settings()


if __name__ == "__main__":
    main()
