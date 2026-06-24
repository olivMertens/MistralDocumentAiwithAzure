"""Side-by-side OCR model comparison — Mistral Document AI v25.05 vs v25.12.

A focused "viewport" that runs the **same** input (document *or* handwriting image)
through both model versions at once and shows the extracted text next to the source,
with latency and word-count metrics plus a word-level diff. Ideal for demonstrating
how v25.12 improves on complex layouts and handwriting.

Launch the app, then pick "Compare Models" from the sidebar:

    uv run streamlit run app.py
"""

from __future__ import annotations

import asyncio
import base64
import html
import os
from difflib import SequenceMatcher
from pathlib import Path

import streamlit as st

from src.extract import (
    MODELS,
    OCRResult,
    SUPPORTED_IMAGE_MIME,
    compare_models,
    get_deployment_name,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Model Comparison - Mistral Document AI",
    page_icon="\u2696\ufe0f",
    layout="wide",
)

MAX_FILE_SIZE_MB = 30
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
IMAGE_EXTS = [ext.lstrip(".") for ext in SUPPORTED_IMAGE_MIME]

# ---------------------------------------------------------------------------
# Load .env (same lightweight loader as app.py)
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
def run_async(coro):
    """Run an async coroutine from Streamlit's sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def is_pdf(data: bytes, filename: str) -> bool:
    return filename.lower().endswith(".pdf") or data[:5].startswith(b"%PDF")


def render_source(data: bytes, filename: str) -> None:
    """Preview the source as an inline PDF or an image."""
    if is_pdf(data, filename):
        b64 = base64.b64encode(data).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" '
            f'width="100%" height="560" type="application/pdf"></iframe>',
            unsafe_allow_html=True,
        )
    else:
        st.image(data, use_container_width=True)


def word_diff_html(a: str, b: str) -> str:
    """Word-level diff of two texts, highlighting what v25.12 (b) changed vs v25.05 (a)."""
    a_words = a.split()
    b_words = b.split()
    matcher = SequenceMatcher(a=a_words, b=b_words, autojunk=False)
    parts: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        a_seg = html.escape(" ".join(a_words[i1:i2]))
        b_seg = html.escape(" ".join(b_words[j1:j2]))
        if tag == "equal":
            parts.append(b_seg)
        elif tag == "insert":
            parts.append(f'<span style="background:#1f7a1f33;border-radius:3px">{b_seg}</span>')
        elif tag == "delete":
            parts.append(
                f'<span style="background:#a3333333;border-radius:3px;'
                f'text-decoration:line-through">{a_seg}</span>'
            )
        else:  # replace
            parts.append(
                f'<span style="background:#a3333333;border-radius:3px;'
                f'text-decoration:line-through">{a_seg}</span> '
                f'<span style="background:#1f7a1f33;border-radius:3px">{b_seg}</span>'
            )
    body = " ".join(p for p in parts if p)
    return (
        '<div style="line-height:1.7;white-space:pre-wrap;font-family:ui-monospace,'
        f'SFMono-Regular,Menlo,monospace;font-size:0.85rem">{body}</div>'
    )


def similarity_pct(a: str, b: str) -> float:
    return SequenceMatcher(a=a.split(), b=b.split(), autojunk=False).ratio() * 100


# ---------------------------------------------------------------------------
# Sidebar configuration
# ---------------------------------------------------------------------------
st.sidebar.title("Comparison Config")

endpoint = st.sidebar.text_input(
    "Endpoint",
    value=os.getenv("MISTRAL_ENDPOINT", ""),
    help="Microsoft Foundry endpoint URL",
)
api_key = st.sidebar.text_input(
    "API Key (optional)",
    value=os.getenv("AZURE_AI_KEY", ""),
    type="password",
    help="Leave empty to use Azure AD / DefaultAzureCredential",
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Models compared")
for key, info in MODELS.items():
    st.sidebar.caption(f"**{info['label']}** \u2014 `{get_deployment_name(key)}`")

st.sidebar.markdown("---")
st.sidebar.markdown("### v25.12 options")
table_format = st.sidebar.selectbox(
    "Table format (v25.12 only)",
    options=["(none)", "markdown", "html"],
    help="Structured table output is only applied to the v25.12 request.",
)
table_format_val = None if table_format == "(none)" else table_format
extract_header = st.sidebar.checkbox("Extract headers (v25.12)")
extract_footer = st.sidebar.checkbox("Extract footers (v25.12)")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("\u2696\ufe0f Model Comparison \u2014 v25.05 vs v25.12")
st.markdown(
    "Run the **same** document or handwriting image through both Mistral Document AI "
    "versions at once. Compare the extracted text side-by-side with the source, and "
    "see the **latency** and **accuracy** difference \u2014 handy for handwriting and "
    "complex layouts where v25.12 shines."
)

# ---------------------------------------------------------------------------
# Input selection
# ---------------------------------------------------------------------------
col_up, col_pick = st.columns([1, 1])

with col_up:
    uploaded = st.file_uploader(
        "Upload a document or image",
        type=["pdf"] + IMAGE_EXTS,
        help=f"PDF or image (PNG, JPEG, AVIF, WEBP\u2026) \u2014 max {MAX_FILE_SIZE_MB} MB",
    )

with col_pick:
    data_dir = Path("data")
    local_files: list[Path] = []
    if data_dir.exists():
        for pattern in ["*.pdf", *(f"*.{e}" for e in IMAGE_EXTS)]:
            local_files.extend(sorted(data_dir.glob(pattern)))
    local_choice = st.selectbox(
        "Or pick a sample from data/",
        options=["(none)"] + [p.name for p in sorted(set(local_files))],
        help="Drop handwriting samples into data/ (or run scripts/generate_sample_images.py).",
    )

# Resolve the active input
src_bytes: bytes | None = None
src_name = ""
if uploaded is not None:
    src_bytes = uploaded.read()
    src_name = uploaded.name
elif local_choice and local_choice != "(none)":
    p = data_dir / local_choice
    src_bytes = p.read_bytes()
    src_name = local_choice

if src_bytes is not None and len(src_bytes) > MAX_FILE_SIZE_BYTES:
    st.error(
        f"File too large: {len(src_bytes) / (1024 * 1024):.1f} MB "
        f"(limit: {MAX_FILE_SIZE_MB} MB on Microsoft Foundry)"
    )
    src_bytes = None

# ---------------------------------------------------------------------------
# Run comparison
# ---------------------------------------------------------------------------
disabled = not (src_bytes and endpoint)
if not endpoint:
    st.warning("Set your MISTRAL_ENDPOINT in the sidebar or .env file.")

if st.button(
    "Compare both models",
    type="primary",
    use_container_width=True,
    disabled=disabled,
):
    with st.spinner("Running both models concurrently\u2026"):
        try:
            results = run_async(
                compare_models(
                    src_bytes,
                    src_name,
                    model_keys=tuple(MODELS.keys()),
                    endpoint=endpoint,
                    api_key=api_key or None,
                    table_format=table_format_val,
                    extract_header=extract_header,
                    extract_footer=extract_footer,
                )
            )
            st.session_state["cmp_results"] = results
            st.session_state["cmp_bytes"] = src_bytes
            st.session_state["cmp_name"] = src_name
        except Exception as exc:  # noqa: BLE001
            st.error(f"Comparison failed: {exc}")

# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------
if "cmp_results" in st.session_state:
    results: dict[str, OCRResult | Exception] = st.session_state["cmp_results"]
    src_bytes = st.session_state.get("cmp_bytes", b"")
    src_name = st.session_state.get("cmp_name", "")
    keys = list(results.keys())

    st.markdown("---")

    # ---- Metrics row ----
    st.markdown("### Performance")
    metric_cols = st.columns(len(keys))
    word_counts: dict[str, int] = {}
    baseline_ms: float | None = None
    baseline_words: int | None = None
    for idx, key in enumerate(keys):
        res = results[key]
        label = MODELS[key]["label"]
        with metric_cols[idx]:
            if isinstance(res, Exception):
                st.metric(f"{label} \u00b7 latency", "error")
                continue
            words = len(res.markdown.split())
            word_counts[key] = words
            ms_delta = (
                f"{res.elapsed_ms - baseline_ms:+.0f} ms vs {MODELS[keys[0]]['label']}"
                if baseline_ms is not None
                else None
            )
            w_delta = (
                words - baseline_words if baseline_words is not None else None
            )
            st.metric(
                f"{label} \u00b7 latency",
                f"{res.elapsed_ms:.0f} ms",
                delta=ms_delta,
                delta_color="inverse",
            )
            st.metric(f"{label} \u00b7 words", f"{words:,}", delta=w_delta)
            st.metric(f"{label} \u00b7 chars", f"{len(res.markdown):,}")
            if baseline_ms is None:
                baseline_ms = res.elapsed_ms
                baseline_words = words

    # Similarity between the two text outputs (only meaningful for exactly 2 models)
    ok_keys = [k for k in keys if not isinstance(results[k], Exception)]
    if len(ok_keys) == 2:
        a, b = results[ok_keys[0]], results[ok_keys[1]]
        st.caption(
            f"Text similarity between {MODELS[ok_keys[0]]['label']} and "
            f"{MODELS[ok_keys[1]]['label']}: **{similarity_pct(a.markdown, b.markdown):.1f}%**"
        )

    view_mode = st.radio(
        "Text view",
        ["Rendered", "Raw text"],
        horizontal=True,
        key="cmp_view",
    )

    # ---- Viewport: source + one column per model ----
    st.markdown("### Viewport")
    cols = st.columns([1.1] + [1] * len(keys))

    with cols[0]:
        st.markdown("#### \U0001f4c4 Source")
        st.caption(src_name)
        if src_bytes:
            render_source(src_bytes, src_name)

    for idx, key in enumerate(keys):
        res = results[key]
        with cols[idx + 1]:
            st.markdown(f"#### {MODELS[key]['label']}")
            st.caption(f"`{get_deployment_name(key)}`")
            if isinstance(res, Exception):
                st.error(f"Extraction failed: {res}")
                continue
            if view_mode == "Rendered":
                st.markdown(res.markdown or "_(no text extracted)_")
            else:
                st.code(res.markdown, language="markdown")
            st.download_button(
                f"Download {MODELS[key]['label']} .md",
                data=res.markdown,
                file_name=f"{Path(src_name).stem}_{key}.md",
                mime="text/markdown",
                key=f"dl_{key}",
            )

    # ---- Word-level diff ----
    if len(ok_keys) == 2:
        a_key, b_key = ok_keys
        with st.expander(
            f"\U0001f50d Differences \u2014 {MODELS[b_key]['label']} relative to "
            f"{MODELS[a_key]['label']}",
            expanded=True,
        ):
            st.caption(
                "Green = added/changed by "
                f"{MODELS[b_key]['label']} \u00b7 red strikethrough = only in "
                f"{MODELS[a_key]['label']}"
            )
            st.markdown(
                word_diff_html(results[a_key].markdown, results[b_key].markdown),
                unsafe_allow_html=True,
            )
else:
    st.info(
        "Pick a sample or upload a file, then click **Compare both models**. "
        "Try a handwriting image to see the v25.12 improvement most clearly."
    )
