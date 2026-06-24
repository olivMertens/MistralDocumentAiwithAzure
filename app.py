"""Streamlit UI for Mistral Document AI OCR extraction.

Launch: uv run streamlit run app.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from src.extract import ocr_pdf, OCRResult, MODELS, get_deployment_name, _pydantic_to_mistral_schema, ImageDescription

# ---------------------------------------------------------------------------
# Upload constraints (Microsoft Foundry limits)
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB = 30
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def _validate_upload(data: bytes, filename: str) -> str | None:
    """Return an error message if the uploaded file is invalid, else None."""
    if len(data) > MAX_FILE_SIZE_BYTES:
        return (
            f"File too large: {len(data) / (1024 * 1024):.1f} MB "
            f"(limit: {MAX_FILE_SIZE_MB} MB on Microsoft Foundry)"
        )
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext == 'pdf' and not data[:5].startswith(b'%PDF'):
        return "File does not appear to be a valid PDF (bad header)"
    return None


def _get_page_count(data: bytes) -> int | None:
    """Return page count of a PDF, or None on failure."""
    try:
        import fitz
        doc = fitz.open(stream=data, filetype='pdf')
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return None


def _parse_pages_input(text: str) -> list[int] | None:
    """Parse user page ranges like '1, 3, 5-8' into a 0-indexed list."""
    text = text.strip()
    if not text:
        return None
    try:
        pages: list[int] = []
        for part in text.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                s, e = part.split('-', 1)
                pages.extend(range(int(s.strip()) - 1, int(e.strip())))
            else:
                pages.append(int(part) - 1)
        return sorted(set(p for p in pages if p >= 0)) or None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Mistral Document AI - OCR Demo",
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_markdown_tables(md_text: str) -> list[pd.DataFrame]:
    """Parse Markdown pipe tables into DataFrames."""
    tables: list[pd.DataFrame] = []
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if (
            "|" in line
            and i + 1 < len(lines)
            and re.match(r"^[\|\s:\-]+$", lines[i + 1].strip())
        ):
            header = [c.strip() for c in line.strip("|").split("|")]
            rows: list[list[str]] = []
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                row = [c.strip() for c in lines[j].strip("|").split("|")]
                rows.append(row)
                j += 1
            if rows:
                df = pd.DataFrame(rows, columns=header[: len(rows[0])])
                tables.append(df)
            i = j
        else:
            i += 1
    return tables


def extract_sections(md_text: str) -> list[dict[str, str]]:
    """Split markdown into sections by headings for comprehension view."""
    sections: list[dict[str, str]] = []
    current_title = "Introduction"
    current_lines: list[str] = []
    for line in md_text.split("\n"):
        if line.startswith("#"):
            if current_lines:
                sections.append(
                    {"title": current_title, "content": "\n".join(current_lines)}
                )
            current_title = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append(
            {"title": current_title, "content": "\n".join(current_lines)}
        )
    return sections


def compute_doc_stats(result: OCRResult) -> dict:
    """Compute document comprehension statistics."""
    tables = extract_markdown_tables(result.markdown)
    sections = extract_sections(result.markdown)
    words = len(result.markdown.split())
    lines = result.markdown.count("\n") + 1
    has_headers = bool(re.search(r"^#{1,6}\s", result.markdown, re.MULTILINE))
    has_lists = bool(re.search(r"^[\s]*[-*]\s", result.markdown, re.MULTILINE))
    has_numbers = bool(re.search(r"\d+[.,]\d+", result.markdown))

    return {
        "words": words,
        "lines": lines,
        "tables": len(tables),
        "sections": len(sections),
        "has_headers": has_headers,
        "has_lists": has_lists,
        "has_numbers": has_numbers,
        "avg_section_len": words // max(len(sections), 1),
    }


def run_async(coro):
    """Run async coroutine from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("Configuration")

endpoint = st.sidebar.text_input(
    "Endpoint",
    value=os.getenv("MISTRAL_ENDPOINT", ""),
    type="default",
    help="Microsoft Foundry endpoint URL",
)

