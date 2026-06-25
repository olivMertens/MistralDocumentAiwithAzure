"""Streamlit UI for Mistral Document AI OCR extraction.

Launch: uv run streamlit run app.py
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import base64
import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from src.extract import ocr_pdf, OCRResult, get_deployment_name, _pydantic_to_mistral_schema, ImageDescription

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
    page_title="Compare Mistral Document AI — OCR 4.0 vs v25.12 on Azure",
    page_icon="📄",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Branding — Microsoft Azure (#0078D4) × Mistral AI flame (#FF6A13)
# ---------------------------------------------------------------------------
AZURE_BLUE = "#0078D4"
AZURE_LIGHT = "#50E6FF"
AZURE_DEEP = "#243A5E"
MISTRAL_ORANGE = "#FF6A13"
MISTRAL_AMBER = "#FFAF00"
MISTRAL_RED = "#E10500"

st.markdown(
    """
    <style>
    :root {
      --azure-blue: #0078D4; --azure-light: #50E6FF; --azure-deep: #243A5E;
      --mistral-orange: #FF6A13; --mistral-amber: #FFAF00; --mistral-red: #E10500;
    }
    /* ---- Hero header ---- */
    .brand-hero {
      position: relative; border-radius: 18px; padding: 1.6rem 1.9rem;
      margin: 0.1rem 0 1.1rem 0; overflow: hidden; color: #fff;
      background:
        radial-gradient(120% 150% at 0% 0%, rgba(0,120,212,0.18) 0%, rgba(0,120,212,0) 55%),
        radial-gradient(120% 150% at 100% 0%, rgba(255,106,19,0.20) 0%, rgba(255,106,19,0) 55%),
        linear-gradient(135deg, #0b2746 0%, #103a63 45%, #1d2f50 100%);
      box-shadow: 0 10px 30px rgba(16,42,80,0.25);
    }
    .brand-hero::after {
      content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 4px;
      background: linear-gradient(90deg,#50E6FF 0%,#0078D4 32%,#FF8205 70%,#E10500 100%);
    }
    .brand-eyebrow {
      font-size: 0.8rem; font-weight: 600; letter-spacing: 0.12em;
      text-transform: uppercase; color: #9bd0ff; margin-bottom: 0.35rem;
    }
    .brand-title { font-size: 2.0rem; font-weight: 800; line-height: 1.12; margin: 0 0 0.5rem 0; }
    .brand-title .accent {
      background: linear-gradient(90deg,#FFAF00,#FF6A13 55%,#E10500);
      -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .brand-sub { font-size: 0.98rem; color: #d7e6f5; margin: 0; max-width: 60rem; }
    .brand-chips { margin-top: 0.9rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .chip {
      display: inline-flex; align-items: center; gap: 0.45rem; font-size: 0.78rem;
      font-weight: 600; padding: 0.3rem 0.75rem; border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.25);
    }
    .chip-azure { background: rgba(0,120,212,0.22); color: #cfe9ff; }
    .chip-mistral { background: rgba(255,106,19,0.22); color: #ffd9b8; }
    .chip-dot { width: 8px; height: 8px; border-radius: 50%; }
    .chip-azure .chip-dot { background: #50E6FF; }
    .chip-mistral .chip-dot { background: #FF8205; }
    /* ---- Primary button: Azure→Mistral gradient ---- */
    .stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
      background: linear-gradient(90deg,#0078D4 0%,#1f6fc4 45%,#FF6A13 100%) !important;
      border: none !important; color: #fff !important; font-weight: 600;
      box-shadow: 0 6px 16px rgba(0,120,212,0.30);
    }
    .stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
      filter: brightness(1.05); box-shadow: 0 8px 22px rgba(255,106,19,0.34);
    }
    /* ---- Metric cards ---- */
    [data-testid="stMetric"] {
      background: #fff; border: 1px solid #E2E8F0; border-left: 4px solid #0078D4;
      border-radius: 12px; padding: 0.8rem 1rem; box-shadow: 0 2px 8px rgba(16,42,80,0.05);
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { color: #0b2746; }
    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] { gap: 0.25rem; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; }
    .stTabs [aria-selected="true"] { color: #0078D4 !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: #0078D4 !important; }
    /* ---- Complexity badges ---- */
    .cx-badges { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.5rem 0 0.2rem 0; }
    .cx-badge {
      font-size: 0.76rem; font-weight: 600; padding: 0.24rem 0.62rem; border-radius: 999px;
      border: 1px solid #cfe0f2; background: #eef5fc; color: #0b3b66;
    }
    .cx-badge.warn { background: #fff3e6; border-color: #ffd6a8; color: #9a4a00; }
    .cx-badge.mistral { background: #fff0e6; border-color: #ffcaa3; color: #a83800; }
    /* ---- Model column headers (compare view) ---- */
    .model-head {
      border-radius: 12px; padding: 0.55rem 0.95rem; font-weight: 700; color: #fff;
      margin-bottom: 0.6rem; display: flex; align-items: center; gap: 0.5rem;
    }
    .model-head.ocr4 { background: linear-gradient(90deg,#FF8205,#E10500); }
    .model-head.v2512 { background: linear-gradient(90deg,#0078D4,#243A5E); }
    .model-head .mh-tag {
      font-size: 0.72rem; font-weight: 600; background: rgba(255,255,255,0.22);
      padding: 0.12rem 0.5rem; border-radius: 999px;
    }
    /* ---- Whole-app background wash (Azure -> faint Mistral) ---- */
    [data-testid="stAppViewContainer"] {
      background:
        radial-gradient(1200px 480px at 100% -6%, rgba(255,106,19,0.06) 0%, rgba(255,106,19,0) 60%),
        radial-gradient(1100px 520px at 0% -8%, rgba(0,120,212,0.10) 0%, rgba(0,120,212,0) 55%),
        #f3f8fe;
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stHeader"]::after {
      content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
      background: linear-gradient(90deg,#50E6FF 0%,#0078D4 30%,#FF8205 72%,#E10500 100%);
    }
    /* ---- Sidebar: branded gradient surface + nav emphasis ---- */
    [data-testid="stSidebar"] {
      background: linear-gradient(180deg,#eaf3fd 0%,#e7effb 52%,#f4eefb 100%);
      border-right: 1px solid #d6e4f0;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
      background: rgba(0,120,212,0.12); font-weight: 700; border-radius: 8px;
    }
    .side-brand { padding: 0.15rem 0 0.5rem 0; line-height: 1.2; }
    .side-brand-title {
      font-weight: 800; font-size: 1.06rem;
      background: linear-gradient(90deg,#0078D4,#FF6A13);
      -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    }
    .side-brand-sub { font-size: 0.76rem; color: #5b6b7f; margin-top: 0.05rem; }
    /* ---- Expanders as soft cards on the tinted body ---- */
    [data-testid="stExpander"] {
      background: rgba(255,255,255,0.78); border: 1px solid #d8e6f5;
      border-radius: 14px; box-shadow: 0 2px 10px rgba(16,42,80,0.05);
    }
    </style>
    """,
    unsafe_allow_html=True,
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


def _render_sample_preview(data: bytes) -> None:
    """Show the selected document in a native PDF viewer with quick complexity badges."""
    pages = _get_page_count(data)
    size = (
        f"{len(data) / 1024:.0f} KB"
        if len(data) < 1024 * 1024
        else f"{len(data) / (1024 * 1024):.1f} MB"
    )
    badges: list[str] = []
    if pages:
        badges.append(f'<span class="cx-badge">{pages} page(s)</span>')
    badges.append(f'<span class="cx-badge">{size}</span>')
    if pages and pages > 30:
        badges.append('<span class="cx-badge warn">auto-chunked (&gt;30 pages)</span>')
    st.markdown('<div class="cx-badges">' + "".join(badges) + "</div>", unsafe_allow_html=True)
    try:
        st.pdf(data, height=480)
    except Exception:
        st.caption("Inline preview unavailable - use the download button to open the PDF.")


def _build_annotation_params(opts):
    """Construct bbox/document annotation schema params from the given options."""
    bbox_fmt = _pydantic_to_mistral_schema(ImageDescription) if opts["enable_bbox"] else None
    doc_fmt = None
    if opts["enable_doc_annotation"]:
        from pydantic import create_model as _cm

        _DocSummary = _cm(
            "DocumentSummary",
            topics=(list[str], ...),
            entities=(list[str], ...),
            summary=(str, ...),
        )
        doc_fmt = _pydantic_to_mistral_schema(_DocSummary)
    return bbox_fmt, doc_fmt


def _run_ocr_for(mk: str, src_pdf: bytes, name: str, opts: dict, progress_cb=None) -> OCRResult:
    """Run a single OCR call for model key `mk` using the given options dict."""
    tmp_path = Path("data") / f"_tmp_{mk}_{name}"
    tmp_path.parent.mkdir(exist_ok=True)
    tmp_path.write_bytes(src_pdf)
    bbox_fmt, doc_fmt = _build_annotation_params(opts)
    adv = mk in ("2512", "ocr4")
    is4 = mk == "ocr4"
    sel_pages = _parse_pages_input(opts["pages_input"]) if adv else None
    try:
        return run_async(
            ocr_pdf(
                tmp_path,
                endpoint=opts["endpoint"],
                model_key=mk,
                api_key=opts["api_key"] or None,
                include_images=opts["include_images"],
                table_format=opts["table_format_val"] if adv else None,
                extract_header=opts["extract_header"] if adv else False,
                extract_footer=opts["extract_footer"] if adv else False,
                pages=sel_pages,
                image_limit=opts["image_limit"] if adv and opts["image_limit"] > 0 else None,
                include_blocks=opts["include_blocks"] if is4 else False,
                confidence_scores_granularity=(
                    opts["confidence_granularity"]
                    if is4 and opts["confidence_granularity"] != "off"
                    else None
                ),
                bbox_annotation_format=bbox_fmt,
                document_annotation_format=doc_fmt,
                document_annotation_prompt=opts["doc_annotation_prompt"] or None,
                progress_callback=progress_cb,
            )
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def _render_comparison(cmp: dict, name: str, pdf_bytes: bytes = b"", table_format=None) -> None:
    """Side-by-side OCR 4.0 vs v25.12 with a per-model deep dive."""
    st.markdown("---")
    st.markdown("## \u2696\ufe0f OCR 4.0 vs v25.12")
    st.caption(
        f"Document: **{name}** \u2014 both models were called **in parallel** with identical "
        f"parameters and REST path (`/providers/mistral/azure/ocr`)."
    )

    order = [("ocr4", "OCR 4.0", "ocr4"), ("2512", "v25.12", "v2512")]
    cols = st.columns(2)
    stats_by_model: dict[str, dict] = {}

    for col, (mk, lbl, cls) in zip(cols, order):
        entry = cmp.get(mk, {})
        with col:
            st.markdown(
                f'<div class="model-head {cls}">{lbl}'
                f'<span class="mh-tag">{get_deployment_name(mk)}</span></div>',
                unsafe_allow_html=True,
            )
            if not entry.get("ok"):
                st.error(f"\u274c {entry.get('error', 'unknown error')}")
                stats_by_model[mk] = {}
                continue
            res: OCRResult = entry["result"]
            s = compute_doc_stats(res)
            blocks = sum(len(p.blocks) for p in res.pages)
            has_conf = any(p.confidence_scores is not None for p in res.pages)
            stats_by_model[mk] = {
                "time": res.elapsed_ms,
                "pages": len(res.pages),
                "words": s["words"],
                "tables": s["tables"],
                "images": len(res.images),
                "sections": s["sections"],
                "blocks": blocks,
                "confidence": has_conf,
                "result": res,
            }
            c1, c2, c3 = st.columns(3)
            c1.metric("Pages", len(res.pages))
            c2.metric("Words", f"{s['words']:,}")
            c3.metric("Tables", s["tables"])
            c4, c5, c6 = st.columns(3)
            c4.metric("Images", len(res.images))
            c5.metric("Blocks", blocks)
            c6.metric("Time", f"{res.elapsed_ms:.0f} ms")
            st.download_button(
                f"Download {lbl} .md",
                data=res.markdown,
                file_name=f"{Path(name).stem}_{mk}.md",
                mime="text/markdown",
                key=f"cmp_dl_{mk}",
                width="stretch",
            )

    # Consolidated diff table
    def _cell(mk: str, key: str, fmt=str):
        v = stats_by_model.get(mk, {}).get(key)
        return fmt(v) if v is not None else "\u2014"

    st.markdown("### Side-by-side metrics")
    diff_rows = [
        {"Metric": "Status", "OCR 4.0": "\u2705 OK" if stats_by_model.get("ocr4") else "\u274c failed",
         "v25.12": "\u2705 OK" if stats_by_model.get("2512") else "\u274c failed"},
        {"Metric": "Latency", "OCR 4.0": _cell("ocr4", "time", lambda v: f"{v:.0f} ms"),
         "v25.12": _cell("2512", "time", lambda v: f"{v:.0f} ms")},
        {"Metric": "Pages", "OCR 4.0": _cell("ocr4", "pages"), "v25.12": _cell("2512", "pages")},
        {"Metric": "Words", "OCR 4.0": _cell("ocr4", "words", lambda v: f"{v:,}"),
         "v25.12": _cell("2512", "words", lambda v: f"{v:,}")},
        {"Metric": "Tables", "OCR 4.0": _cell("ocr4", "tables"), "v25.12": _cell("2512", "tables")},
        {"Metric": "Images", "OCR 4.0": _cell("ocr4", "images"), "v25.12": _cell("2512", "images")},
        {"Metric": "Sections", "OCR 4.0": _cell("ocr4", "sections"), "v25.12": _cell("2512", "sections")},
        {"Metric": "Content blocks (bbox)", "OCR 4.0": _cell("ocr4", "blocks"),
         "v25.12": "n/a"},
        {"Metric": "Inline confidence", "OCR 4.0": "\u2705" if stats_by_model.get("ocr4", {}).get("confidence") else "\u2014",
         "v25.12": "n/a"},
    ]
    st.dataframe(pd.DataFrame(diff_rows), width="stretch", hide_index=True)
    st.caption(
        "**Content blocks** and **inline confidence** are OCR 4.0-only \u2014 enable "
        "*Content blocks* / *Confidence scores* in the sidebar before comparing to populate them."
    )

    # Per-model deep dive (full detail for each model, side by side as tabs)
    st.markdown("### \U0001f50e Detailed breakdown per model")
    d_ocr4, d_2512 = st.tabs(["\U0001f7e0 OCR 4.0", "\U0001f535 v25.12"])
    for tab, mk, lbl in ((d_ocr4, "ocr4", "OCR 4.0"), (d_2512, "2512", "v25.12")):
        with tab:
            entry = cmp.get(mk, {})
            if entry.get("ok"):
                render_result_detail(entry["result"], name, pdf_bytes, table_format, key=mk)
            else:
                st.info(f"{lbl} did not return a result for this run.")


# ---------------------------------------------------------------------------
# Brand chips (reused across page heroes)
# ---------------------------------------------------------------------------
CHIP_AZURE = (
    '<span class="chip chip-azure"><span class="chip-dot"></span>Azure AI Foundry</span>'
)
CHIP_MISTRAL = (
    '<span class="chip chip-mistral"><span class="chip-dot"></span>Mistral OCR 4.0</span>'
)
CHIP_API = (
    '<span class="chip chip-azure"><span class="chip-dot"></span>'
    'REST &middot; api 2024-05-01-preview</span>'
)


def _hero(eyebrow: str, title_html: str, sub_html: str, chips: list[str]) -> None:
    """Render the branded, full-width page hero."""
    st.markdown(
        '<div class="brand-hero">'
        '<div class="brand-eyebrow">' + eyebrow + '</div>'
        '<div class="brand-title">' + title_html + '</div>'
        '<p class="brand-sub">' + sub_html + '</p>'
        '<div class="brand-chips">' + "".join(chips) + '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Shared sidebar controls — Connection, OCR options, history
# ---------------------------------------------------------------------------
def render_connection() -> tuple[str, str]:
    """Endpoint + API key (shared across pages). Both are required."""
    with st.sidebar:
        st.markdown("#### \U0001f50c Connection")
        endpoint = st.text_input(
            "Endpoint",
            value=os.getenv("MISTRAL_ENDPOINT", ""),
            key="cfg_endpoint",
            help="Microsoft Foundry endpoint, e.g. https://<resource>.services.ai.azure.com",
        )
        api_key = st.text_input(
            "API key",
            value=os.getenv("AZURE_AI_KEY", ""),
            type="password",
            key="cfg_api_key",
            help="Required \u2014 Microsoft Foundry API key for the deployment.",
        )
        if not (endpoint and api_key):
            st.caption("\u26a0\ufe0f Endpoint **and** API key are required to run OCR.")
    return endpoint, api_key


def render_ocr_options() -> dict:
    """Render shared OCR option widgets in the sidebar and return an options dict.

    Both models always run on the document, so there is no model selector. The
    OCR 4.0-only extras (content blocks, confidence) apply to the OCR 4.0 column.
    """
    opts: dict = {}
    with st.sidebar:
        opts["include_images"] = st.checkbox(
            "Include image extraction", value=True, key="cfg_include_images"
        )

        with st.expander("\u2699\ufe0f Advanced extraction", expanded=False):
            table_format = st.selectbox(
                "Table format",
                options=["(none)", "markdown", "html"],
                key="cfg_table_format",
                help=(
                    "How tables are returned (v25.12 / OCR 4.0).\n\n"
                    "- **(none)**: tables stay inline in the page markdown.\n"
                    "- **markdown**: also returned in `pages[].tables[]` with a `markdown` key.\n"
                    "- **html**: returned with an `html` key preserving colspan / rowspan."
                ),
            )
            opts["table_format_val"] = None if table_format == "(none)" else table_format
            opts["extract_header"] = st.checkbox(
                "Extract headers",
                key="cfg_extract_header",
                help="Extract repeated header text from the top of each page (`pages[].header`).",
            )
            opts["extract_footer"] = st.checkbox(
                "Extract footers",
                key="cfg_extract_footer",
                help="Extract repeated footer text from the bottom of each page (`pages[].footer`).",
            )
            opts["pages_input"] = st.text_input(
                "Pages (e.g. 1, 3, 5-8)",
                key="cfg_pages",
                help="1-indexed, comma-separated, ranges allowed. Empty = all pages.",
            )
            opts["image_limit"] = st.number_input(
                "Image limit",
                min_value=0,
                value=0,
                key="cfg_image_limit",
                help="Max images returned across all pages. 0 = unlimited.",
            )

        with st.expander("\u2728 OCR 4.0 features", expanded=False):
            st.caption("These apply to the **OCR 4.0** column of the comparison.")
            opts["include_blocks"] = st.checkbox(
                "Content blocks + bounding boxes",
                value=False,
                key="cfg_include_blocks",
                help=(
                    "OCR 4.0 only. Paragraph-level blocks with bounding boxes and type "
                    "classification (title, paragraph, table, equation, signature, ...). "
                    "Great for semantic chunking (RAG), citations and layout-aware pipelines."
                ),
            )
            opts["confidence_granularity"] = st.selectbox(
                "Confidence scores",
                options=["off", "page", "word"],
                index=0,
                key="cfg_confidence",
                help=(
                    "OCR 4.0 only. Inline confidence per page or per word for "
                    "human-in-the-loop QA and automated error flagging."
                ),
            )

        with st.expander("\U0001f3f7\ufe0f Annotations", expanded=False):
            st.caption(
                "JSON-Schema structured extraction. Limited to the first **8 pages**."
            )
            opts["enable_bbox"] = st.checkbox(
                "BBox annotations (per-image)",
                key="cfg_bbox",
                help="Classify each image with a JSON Schema (image_type, summary, ...).",
            )
            opts["enable_doc_annotation"] = st.checkbox(
                "Document annotation (whole-doc)",
                key="cfg_doc_annot",
                help="One structured summary for the whole document (`document_annotation`).",
            )
            prompt = ""
            if opts["enable_doc_annotation"]:
                prompt = st.text_area(
                    "Document annotation prompt",
                    value="Summarize this document with key topics and entities.",
                    height=80,
                    key="cfg_doc_prompt",
                    help="Optional prompt guiding the document-level annotation.",
                )
            opts["doc_annotation_prompt"] = prompt

    opts["supports_advanced"] = True
    return opts


def render_history() -> None:
    """Recent extractions saved under extraction/ (collapsed in the sidebar)."""
    with st.sidebar:
        with st.expander("\U0001f553 Extraction history", expanded=False):
            extraction_dir = Path("extraction")
            saved = (
                sorted(extraction_dir.glob("*_meta.json"), reverse=True)
                if extraction_dir.exists()
                else []
            )
            if saved:
                for meta_file in saved[:10]:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    src = meta.get("source", meta_file.stem)
                    pages = meta.get("pages", "?")
                    tbls = meta.get("tables", meta.get("tables_found", 0))
                    st.caption(f"{src} \u2014 {pages}p, {tbls} tables")
            else:
                st.caption("No extractions saved yet.")


def file_input() -> tuple[bytes | None, str]:
    """Upload or pick a PDF, validate, and show a preview. Keyed for cross-page persistence."""
    col1, col2 = st.columns([1, 1])
    with col1:
        uploaded_file = st.file_uploader(
            "Upload PDF",
            type=["pdf"],
            key="in_upload",
            help=f"PDF format \u2014 max {MAX_FILE_SIZE_MB} MB per file",
        )
    with col2:
        data_dir = Path("data")
        local_pdfs = sorted(data_dir.glob("*.pdf")) if data_dir.exists() else []
        local_choice = st.selectbox(
            "Or select from data/",
            options=["(none)"] + [p.name for p in local_pdfs],
            key="in_local_choice",
        )

    pdf_bytes: bytes | None = None
    pdf_name = ""
    if uploaded_file is not None:
        pdf_bytes = uploaded_file.read()
        pdf_name = uploaded_file.name
    elif local_choice and local_choice != "(none)":
        pdf_bytes = (Path("data") / local_choice).read_bytes()
        pdf_name = local_choice

    if pdf_bytes:
        validation_error = _validate_upload(pdf_bytes, pdf_name)
        if validation_error:
            st.error(f"\u274c {validation_error}")
            return None, ""
        size_mb = len(pdf_bytes) / (1024 * 1024)
        page_count = _get_page_count(pdf_bytes)
        info_parts = [f"**{pdf_name}**", f"{size_mb:.2f} MB"]
        if page_count is not None:
            info_parts.append(f"{page_count} page(s)")
            if page_count > 30:
                info_parts.append("\u26a1 auto-chunked (>30 pages)")
        if size_mb > MAX_FILE_SIZE_MB * 0.8:
            st.warning(
                f"\u26a0\ufe0f File is {size_mb:.1f} MB \u2014 approaching "
                f"the {MAX_FILE_SIZE_MB} MB limit"
            )
        st.info(" \u00b7 ".join(info_parts))
        with st.expander("\U0001f4c4 Document preview & complexity", expanded=True):
            st.caption(
                "Visual preview of the selected document \u2014 gauge layout "
                "complexity before running OCR."
            )
            _render_sample_preview(pdf_bytes)

    return pdf_bytes, pdf_name


# ---------------------------------------------------------------------------
# Reference content (moved out of the viewport into its own page)
# ---------------------------------------------------------------------------
def render_reference():
    st.markdown("### v25.12 vs OCR 4.0 — Feature Matrix")
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
| `include_blocks` | `bool` | `false` | **OCR 4.0** \u2014 return content blocks with bounding boxes + type into `pages[].blocks` |
| `confidence_scores_granularity` | `\"page\"` \\| `\"word\"` \\| `null` | `null` | **OCR 4.0** \u2014 inline confidence scores into `pages[].confidence_scores` |

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


# ---------------------------------------------------------------------------
# Per-model detail renderer (used by the comparison view)
# ---------------------------------------------------------------------------
def render_result_detail(result, pdf_name, pdf_bytes_display=b"", table_format=None, *, key=""):
    """Render the detailed tabbed view for a single OCR result (model-scoped keys)."""
    tab_md, tab_tables, tab_images, tab_pages, tab_annotations, tab_raw = st.tabs(
        ["Full Markdown", "Tables", "Images", "Per Page", "Annotations", "Raw JSON"]
    )

    # --- Full Markdown tab ---
    with tab_md:
        st.markdown("### Extracted Markdown")
        view_mode = st.radio(
            "View mode",
            ["Rendered", "Raw source"],
            horizontal=True,
            key=f"{key}_md_view",
        )
        if view_mode == "Rendered":
            st.markdown(result.markdown)
        else:
            st.code(result.markdown, language="markdown")
        st.download_button(
            "Download .md",
            data=result.markdown,
            file_name=f"{Path(pdf_name).stem}_{key}.md",
            mime="text/markdown",
            key=f"{key}_dl_md",
        )

    # --- Tables tab ---
    with tab_tables:
        used_format = table_format
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
                        file_name=f"{Path(pdf_name).stem}_{key}_api_table_{idx + 1}.html",
                        mime="text/html",
                        key=f"{key}_api_html_{idx}",
                    )
                elif isinstance(tbl, dict) and "markdown" in tbl:
                    st.markdown(tbl["markdown"])
                    st.download_button(
                        f"Download Table {idx + 1} (Markdown)",
                        data=tbl["markdown"],
                        file_name=f"{Path(pdf_name).stem}_{key}_api_table_{idx + 1}.md",
                        mime="text/markdown",
                        key=f"{key}_api_md_{idx}",
                    )
                else:
                    st.json(tbl)
            st.markdown("---")
            st.markdown("#### Also parsed from inline markdown:")

        tables = extract_markdown_tables(result.markdown)
        if tables:
            st.markdown(f"### {len(tables)} table(s) detected")
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
            st.dataframe(pd.DataFrame(summary_data), width="stretch", hide_index=True)
            st.markdown("---")
            for idx, df in enumerate(tables):
                st.markdown(
                    f"**Table {idx + 1}** ({df.shape[0]} rows x {df.shape[1]} cols)"
                )
                search_term = st.text_input(
                    f"Filter Table {idx + 1}",
                    key=f"{key}_filter_{idx}",
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
                st.dataframe(display_df, width="stretch", hide_index=True)
                csv = df.to_csv(index=False)
                st.download_button(
                    f"Download Table {idx + 1} as CSV",
                    data=csv,
                    file_name=f"{Path(pdf_name).stem}_{key}_table_{idx + 1}.csv",
                    mime="text/csv",
                    key=f"{key}_csv_{idx}",
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
                for col_idx, img in enumerate(result.images[i : i + cols_per_row]):
                    img_id = img.get("id", "unknown")
                    page = img.get("page_index", "?")
                    b64 = img.get("image_base64") or img.get("base64", "")
                    with img_cols[col_idx]:
                        st.markdown(f"**{img_id}** (page {page})")
                        if b64:
                            st.image(base64.b64decode(b64), caption=img_id, width="stretch")
                        else:
                            st.caption("No base64 image data available.")
                        meta_keys = {
                            k: v for k, v in img.items() if k not in ("image_base64", "base64")
                        }
                        st.json(meta_keys)
        else:
            st.info("No images extracted. Enable 'Include image extraction' in sidebar.")

    # --- Per Page tab ---
    with tab_pages:
        st.markdown("### Per-page breakdown")
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
                st.dataframe(pd.DataFrame(hf_data), width="stretch", hide_index=True)

        page_data = []
        for p in result.pages:
            page_tables = extract_markdown_tables(p.markdown)
            page_data.append({
                "Page": p.page_index + 1,
                "Characters": len(p.markdown),
                "Words": len(p.markdown.split()),
                "Tables": len(page_tables) + len(p.tables),
                "Images": len(p.images),
                "Blocks": len(p.blocks),
                "Preview": p.markdown[:120].replace("\n", " "),
            })
        st.dataframe(pd.DataFrame(page_data), width="stretch", hide_index=True)

        if result.pages:
            page_idx = st.selectbox(
                "View page markdown",
                options=range(len(result.pages)),
                format_func=lambda x: f"Page {x + 1}",
                key=f"{key}_pagesel",
            )
            selected_page = result.pages[page_idx]
            st.markdown("---")
            if selected_page.header:
                st.caption(f"**Header:** {selected_page.header}")
            st.markdown(selected_page.markdown)
            if selected_page.footer:
                st.caption(f"**Footer:** {selected_page.footer}")

            if selected_page.blocks:
                st.markdown("---")
                st.markdown("#### \U0001f9e9 Content blocks (OCR 4.0)")
                block_rows = []
                for b in selected_page.blocks:
                    text = b.get("content") or b.get("markdown") or b.get("text") or ""
                    conf = b.get("confidence") or b.get("confidence_score")
                    block_rows.append({
                        "Type": b.get("type", "\u2014"),
                        "BBox": str(b.get("bbox") or b.get("bounding_box") or "\u2014"),
                        "Confidence": round(conf, 3) if isinstance(conf, (int, float)) else "\u2014",
                        "Content": str(text)[:80].replace("\n", " "),
                    })
                st.dataframe(pd.DataFrame(block_rows), width="stretch", hide_index=True)

            if selected_page.confidence_scores is not None:
                with st.expander("\U0001f3af Confidence scores (OCR 4.0)", expanded=False):
                    st.json(selected_page.confidence_scores)

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
            file_name=f"{Path(pdf_name).stem}_{key}_ocr.json",
            mime="application/json",
            key=f"{key}_dl_json",
        )

    # ---- Save to extraction/ ----
    st.markdown("---")
    if st.button("Save to extraction/ folder", width="stretch", key=f"{key}_save"):
        out_dir = Path("extraction")
        out_dir.mkdir(exist_ok=True)
        stem = f"{Path(pdf_name).stem}_{key}"
        (out_dir / f"{stem}.md").write_text(result.markdown, encoding="utf-8")
        tables = extract_markdown_tables(result.markdown)
        for i, df in enumerate(tables):
            df.to_csv(out_dir / f"{stem}_table_{i + 1}.csv", index=False)
        meta = {
            "source": pdf_name,
            "model": key,
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
        full_json = result.model_dump()
        full_json["source"] = pdf_name
        (out_dir / f"{stem}_full.json").write_text(
            json.dumps(full_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        st.success(
            f"Saved to extraction/{stem}.md + metadata + {len(tables)} CSV(s) + full JSON"
        )


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_compare() -> None:
    _hero(
        "Two models \u00b7 one document \u00b7 side by side",
        'Compare <span class="accent">OCR 4.0</span> vs <span class="accent">v25.12</span>',
        "Upload a PDF and run <b>both</b> Mistral Document AI models on it <b>in parallel</b>, "
        "then compare their markdown, tables, images, timing and confidence \u2014 column by "
        "column. If one model is unavailable, the other still renders.",
        [CHIP_MISTRAL, CHIP_AZURE, CHIP_API],
    )
    endpoint, api_key = render_connection()
    opts = render_ocr_options()
    render_history()
    opts["endpoint"], opts["api_key"] = endpoint, api_key

    pdf_bytes, pdf_name = file_input()

    ready = bool(pdf_bytes and endpoint and api_key)
    if not endpoint or not api_key:
        st.warning(
            "Set your **endpoint** and **API key** in the sidebar **Connection** "
            "(or `MISTRAL_ENDPOINT` / `AZURE_AI_KEY` in `.env`) to run the comparison."
        )
    elif not pdf_bytes:
        st.info("Upload a PDF or pick one from `data/` to compare the two models.")

    if st.button(
        "\u2696\ufe0f Run both models in parallel",
        type="primary",
        width="stretch",
        disabled=not ready,
        help="Run OCR 4.0 and v25.12 concurrently on this document and compare them side by side.",
    ):
        with st.spinner("Running OCR 4.0 and v25.12 in parallel\u2026"):
            cmp_results: dict = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                futures = {
                    ex.submit(_run_ocr_for, mk, pdf_bytes, pdf_name, opts): mk
                    for mk in ("ocr4", "2512")
                }
                for fut in concurrent.futures.as_completed(futures):
                    mk = futures[fut]
                    try:
                        cmp_results[mk] = {"ok": True, "result": fut.result()}
                    except Exception as exc:
                        cmp_results[mk] = {"ok": False, "error": str(exc)}
        st.session_state["compare"] = cmp_results
        st.session_state["compare_pdf_name"] = pdf_name
        st.session_state["compare_pdf_bytes"] = pdf_bytes
        st.session_state["compare_table_format"] = opts["table_format_val"]

    if "compare" in st.session_state:
        _render_comparison(
            st.session_state["compare"],
            st.session_state.get("compare_pdf_name", ""),
            st.session_state.get("compare_pdf_bytes", b""),
            st.session_state.get("compare_table_format"),
        )


def page_reference() -> None:
    _hero(
        "Feature matrix \u00b7 capabilities, limits & parameters",
        'OCR 4.0 vs v25.12 \u2014 <span class="accent">feature matrix</span>',
        "A static side-by-side <strong>capability matrix</strong> \u2014 supported features, Microsoft "
        "Foundry API limits, request parameters and pricing. No document run here; use "
        "<strong>Compare</strong> to run both models live on a PDF.",
        [CHIP_AZURE, CHIP_MISTRAL, CHIP_API],
    )
    render_reference()


# ---------------------------------------------------------------------------
# Sidebar brand header + multipage navigation (st.navigation)
# ---------------------------------------------------------------------------
def main() -> None:
    """Entry point: brand header + multipage navigation."""
    st.sidebar.markdown(
        '<div class="side-brand">'
        '<div class="side-brand-title">Mistral Document AI</div>'
        '<div class="side-brand-sub">OCR 4.0 vs v25.12 \u00b7 on Microsoft Azure</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    nav = st.navigation(
        [
            st.Page(page_compare, title="Compare", icon="\u2696\ufe0f", default=True),
            st.Page(page_reference, title="Feature matrix", icon="\U0001f4ca"),
        ]
    )
    nav.run()


if __name__ == "__main__":
    main()
