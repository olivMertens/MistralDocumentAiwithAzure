"""Handwriting & Multilingual OCR — Mistral Document AI v25.05 vs v25.12.

A clean side-by-side "viewport" that runs the **same** input (a document *or* a
handwriting image) through both model versions at once and shows the extracted text
next to the source, with latency / word-count metrics and a word-level diff. Built to
make the v25.12 improvement on **handwriting** and **multilingual** scripts obvious.

Enter your endpoint (DNS) + API key once — they are saved in your **browser's local
storage** so the demo is ready next time. Click **Test** to verify the connection,
pick a curated sample, then **Compare**.

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
    test_connection,
)

try:
    from streamlit_local_storage import LocalStorage

    _LS_AVAILABLE = True
except Exception:  # noqa: BLE001 — degrade gracefully if the component is missing
    _LS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Handwriting & Multilingual OCR - Mistral Document AI",
    page_icon="\U0001f58d\ufe0f",
    layout="wide",
)

MAX_FILE_SIZE_MB = 30
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
IMAGE_EXTS = [ext.lstrip(".") for ext in SUPPORTED_IMAGE_MIME]

LS_ENDPOINT_KEY = "mistral_endpoint"
LS_APIKEY_KEY = "mistral_api_key"

# ---------------------------------------------------------------------------
# Load .env (same lightweight loader as app.py) — used as a fallback default
# ---------------------------------------------------------------------------
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ---------------------------------------------------------------------------
# Curated sample catalogue — friendly label, difficulty, language.
# Ordered easy -> very hard so a demo can ramp up the challenge.
# ---------------------------------------------------------------------------
CURATED: dict[str, tuple[str, str, str]] = {
    "sample_printed_note.png": ("\U0001f4c4 Printed note \u2014 English", "Easy", "EN"),
    "sample_handwritten_en.png": ("\u270d\ufe0f Handwriting \u2014 English list", "Medium", "EN"),
    "sample_printed_zh.png": ("\U0001f30f Printed \u2014 Chinese \u4e2d\u6587", "Medium", "ZH"),
    "sample_printed_ja.png": ("\U0001f30f Printed \u2014 Japanese \u65e5\u672c\u8a9e", "Medium", "JA"),
    "sample_printed_ko.png": ("\U0001f30f Printed \u2014 Korean \ud55c\uad6d\uc5b4", "Medium", "KO"),
    "sample_handwritten_fr.png": ("\u270d\ufe0f Handwriting \u2014 French (accents)", "Hard", "FR"),
    "sample_handwritten_es.png": ("\u270d\ufe0f Handwriting \u2014 Spanish (\u00f1 \u00bf\u00a1)", "Hard", "ES"),
    "sample_handwritten_de.png": ("\u270d\ufe0f Handwriting \u2014 German (\u00e4 \u00f6 \u00fc \u00df)", "Hard", "DE"),
    "sample_handwritten_it.png": ("\u270d\ufe0f Handwriting \u2014 Italian", "Hard", "IT"),
    "sample_complex_report.pdf": ("\U0001f4d1 Complex report PDF (tables + charts)", "Hard", "\u2014"),
    "sample_handwritten_hard.png": ("\U0001fa7a Doctor's note \u2014 messy scrawl", "Very hard", "EN"),
}
DIFFICULTY_RANK = {"Easy": 0, "Medium": 1, "Hard": 2, "Very hard": 3}


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


def hydrate_connection(local_store) -> None:
    """Seed endpoint/key from .env, then override once from browser local storage."""
    if "endpoint_input" not in st.session_state:
        st.session_state["endpoint_input"] = os.getenv("MISTRAL_ENDPOINT", "")
    if "apikey_input" not in st.session_state:
        st.session_state["apikey_input"] = os.getenv("AZURE_AI_KEY", "")
    if local_store is not None and not st.session_state.get("_ls_hydrated"):
        stored_ep = local_store.getItem(LS_ENDPOINT_KEY)
        stored_key = local_store.getItem(LS_APIKEY_KEY)
        if stored_ep:
            st.session_state["endpoint_input"] = stored_ep
        if stored_key:
            st.session_state["apikey_input"] = stored_key
        if stored_ep or stored_key:
            st.session_state["_ls_hydrated"] = True


# ---------------------------------------------------------------------------
# Sidebar — Connection (persisted to browser local storage)
# ---------------------------------------------------------------------------
local_store = LocalStorage() if _LS_AVAILABLE else None
hydrate_connection(local_store)

st.sidebar.title("\U0001f50c Connection")
if _LS_AVAILABLE:
    st.sidebar.caption("Saved in your browser's local storage \u2014 it never leaves this machine.")
else:
    st.sidebar.caption("Kept for this session only (local-storage component unavailable).")

st.sidebar.text_input(
    "Endpoint (DNS)",
    key="endpoint_input",
    placeholder="https://<resource>.services.ai.azure.com",
    help="Your Microsoft Foundry endpoint URL.",
)
st.sidebar.text_input(
    "API key",
    key="apikey_input",
    type="password",
    help="Leave empty to use Azure AD / DefaultAzureCredential.",
)

c_save, c_test = st.sidebar.columns(2)
save_clicked = c_save.button("\U0001f4be Save", use_container_width=True)
test_clicked = c_test.button("\U0001f50c Test", use_container_width=True)

if save_clicked:
    if local_store is not None:
        local_store.setItem(
            LS_ENDPOINT_KEY, st.session_state["endpoint_input"], key="ls_save_ep"
        )
        local_store.setItem(
            LS_APIKEY_KEY, st.session_state["apikey_input"], key="ls_save_key"
        )
        st.session_state["_ls_hydrated"] = True
        st.sidebar.success("Saved to your browser.")
    else:
        st.sidebar.info("Local storage unavailable \u2014 values kept for this session only.")

if test_clicked:
    ep = st.session_state["endpoint_input"].strip()
    ak = st.session_state["apikey_input"].strip()
    if not ep:
        st.session_state["conn_status"] = {"ok": False, "message": "Set an endpoint first."}
    else:
        with st.spinner("Testing connection\u2026"):
            st.session_state["conn_status"] = run_async(test_connection(ep, ak or None))

status = st.session_state.get("conn_status")
if status:
    if status.get("ok"):
        ms = status.get("elapsed_ms")
        tail = f" \u00b7 {ms:.0f} ms" if ms else ""
        st.sidebar.success(f"\u2705 {status.get('message', 'Connected')}{tail}")
    else:
        st.sidebar.error(f"\u274c {status.get('message', 'Connection failed')}")

st.sidebar.caption("\u26a0\ufe0f The API key is stored in plain text in your browser. Use a demo/dev key.")

# Active connection values used by the comparison run.
endpoint = st.session_state["endpoint_input"].strip()
api_key = st.session_state["apikey_input"].strip()

st.sidebar.markdown("---")
st.sidebar.markdown("### Models compared")
for key, info in MODELS.items():
    st.sidebar.caption(f"**{info['label']}** \u2014 `{get_deployment_name(key)}`")

with st.sidebar.expander("\u2699\ufe0f Advanced \u2014 v25.12 options", expanded=False):
    table_format = st.selectbox(
        "Table format",
        options=["(none)", "markdown", "html"],
        help="Structured table output is applied to the v25.12 request only.",
    )
    table_format_val = None if table_format == "(none)" else table_format
    extract_header = st.checkbox("Extract headers")
    extract_footer = st.checkbox("Extract footers")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("\U0001f58d\ufe0f Handwriting & Multilingual OCR \u2014 v25.05 vs v25.12")
st.markdown(
    "Run the **same** page through both Mistral Document AI versions at once and compare "
    "the extracted text side-by-side with the source. Built to show how **v25.12** improves "
    "on **handwriting**, **multilingual** scripts (EN/FR/ES/DE/IT and \u4e2d\u6587/\u65e5\u672c\u8a9e/"
    "\ud55c\uad6d\uc5b4), and dense layouts. Set your endpoint + key once (saved in your browser), "
    "**Test** the connection, pick a sample, then **Compare**."
)

# ---------------------------------------------------------------------------
# Input selection
# ---------------------------------------------------------------------------
st.markdown("#### 1 \u00b7 Choose an input")

data_dir = Path("data")
existing = {p.name for p in data_dir.iterdir()} if data_dir.exists() else set()

# Build curated options (only files present on disk), then any extra files.
options: list[tuple[str, str | None]] = [("\u2014 Select a sample \u2014", None)]
for fname, (label, diff, _lang) in sorted(
    CURATED.items(), key=lambda kv: (DIFFICULTY_RANK[kv[1][1]], kv[1][0])
):
    if fname in existing:
        options.append((f"{label}  \u00b7  {diff}", fname))
valid_exts = {"pdf", *IMAGE_EXTS}
for fname in sorted(existing):
    if fname not in CURATED and fname.rsplit(".", 1)[-1].lower() in valid_exts:
        options.append((f"\U0001f4ce Other \u2014 {fname}", fname))

label_to_file = dict(options)

col_pick, col_up = st.columns([1.3, 1])
with col_pick:
    choice_label = st.selectbox(
        "Curated samples (easy \u2192 very hard)",
        options=[lbl for lbl, _ in options],
        help="Multilingual handwriting + a complex report. "
        "Generate more with scripts/generate_sample_images.py.",
    )
    local_choice = label_to_file.get(choice_label)
    if local_choice and local_choice in CURATED:
        _, diff, lang = CURATED[local_choice]
        st.caption(f"Difficulty: **{diff}**  \u00b7  Language: **{lang}**")
with col_up:
    uploaded = st.file_uploader(
        "\u2026or upload your own",
        type=["pdf"] + IMAGE_EXTS,
        help=f"PDF or image (PNG, JPEG, AVIF, WEBP\u2026) \u2014 max {MAX_FILE_SIZE_MB} MB",
    )

# Resolve the active input (an upload takes priority over the picker).
src_bytes: bytes | None = None
src_name = ""
if uploaded is not None:
    src_bytes = uploaded.read()
    src_name = uploaded.name
elif local_choice:
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
st.markdown("#### 2 \u00b7 Compare")
disabled = not (src_bytes and endpoint)
if not endpoint:
    st.warning("Set your endpoint in the **Connection** panel (sidebar), then **Save**.")
elif not src_bytes:
    st.info("Pick a curated sample or upload a file above.")

if st.button(
    "\U0001f504 Compare both models",
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