# Model selection
model_options = {k: v["label"] + " - " + v["description"] for k, v in MODELS.items()}
model_key = st.sidebar.radio(
    "Model version",
    options=list(MODELS.keys()),
    format_func=lambda k: MODELS[k]["label"],
    help="OCR 4.0 and v25.12 add table_format, header/footer extraction",
)
resolved_deployment = get_deployment_name(model_key)
st.sidebar.caption(f"Deployment: `{resolved_deployment}`")

api_key = st.sidebar.text_input(
    "API Key (optional)",
    value=os.getenv("AZURE_AI_KEY", ""),
    type="password",
    help="Leave empty to use Azure AD / DefaultAzureCredential",
)
include_images = st.sidebar.checkbox("Include image extraction", value=True)

# Advanced feature controls (v25.12 / OCR 4.0)
st.sidebar.markdown("---")
st.sidebar.markdown("### Advanced Features")
supports_advanced = model_key in ("2512", "ocr4")
table_format = st.sidebar.selectbox(
    "Table format",
    options=["(none)", "markdown", "html"],
    disabled=not supports_advanced,
    help=(
        "Controls how tables are returned in the API response (v25.12 / OCR 4.0).\n\n"
        "- **(none)**: tables are embedded inline in the page markdown only.\n"
        "- **markdown**: tables are also returned as separate entries in `pages[].tables[]` "
        "with a `markdown` key — easier for programmatic extraction.\n"
        "- **html**: same, but with an `html` key containing `<table>` elements — "
        "preserves `colspan`, `rowspan`, and merged cells better than markdown."
    ),
)
table_format_val = None if table_format == "(none)" else table_format
extract_header = st.sidebar.checkbox(
    "Extract headers",
    disabled=not supports_advanced,
    help=(
        "Extract repeated header text from the top of each page "
        "(e.g. document title, chapter name). Returned in `pages[].header`."
    ),
)
extract_footer = st.sidebar.checkbox(
    "Extract footers",
    disabled=not supports_advanced,
    help=(
        "Extract repeated footer text from the bottom of each page "
        "(e.g. page numbers, disclaimers). Returned in `pages[].footer`."
    ),
)
pages_input = st.sidebar.text_input(
    "Pages (e.g. 1, 3, 5-8)",
    disabled=not supports_advanced,
    help=(
        "Select specific pages to extract (1-indexed, comma-separated, ranges allowed). "
        "Leave empty to process all pages. Useful for large documents where you only "
        "need certain sections. v25.12 / OCR 4.0."
    ),
)
image_limit = st.sidebar.number_input(
    "Image limit",
    min_value=0,
    value=0,
    disabled=not supports_advanced,
    help=(
        "Maximum number of images to return across all pages. "
        "Set to 0 for unlimited. Useful to reduce response size "
        "when you only need text/tables. v25.12 / OCR 4.0."
    ),
)
if model_key == "ocr4":
    st.sidebar.caption(
        "\u2728 OCR 4.0 adds paragraph bounding boxes, block classification, "
        "and inline confidence scores."
    )

# Annotation controls
st.sidebar.markdown("---")
st.sidebar.markdown("### Annotations")
st.sidebar.caption(
    "Annotations use JSON Schema to extract structured data. "
    "Limited to the first **8 pages** of the document."
)
enable_bbox = st.sidebar.checkbox(
    "BBox annotations (per-image)",
    help=(
        "Classify each image found in the document using a JSON Schema. "
        "Each image in `pages[].images[]` will include structured fields "
        "(image_type, summary, details, is_relevant) alongside the base64 data.\n\n"
        "Use cases: chart classification, logo detection, figure summarisation."
    ),
)
enable_doc_annotation = st.sidebar.checkbox(
    "Document annotation (whole-doc)",
    help=(
        "Extract a single structured summary for the entire document using a JSON Schema. "
        "Mistral reads all content (text + images) and returns one structured object "
        "in the `document_annotation` field.\n\n"
        "Use cases: document classification, entity extraction, executive summaries, "
        "invoice field extraction, compliance tagging."
    ),
)
doc_annotation_prompt = ""
if enable_doc_annotation:
    doc_annotation_prompt = st.sidebar.text_area(
        "Document annotation prompt",
        value="Summarize this document with key topics and entities.",
        height=80,
        help="Optional prompt guiding the document-level annotation. Describes what you want extracted.",
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Deploy models:** run `scripts/deploy_all.ps1` or `.sh`\n\n"
    "**Auth:** API key or `az login` for DefaultAzureCredential"
)

