# Weekly REOT Generator
## Automated PDF-to-PowerPoint Report Generation System with Direct Camera Capture

An enterprise-grade automation system and interactive dashboard designed to streamline the weekly production of promotional REOT (Retail Implementation) PowerPoint presentations. 

The application extracts promotional product names, variants, pack sizes, and prices from weekly PDF catalogs, allows store staff to **take product photos directly using their smartphone camera or desktop webcam**, automatically associates each photo directly with its corresponding product, and populates the permanent presentation template with 100% design fidelity.

---

## 📌 Key Capabilities

- **Direct In-App Camera Integration**:
  - Store staff and users can take photos directly inside the web application via browser camera access (`getUserMedia`).
  - Supports smartphone rear/main cameras and desktop webcams over HTTPS or localhost.
  - Interactive viewfinder with live preview, "Retake", and "Use Photo" confirmation.
  - Alternative file uploader per product for devices without a camera.
  - Direct 1-to-1 association with product IDs, completely eliminating manual image matching.

- **Real-Time Capture Progress Tracking**:
  - Live progress bar showing captured count (e.g., `Photos Captured: 15 / 27 Products`).
  - Quick filter buttons: `All Products`, `Missing Photos`, and `Captured Photos`.
  - Clear visual status badges (`🟢 CAPTURED` vs `🔴 NOT CAPTURED`).

- **Permanent PowerPoint Template Management**:
  - Reuses your original corporate REOT template (`Template Implementasi GS Retail.pptx`) permanently.
  - Preserves 100% of native PowerPoint formatting (typography, colors, borders, dimensions, alignments, and vector artwork).
  - Dynamically calculates the required number of slides based on product count (8 products per slide).

- **Intelligent PDF Product Extraction Engine**:
  - High-performance text parsing with **PyMuPDF (`fitz`)**.
  - Automatic fallback to **Tesseract OCR** for scanned documents or rasterized marketing flyers.
  - Automated bundle splitting (e.g. separating bundled promos like `AMIDIS Botol` + `ULTRA MILK` into individual product cards).
  - Normalizes product names, packaging units (`ml`, `l`, `kg`, `g`, `pcs`, `box`, `rcg`, `karton`, `jerigen`), and detects brands.
  - Filters promotional disclaimers and marketing copy automatically.

- **Data Review & Manual Correction**:
  - Review and edit product names, pack sizes, SKUs, and promo prices in real-time.
  - Preview, retake, or delete photos for any product with a single click.
  - Add missing products or remove duplicates before generation.

- **Dynamic PowerPoint Generation**:
  - Deep XML slide duplication preserving exact table layouts, fonts (`The Jamsil 3 Regular`), and borders.
  - Non-distorting aspect-ratio-preserving image insertion.
  - Automatically renders the promotional PDF's first page into the Slide 2 flyer banner.
  - Produces valid, fully editable `.pptx` presentations.

---

## 🏗️ Project Architecture