# Sidebar: extraction history
st.sidebar.markdown("---")
st.sidebar.markdown("### Extraction History")
extraction_dir = Path("extraction")
if extraction_dir.exists():
    saved = sorted(extraction_dir.glob("*_meta.json"), reverse=True)
    if saved:
        for meta_file in saved[:10]:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            src = meta.get("source", meta_file.stem)
            pages = meta.get("pages", "?")
            tbls = meta.get("tables", meta.get("tables_found", 0))
            st.sidebar.caption(f"{src} - {pages}p, {tbls} tables")
    else:
        st.sidebar.caption("No extractions saved yet.")
else:
    st.sidebar.caption("No extractions saved yet.")

# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------
st.title("Mistral Document AI - OCR Extraction")
st.markdown(
    f"Upload a PDF or pick one from `data/` to extract text, tables, and images "
    f"using **Mistral Document AI {MODELS[model_key]['label']}** on Microsoft Foundry."
)

# ---------------------------------------------------------------------------
# Model Comparison & Limits info section
# ---------------------------------------------------------------------------
with st.expander("\u2139\ufe0f  Model Comparison & API Limits", expanded=False):
    st.markdown("### v25.12 vs OCR 4.0 — Feature Comparison")
    st.markdown(
        """
| Feature | v25.12 (`mistral-document-ai-2512`) | OCR 4.0 (`mistral-ocr-4-0`) |
|---------|----------------------------|----------------------------|
| **OCR engine** | `mistral-ocr-2512` + `mistral-small-2506` | `mistral-ocr-4-0` (+ Mistral Medium 3.5 annotations) |
| **Status** | GA | Preview |
| **Markdown output** | \u2705 | \u2705 |
| **Image extraction (bbox)** | \u2705 | \u2705 |
| **Paragraph bounding boxes** | \u274c | \u2705 \u2014 per-paragraph layout coordinates |
| **Block classification** | \u274c | \u2705 \u2014 title, header, footer, code, table, equation, paragraph, list, signature, image, caption, references |
| **Inline confidence scores** | \u274c | \u2705 \u2014 per-page / per-word confidence |
| **Hyperlink detection** | \u2705 | \u2705 |
| **`table_format`** | `"markdown"` / `"html"` | `"markdown"` / `"markdown-tables"` / `"html"` (colspan/rowspan) |
| **`extract_header` / `extract_footer`** | \u2705 | \u2705 |
| **`pages` selection** | \u2705 | \u2705 |
| **`image_limit`** | \u2705 | \u2705 |
| **BBox / Document annotations** | JSON Schema structured output | JSON Schema structured output |
| **Streaming API** | \u274c | \u2705 \u2014 redesigned, reduced time-to-first-token |
| **Multilingual accuracy** | 99%+ across 25+ languages | **170 languages** |
| **Supported formats** | PDF, PNG, JPEG, AVIF, PPTX, DOCX | PDF, PNG, JPEG, AVIF, PPTX, DOCX |
| **Deployment SKU** | GlobalStandard | GlobalStandard / DataZoneStandard |
| **Pricing (Global Standard)** | per Foundry pricing | $4 / 1K pages (OCR) \u00b7 $5 / 1K pages (OCR + annotations) |
"""
    )

    st.markdown("### API Limits (Microsoft Foundry)")
    st.markdown(
        """
| Limit | Value | Notes |
|-------|-------|-------|
| **Max file size** | **30 MB** per request | Applies to both v25.12 and OCR 4.0 on Microsoft Foundry |
| **Max pages per request** | **30 pages** | Documents >30 pages are auto-chunked by this app |
| **Annotations page limit** | **8 pages** | `document_annotation` limited to first 8 pages |
| **Supported formats** | PDF, PNG, JPEG, AVIF, PPTX, DOCX | Images: 1 page per request |

> **Large documents**: This app automatically splits PDFs over 30 pages into
> chunks and processes them sequentially, merging results transparently.
"""
    )

    st.markdown(
        "\n**Documentation:** "
        "[OCR Processor](https://docs.mistral.ai/capabilities/document_ai/basic_ocr) · "
        "[Annotations](https://docs.mistral.ai/capabilities/document_ai/annotations) · "
        "[API Reference](https://docs.mistral.ai/api/endpoint/ocr) · "
        "[Azure Model Card (OCR 4.0)](https://ai.azure.com/catalog/models/mistral-ocr-4-0) · "
        "[Azure Model Card (2512)](https://ai.azure.com/explore/models/mistral-document-ai-2512/version/1/registry/azureml-mistral)"
    )
    st.markdown("### Parameters Reference (v25.12 / OCR 4.0)")
    st.markdown(
        """
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `table_format` | `\"markdown\"` \\| `\"html\"` \\| `null` | `null` | Structured table output format |
| `extract_header` | `bool` | `false` | Extract repeated page headers into `pages[].header` |
| `extract_footer` | `bool` | `false` | Extract repeated page footers into `pages[].footer` |
| `pages` | `list[int]` | all | Select specific pages (0-indexed) |
| `image_limit` | `int` | unlimited | Max images to return |

**`table_format` behaviour:**
- **`null`** (default) \u2014 tables are only inline in the page markdown as pipe tables
- **`\"markdown\"`** \u2014 tables also appear in `pages[].tables[]` with a `markdown` key
- **`\"html\"`** \u2014 tables in `pages[].tables[]` with an `html` key (`<table>` element, preserves merged cells)

> In all cases, tables remain inline in `pages[].markdown`. The `table_format` parameter adds a *structured copy* for easier downstream parsing.
"""
    )

    st.markdown("### How Annotations Work")
    st.markdown(
        """
Annotations extract **structured data** from your document using JSON Schemas. Limited to the **first 8 pages**.

**BBox annotations** (`bbox_annotation_format`) \u2014 applied to **each image**:
- Classifies and describes every image found (charts, photos, logos, tables\u2026)
- Returns structured fields alongside the image base64 data
- Use cases: chart classification, logo detection, figure summarisation

**Document annotations** (`document_annotation_format` + `document_annotation_prompt`) \u2014 applied to the **whole document**:
- Reads all content (text + images) and returns one structured JSON object
- Use cases: document classification, entity extraction, invoice parsing, compliance tagging
- The optional *prompt* guides what Mistral should focus on

**How to use in this app:**
1. Enable \u201cBBox annotations\u201d and/or \u201cDocument annotation\u201d in the sidebar
2. Run an extraction
3. View results in the **Annotations** tab
"""
    )
# File selection
col1, col2 = st.columns([1, 1])

with col1:
    uploaded_file = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        help=f"PDF format — max {MAX_FILE_SIZE_MB} MB per file",
    )

with col2:
    data_dir = Path("data")
    local_pdfs = sorted(data_dir.glob("*.pdf")) if data_dir.exists() else []
    local_choice = st.selectbox(
        "Or select from data/",
        options=["(none)"] + [p.name for p in local_pdfs],
    )

# Determine which PDF to process
pdf_bytes: bytes | None = None
pdf_name = ""

if uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    pdf_name = uploaded_file.name
elif local_choice and local_choice != "(none)":
    pdf_path = data_dir / local_choice
    pdf_bytes = pdf_path.read_bytes()
    pdf_name = local_choice

# Validate and show file info
if pdf_bytes:
    validation_error = _validate_upload(pdf_bytes, pdf_name)
    if validation_error:
        st.error(f"\u274c {validation_error}")
        pdf_bytes = None
    else:
        size_mb = len(pdf_bytes) / (1024 * 1024)
        page_count = _get_page_count(pdf_bytes)
        info_parts = [f"**{pdf_name}**", f"{size_mb:.2f} MB"]
        if page_count is not None:
            info_parts.append(f"{page_count} page(s)")
            if page_count > 30:
                info_parts.append("\u26a1 auto-chunked (>30 pages)")
        if size_mb > MAX_FILE_SIZE_MB * 0.8:
            st.warning(
                f"\u26a0\ufe0f File is {size_mb:.1f} MB — approaching "
                f"the {MAX_FILE_SIZE_MB} MB limit"
            )
        st.info(" \u00b7 ".join(info_parts))

# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------
if pdf_bytes and endpoint:
    if st.button(
        "Extract with Mistral Document AI",
        type="primary",
        use_container_width=True,
    ):
        tmp_path = Path("data") / f"_tmp_{pdf_name}"
        tmp_path.parent.mkdir(exist_ok=True)
        tmp_path.write_bytes(pdf_bytes)

        progress_bar = st.progress(0.0, text="Preparing extraction\u2026")

        def _on_progress(pct: float, msg: str) -> None:
            progress_bar.progress(min(pct, 1.0), text=msg)

        try:
            progress_bar.progress(0.05, text="Validating document\u2026")

            # Build annotation params
            bbox_fmt = _pydantic_to_mistral_schema(ImageDescription) if enable_bbox else None
            doc_fmt = None
            if enable_doc_annotation:
                from pydantic import create_model as _cm
                _DocSummary = _cm("DocumentSummary", topics=(list[str], ...), entities=(list[str], ...), summary=(str, ...))
                doc_fmt = _pydantic_to_mistral_schema(_DocSummary)

            # Parse pages param (v25.12 / OCR 4.0)
            selected_pages = _parse_pages_input(pages_input) if supports_advanced else None

            progress_bar.progress(0.10, text=f"Sending to {MODELS[model_key]['label']}\u2026")

            result: OCRResult = run_async(
                ocr_pdf(
                    tmp_path,
                    endpoint=endpoint,
                    model_key=model_key,
                    api_key=api_key or None,
                    include_images=include_images,
                    table_format=table_format_val if supports_advanced else None,
                    extract_header=extract_header if supports_advanced else False,
                    extract_footer=extract_footer if supports_advanced else False,
                    pages=selected_pages,
                    image_limit=image_limit if supports_advanced and image_limit > 0 else None,
                    bbox_annotation_format=bbox_fmt,
                    document_annotation_format=doc_fmt,
                    document_annotation_prompt=doc_annotation_prompt or None,
                    progress_callback=_on_progress,
                )
            )

            progress_bar.progress(1.0, text="\u2705 Extraction complete!")
            st.session_state["result"] = result
            st.session_state["pdf_name"] = pdf_name
            st.session_state["pdf_bytes"] = pdf_bytes
            st.session_state["model_key"] = model_key
            st.session_state["table_format"] = table_format_val if supports_advanced else None
        except Exception as exc:
            progress_bar.progress(1.0, text="\u274c Extraction failed")
            st.error(f"OCR extraction failed: {exc}")
        finally:
            tmp_path.unlink(missing_ok=True)