```
weekly-reot-generator/
│
├── app.py                     # Streamlit Web Application with Camera Viewfinder
├── requirements.txt           # Python dependency specifications
├── README.md                  # Project documentation & instructions
├── conftest.py                # Pytest configuration
│
├── config/
│   ├── settings.py            # Global paths, limits, and thresholds
│   └── template_config.json   # Template placeholder & slot mapping
│
├── modules/
│   ├── pdf_extractor.py       # PDF parsing, block sorting, price association
│   ├── ocr_processor.py       # Tesseract OCR engine for scanned PDFs
│   ├── product_processor.py   # Product cleansing, bundling, and brand detection
│   ├── image_handler.py       # Camera photo saving, isolated storage, thumbnails
│   ├── image_matcher.py       # Tiered fuzzy matching (retained as alternative)
│   ├── template_manager.py    # PPTX template inspection and mapping
│   ├── ppt_generator.py       # PowerPoint slide cloner and layout engine
│   └── report_manager.py      # Camera capture coordinator & report lifecycle
│
├── database/
│   ├── db.py                  # SQLite CRUD operations & repository
│   └── schema.sql             # Relational database schema
│
├── templates/
│   └── reot_template.pptx     # Active permanent presentation template
│
├── sample_data/               # Reference files and sample test data
│   ├── Big Banner LSI 24-30 nov 2026 copy.pdf
│   ├── Template Implementasi GS Retail.pptx
│   └── sample_product_images.zip
│
├── uploads/
│   └── weekly_reports/        # Isolated uploads organized by report ID
│
├── outputs/
│   └── generated_reports/     # Generated PPTX presentations
│
├── utils/
│   ├── file_validator.py      # Extension, size, and Zip Slip validation
│   ├── text_normalizer.py     # Alphanumeric text and packaging normalization
│   └── helpers.py             # PDF-to-image renderer, directory utilities
│
└── tests/
    ├── test_camera_workflow.py # Tests for camera capture & product association
    ├── test_pdf_extractor.py  # Tests for PDF extraction & bundle splitting
    ├── test_image_matcher.py  # Tests for tiered image matching
    └── test_ppt_generator.py  # Tests for slide duplication & layouts
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.11+
- Tesseract OCR (installed via Homebrew on macOS: `brew install tesseract`)

### 1. Set Up Virtual Environment
```bash
cd weekly-reot-generator
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Verify with Automated Test Suite
Run the automated test suite covering extraction, camera association, and PowerPoint generation:
```bash
pytest tests/ -v
```
All 15 tests should pass.

---

## 🖥️ Running the Application

Launch the Streamlit web dashboard:
```bash
cd /Users/aurelliaaca/.gemini/antigravity/scratch/weekly-reot-generator
.venv/bin/streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 📸 Camera Workflow User Guide

1. **Navigate to "Create Weekly Report"**:
   - Enter the **Week Name** (e.g., `Week 48 November 2026`).
   - Enter or confirm the **Reporting Period** (e.g., `24 – 30 November 2026`).
   - Enter the **Store Name** (e.g., `LSI MERUYA`).
2. **Upload Promotional PDF**:
   - Drag and drop your weekly promotional flyer PDF (`Big Banner LSI 24-30 nov 2026 copy.pdf`).
3. **Extract Products**:
   - Click **⚡ Extract Products from PDF & Start Camera Workflow**.
   - The system automatically extracts all products and initializes the interactive capture checklist.
4. **Take Product Photos with Device Camera**:
   - For each product in the list:
     - Click **📸 Take Photo**.
     - Allow browser camera permission when prompted.
     - Aim at the product display on the shelf and click the capture button.
     - Review the preview and click **✅ Use & Save Photo**.
     - The product immediately updates with a green **🟢 CAPTURED** badge and thumbnail.
     - *(Alternative)*: If camera permission is unavailable, click **📁 Upload File** to select an existing photo.
     - To replace a photo, click **📸 Retake Photo**.
     - To remove a photo, click **🗑️ Delete Photo**.
5. **Check Progress**:
   - Watch the progress bar advance: `Photos Captured: X / 27 Products`.
   - Use the `Missing Photos` filter tab to quickly find remaining items.
6. **Generate & Download PowerPoint**:
   - Click **📊 Generate PowerPoint Report**.
   - The presentation is created with original formatting, flyer banner on Slide 2, and all product cards filled.
   - Click **📥 Download PPTX** to save your completed report.

---

## 🔒 Security & Data Isolation

- **Direct ID Binding**: Photos captured from a product card are deterministically associated with that specific product ID (`product_{id}.jpg`). Accidental cross-association is prevented.
- **Report Isolation**: Every weekly report has an isolated folder (`uploads/weekly_reports/report_<id>/`). Product photos never mix across different reporting weeks.
- **Template Protection**: The permanent PowerPoint template is read-only and never modified during report generation.