elif not endpoint:
    st.warning("Set your MISTRAL_ENDPOINT in the sidebar or .env file.")

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
if "result" in st.session_state:
    result: OCRResult = st.session_state["result"]
    pdf_name = st.session_state["pdf_name"]
    pdf_bytes_display: bytes = st.session_state.get("pdf_bytes", b"")

    # ---- Metrics bar ----
    st.markdown("---")
    stats = compute_doc_stats(result)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Pages", len(result.pages))
    m2.metric("Words", f"{stats['words']:,}")
    m3.metric("Tables", stats["tables"])
    m4.metric("Sections", stats["sections"])
    m5.metric("Images", len(result.images))
    m6.metric("Time", f"{result.elapsed_ms:.0f} ms")

    if result.usage:
        st.caption(f"Token usage: {result.usage}")

    # ---- Tabs ----
    tab_overview, tab_md, tab_tables, tab_images, tab_pages, tab_annotations, tab_raw = st.tabs(
        [
            "Document Overview",
            "Full Markdown",
            "Tables",
            "Images",
            "Per Page",
            "Annotations",
            "Raw JSON",
        ]
    )

    # --- Document Overview tab ---
    with tab_overview:
        st.markdown("### Document Comprehension")
        st.markdown(
            "Side-by-side view of the original PDF and OCR-extracted content "
            "with structural analysis."
        )

        ov_left, ov_right = st.columns([1, 1])

        with ov_left:
            st.markdown("#### Original PDF")
            if pdf_bytes_display:
                b64_pdf = base64.b64encode(pdf_bytes_display).decode()
                pdf_iframe = (
                    f'<iframe src="data:application/pdf;base64,{b64_pdf}" '
                    f'width="100%" height="600" type="application/pdf"></iframe>'
                )
                st.markdown(pdf_iframe, unsafe_allow_html=True)
            else:
                st.caption("PDF preview not available.")

        with ov_right:
            st.markdown("#### Extracted Structure")

            # Structure indicators
            badges = []
            if stats["has_headers"]:
                badges.append("Headers")
            if stats["tables"] > 0:
                badges.append(f"{stats['tables']} Tables")
            if stats["has_lists"]:
                badges.append("Lists")
            if stats["has_numbers"]:
                badges.append("Numerical Data")
            if len(result.images) > 0:
                badges.append(f"{len(result.images)} Images")
            st.markdown("**Detected elements:** " + " | ".join(badges))

            # Section breakdown
            sections = extract_sections(result.markdown)
            for sec in sections:
                word_count = len(sec["content"].split())
                tbl_count = len(extract_markdown_tables(sec["content"]))
                label = f"{sec['title']} ({word_count}w"
                if tbl_count:
                    label += f", {tbl_count} table(s)"
                label += ")"
                with st.expander(label, expanded=False):
                    st.markdown(sec["content"][:2000])
                    if len(sec["content"]) > 2000:
                        st.caption("... (content truncated in preview)")

    # --- Full Markdown tab ---
    with tab_md:
        st.markdown("### Extracted Markdown")

        view_mode = st.radio(
            "View mode",
            ["Rendered", "Raw source"],
            horizontal=True,
            key="md_view",
        )

        if view_mode == "Rendered":
            st.markdown(result.markdown)
        else:
            st.code(result.markdown, language="markdown")

        st.download_button(
            "Download .md",
            data=result.markdown,
            file_name=f"{Path(pdf_name).stem}.md",
            mime="text/markdown",
        )

    # --- Tables tab ---
    with tab_tables:
        # Use structured tables from response if available
        used_format = st.session_state.get("table_format")
        structured_tables = []
        for p in result.pages:
            structured_tables.extend(p.tables)

        if structured_tables:
            fmt_label = f" (`table_format={used_format}`)" if used_format else ""
            st.markdown(f"### {len(structured_tables)} structured table(s) from API{fmt_label}")
            for idx, tbl in enumerate(structured_tables):
                st.markdown(f"**Table {idx + 1}**")
                if isinstance(tbl, dict) and "html" in tbl:
                    st.markdown(tbl["html"], unsafe_allow_html=True)
                    st.download_button(
                        f"Download Table {idx + 1} (HTML)",
                        data=tbl["html"],
                        file_name=f"{Path(pdf_name).stem}_api_table_{idx + 1}.html",
                        mime="text/html",
                        key=f"api_html_{idx}",
                    )
                elif isinstance(tbl, dict) and "markdown" in tbl:
                    st.markdown(tbl["markdown"])
                    st.download_button(
                        f"Download Table {idx + 1} (Markdown)",
                        data=tbl["markdown"],
                        file_name=f"{Path(pdf_name).stem}_api_table_{idx + 1}.md",
                        mime="text/markdown",
                        key=f"api_md_{idx}",
                    )
                else:
                    st.json(tbl)
            st.markdown("---")
            st.markdown("#### Also parsed from inline markdown:")

        tables = extract_markdown_tables(result.markdown)
        if tables:
            st.markdown(f"### {len(tables)} table(s) detected")

            # Summary of all tables
            summary_data = []
            for idx, df in enumerate(tables):
                summary_data.append(
                    {
                        "Table": idx + 1,
                        "Rows": df.shape[0],
                        "Columns": df.shape[1],
                        "Column Names": ", ".join(df.columns[:5])
                        + ("..." if df.shape[1] > 5 else ""),
                    }
                )
            st.dataframe(
                pd.DataFrame(summary_data),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")

            # Individual tables with search/filter
            for idx, df in enumerate(tables):
                st.markdown(
                    f"**Table {idx + 1}** ({df.shape[0]} rows x {df.shape[1]} cols)"
                )

                search_term = st.text_input(
                    f"Filter Table {idx + 1}",
                    key=f"filter_{idx}",
                    placeholder="Type to filter rows...",
                )

                display_df = df
                if search_term:
                    mask = df.apply(
                        lambda row: row.astype(str)
                        .str.contains(search_term, case=False, na=False)
                        .any(),
                        axis=1,
                    )
                    display_df = df[mask]

                st.dataframe(display_df, use_container_width=True, hide_index=True)

                csv = df.to_csv(index=False)
                st.download_button(
                    f"Download Table {idx + 1} as CSV",
                    data=csv,
                    file_name=f"{Path(pdf_name).stem}_table_{idx + 1}.csv",
                    mime="text/csv",
                    key=f"csv_{idx}",
                )
                st.markdown("---")
        else:
            st.info("No tables detected in the extracted markdown.")

    # --- Images tab ---
    with tab_images:
        if result.images:
            st.markdown(f"### {len(result.images)} image(s) extracted")
            cols_per_row = 2
            for i in range(0, len(result.images), cols_per_row):
                img_cols = st.columns(cols_per_row)
                for col_idx, img in enumerate(
                    result.images[i : i + cols_per_row]
                ):
                    img_id = img.get("id", "unknown")
                    page = img.get("page_index", "?")
                    b64 = img.get("image_base64") or img.get("base64", "")

                    with img_cols[col_idx]:
                        st.markdown(f"**{img_id}** (page {page})")
                        if b64:
                            st.image(
                                base64.b64decode(b64),
                                caption=img_id,
                                use_container_width=True,
                            )
                        else:
                            st.caption("No base64 image data available.")
                        meta_keys = {
                            k: v
                            for k, v in img.items()
                            if k not in ("image_base64", "base64")
                        }
                        st.json(meta_keys)
        else:
            st.info(
                "No images extracted. Enable 'Include image extraction' in sidebar."
            )

    # --- Per Page tab ---
    with tab_pages:
        st.markdown("### Per-page breakdown")

        # Headers & Footers summary (v25.12 / OCR 4.0)
        has_headers = any(p.header for p in result.pages)
        has_footers = any(p.footer for p in result.pages)
        if has_headers or has_footers:
            with st.expander("\U0001f4cb Headers & Footers", expanded=True):
                hf_data = []
                for p in result.pages:
                    hf_data.append({
                        "Page": p.page_index + 1,
                        "Header": p.header or "\u2014",
                        "Footer": p.footer or "\u2014",
                    })
                st.dataframe(
                    pd.DataFrame(hf_data),
                    use_container_width=True,
                    hide_index=True,
                )

        page_data = []
        for p in result.pages:
            page_tables = extract_markdown_tables(p.markdown)
            row: dict = {
                "Page": p.page_index + 1,
                "Characters": len(p.markdown),
                "Words": len(p.markdown.split()),
                "Tables": len(page_tables) + len(p.tables),
                "Images": len(p.images),
                "Preview": p.markdown[:120].replace("\n", " "),
            }
            page_data.append(row)
        st.dataframe(
            pd.DataFrame(page_data), use_container_width=True, hide_index=True
        )

        # Page selector with rendered markdown
        if result.pages:
            page_idx = st.selectbox(
                "View page markdown",
                options=range(len(result.pages)),
                format_func=lambda x: f"Page {x + 1}",
            )
            selected_page = result.pages[page_idx]
            st.markdown("---")
            if selected_page.header:
                st.caption(f"**Header:** {selected_page.header}")
            st.markdown(selected_page.markdown)
            if selected_page.footer:
                st.caption(f"**Footer:** {selected_page.footer}")

    # --- Annotations tab ---
    with tab_annotations:
        st.markdown("### Annotations")

        if result.document_annotation:
            st.markdown("#### Document-level Annotation")
            if isinstance(result.document_annotation, str):
                try:
                    st.json(json.loads(result.document_annotation))
                except json.JSONDecodeError:
                    st.code(result.document_annotation)
            else:
                st.json(result.document_annotation)
        else:
            st.caption("No document annotation. Enable it in the sidebar.")

        # BBox annotations from images
        bbox_images = [
            img for img in result.images
            if any(k not in ("id", "image_base64", "base64", "page_index") for k in img)
        ]
        if bbox_images:
            st.markdown("#### BBox Image Annotations")
            for img in bbox_images:
                img_id = img.get("id", "unknown")
                st.markdown(f"**{img_id}** (page {img.get('page_index', '?')})")
                meta_keys = {k: v for k, v in img.items() if k not in ("image_base64", "base64")}
                st.json(meta_keys)
        elif not result.document_annotation:
            st.info("Enable bbox or document annotations in the sidebar to see results here.")

    # --- Raw JSON tab ---
    with tab_raw:
        st.markdown("### Raw OCR result (JSON)")
        raw = result.model_dump()
        raw["source"] = pdf_name
        st.json(raw)

        st.download_button(
            "Download full JSON",
            data=json.dumps(raw, indent=2, ensure_ascii=False),
            file_name=f"{Path(pdf_name).stem}_ocr.json",
            mime="application/json",
        )

    # ---- Save to extraction/ ----
    st.markdown("---")
    save_cols = st.columns([1, 1])
    with save_cols[0]:
        if st.button("Save to extraction/ folder", use_container_width=True):
            out_dir = Path("extraction")
            out_dir.mkdir(exist_ok=True)
            stem = Path(pdf_name).stem

            (out_dir / f"{stem}.md").write_text(
                result.markdown, encoding="utf-8"
            )

            tables = extract_markdown_tables(result.markdown)
            for i, df in enumerate(tables):
                df.to_csv(out_dir / f"{stem}_table_{i + 1}.csv", index=False)

            meta = {
                "source": pdf_name,
                "pages": len(result.pages),
                "images": len(result.images),
                "tables": len(tables),
                "chars": len(result.markdown),
                "words": len(result.markdown.split()),
                "sections": len(extract_sections(result.markdown)),
                "usage": result.usage,
                "elapsed_ms": round(result.elapsed_ms, 1),
            }
            (out_dir / f"{stem}_meta.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            # Save full JSON
            full_json = result.model_dump()
            full_json["source"] = pdf_name
            (out_dir / f"{stem}_full.json").write_text(
                json.dumps(full_json, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            st.success(
                f"Saved to extraction/{stem}.md + metadata + "
                f"{len(tables)} CSV(s) + full JSON"
            )
