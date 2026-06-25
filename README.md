# Mistral Document AI on Azure — OCR 4.0 vs v25.12 (OCR demo on Microsoft Foundry)

Standalone, self-contained project demonstrating **Mistral Document AI** OCR deployed and served through **Microsoft Foundry**.

This project leverages **Microsoft Foundry** as the hosting platform to deploy Mistral's Document AI models via the REST API. Both model versions are deployed as **GlobalStandard** SKU endpoints in the same Foundry project.

Extract text, tables, and images from PDF documents using Python. Supports both **v25.12** (table_format, header/footer extraction, enhanced annotations) and **OCR 4.0** (paragraph bounding boxes, block classification, inline confidence scores, 170 languages).

## Why Microsoft Foundry?

- **Managed deployment** — deploy Mistral models with a single CLI command, no infrastructure to manage
- **GlobalStandard SKU** — pay-per-token pricing with automatic scaling
- **Enterprise security** — Azure AD / Managed Identity authentication, VNET integration, private endpoints
- **Unified endpoint** — both model versions share the same Foundry account endpoint

## Available Models

| Model | Version | Deployment Name | Key Features |
|-------|---------|-----------------|-------------|
| Mistral Document AI 2512 | v25.12 | `mistral-document-ai-2512` | OCR, images, bbox annotations, `table_format`, `extract_header/footer` |
| Mistral Document AI OCR 4.0 | 4.0 (Preview) | `mistral-ocr-4-0` | + paragraph bounding boxes, block classification, inline confidence scores, 170 languages, streaming API |

> **OCR 4.0 requires a GlobalStandard (or DataZoneStandard) deployment** and is currently in **Preview**.

## v25.12 vs OCR 4.0 — Detailed Comparison

| Feature | v25.12 (`mistral-document-ai-2512`) | OCR 4.0 (`mistral-ocr-4-0`) |
|---------|----------------------------|----------------------------|
| **OCR engine** | `mistral-ocr-2512` + `mistral-small-2506` | `mistral-ocr-4-0` (+ Mistral Medium 3.5 annotations) |
| **Status** | GA | Preview |
| **Markdown output** | Yes | Yes |
| **Image extraction (bbox)** | Yes | Yes |
| **Paragraph bounding boxes** | No | Yes — per-paragraph layout coordinates |
| **Block classification** | No | Yes — title, header, footer, code, table, equation, paragraph, list, signature, image, caption, references |
| **Inline confidence scores** | No | Yes — per-page / per-word confidence |
| **Hyperlink detection** | Yes | Yes |
| **`table_format` parameter** | `null` / `"markdown"` / `"html"` | `null` / `"markdown"` / `"markdown-tables"` / `"html"` (colspan/rowspan) |
| **`extract_header` / `extract_footer`** | Yes | Yes |
| **`pages` selection** | Yes — select specific pages (0-indexed) | Yes |
| **`image_limit`** | Yes | Yes |
| **BBox / Document annotations** | JSON Schema structured output | JSON Schema structured output |
| **Streaming API** | No | Yes — redesigned, reduced time-to-first-token |
| **Multilingual accuracy** | 99%+ across 25+ languages | **170 languages** |
| **Supported formats** | PDF, PNG, JPEG, AVIF, PPTX, DOCX | PDF, PNG, JPEG, AVIF, PPTX, DOCX |
| **Deployment SKU** | GlobalStandard | GlobalStandard / DataZoneStandard |
| **Pricing (Global Standard)** | per Foundry pricing | $4 / 1K pages (OCR) · $5 / 1K pages (OCR + annotations) |

> **Note**: `table_format`, `extract_header`, and `extract_footer` parameters are available with **OCR 2512 and OCR 4.0** ([source](https://docs.mistral.ai/capabilities/document_ai/basic_ocr)).

### API Limits (Microsoft Foundry)

| Limit | Value | Notes |
|-------|-------|-------|
| **Max file size** | **30 MB** per request | Applies to both v25.12 and OCR 4.0 on Microsoft Foundry |
| **Max pages per request** | **30 pages** | Documents >30 pages are auto-chunked by this project |
| **Annotations page limit** | **8 pages** | `document_annotation` processes only the first 8 pages |
| **Supported input formats** | PDF, PNG, JPEG, AVIF, PPTX, DOCX | Images count as 1 page |

> Documents exceeding 30 pages are automatically split into chunks and processed sequentially — results are merged transparently. See [Large PDFs](#large-pdfs-30-pages) below.

## Documentation & Resources

### Mistral Documentation

- [Document AI — Overview](https://docs.mistral.ai/capabilities/document_ai) — capabilities and model overview
- [Document AI — OCR Processor](https://docs.mistral.ai/capabilities/document_ai/basic_ocr) — OCR API reference, parameters, and code examples
- [Document AI — Annotations](https://docs.mistral.ai/capabilities/document_ai/annotations) — structured extraction, bbox/document annotations, JSON schemas
- [Document AI — Document Q&A](https://docs.mistral.ai/capabilities/document_ai/document_qna) — question answering on documents
- [OCR API Reference](https://docs.mistral.ai/api/endpoint/ocr) — REST API endpoint specification

### Microsoft Foundry

- [Microsoft Foundry documentation](https://learn.microsoft.com/azure/ai-services/)
- [Mistral Document AI OCR 4.0 — Azure Model Card](https://ai.azure.com/catalog/models/mistral-ocr-4-0)
- [Mistral Document AI 2512 — Azure Model Card](https://ai.azure.com/explore/models/mistral-document-ai-2512/version/1/registry/azureml-mistral)
- [Mistral Document AI with OCR 4 and Mistral Medium 3.5 arrive in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/mistral-document-ai-with-ocr-4-and-mistral-medium-3-5-arrive-in-microsoft-foundr/4529863) — official announcement
- [Mistral OCR 4 — release announcement](https://mistral.ai/news/ocr-4/)
- [Unlocking Document Understanding with Mistral Document AI in Microsoft Foundry](https://azurefeeds.com/2025/06/24/unlocking-document-understanding-with-mistral-document-ai-in-microsoft-foundry/) — community walkthrough

### Cookbooks

- [Data Extraction with Structured Outputs](https://colab.research.google.com/github/mistralai/cookbook/blob/main/mistral/ocr/data_extraction.ipynb)
- [Tool Use with OCR](https://colab.research.google.com/github/mistralai/cookbook/blob/main/mistral/ocr/tool_usage.ipynb)
- [Batch OCR](https://colab.research.google.com/github/mistralai/cookbook/blob/main/mistral/ocr/batch_ocr.ipynb)

## Project Structure

```text
mistral-document-ai/
  pyproject.toml              # uv / pip dependencies (Streamlit >= 1.58)
  .env.example                # Configuration template
  .streamlit/
    config.toml               # Azure + Mistral whole-UI theme (+ toolbarMode minimal)
  app.py                      # Streamlit multipage UI: Extract / Compare models / Model comparison
  demo_ocr.ipynb              # Jupyter notebook walkthrough
  src/
    extract.py                # Core OCR client (async, REST, multi-model)
  scripts/
    deploy_all.ps1            # Deploy both models + auto-generate .env
    deploy_all.sh             # Deploy both models (Bash)
    setup_env.ps1             # Resolve existing deployments → .env
    setup_env.sh              # Resolve existing deployments → .env (Bash)
    generate_sample_pdf.py    # Generate sample PDF with tables
  data/                       # Place your PDF files here
  extraction/                 # OCR output (markdown, CSV, JSON)
```

## Quick Start

### 1. Deploy Both Models

```powershell
# PowerShell - deploys both models and writes .env automatically
.\scripts\deploy_all.ps1 -AccountName "my-ai-foundry" -ResourceGroup "rg-demo"
```

```bash
# Bash
./scripts/deploy_all.sh --account-name "my-ai-foundry" --resource-group "rg-demo"
```

This creates `mistral-document-ai-2512` and `mistral-ocr-4-0` deployments and writes the `.env` file with endpoint, deployments, and API key.

### 2. Generate .env (if models already deployed)

If the models are already deployed, resolve all configuration automatically:

```powershell
# PowerShell
.\scripts\setup_env.ps1 -AccountName "my-ai-foundry" -ResourceGroup "rg-demo"
```

```bash
# Bash
./scripts/setup_env.sh --account-name "my-ai-foundry" --resource-group "rg-demo"
```

This discovers the endpoint, deployment names, and API key from your Foundry account and writes `.env`.

For Azure AD authentication (recommended for production), use `--auth aad` / `-AuthMode "aad"`.

Alternatively, copy and edit manually:

```bash
cp .env.example .env
# Edit .env with your endpoint and key
```

### 3. Install Dependencies

```bash
uv venv --python 3.12           # create a virtual environment with Python 3.12
# On Windows:  .venv\Scripts\activate
# On Linux/macOS:  source .venv/bin/activate
uv sync                          # install all dependencies
```

### 4. Generate Sample PDF (Optional)

```bash
uv sync --extra scripts          # installs matplotlib for chart generation
uv run python scripts/generate_sample_pdf.py
```

Creates `data/sample_complex_report.pdf` — a multi-page document with tables, plot charts (bar, line, pie), ASCII art diagrams, and mixed text sections.

### 5. Extract PDFs (CLI)

Place PDF files in `data/`, then:

```bash
uv run extract
```

Results (markdown + metadata JSON + CSVs) appear in `extraction/`.

### 6. Jupyter Notebook

```bash
uv sync --extra notebook
uv run jupyter lab demo_ocr.ipynb
```

Interactive walkthrough: select model version, run OCR, view markdown, parse tables, inspect images, per-page analysis, annotations demo, and model comparison.

### 7. Streamlit UI

```bash
uv run streamlit run app.py
```

> Requires **Streamlit >= 1.58** (latest GA). The pin lives in `pyproject.toml`; run `uv sync`
> (or `pip install -e .`) to upgrade an existing environment.

A **custom-branded, multipage** web app that compares **two** Mistral Document AI models —
**OCR 4.0** and **v25.12** — side by side on Microsoft Foundry. The **whole UI** is themed with the
**Microsoft Azure** (`#0078D4`) and **Mistral AI** (flame `#FF6A13`) palettes via
`.streamlit/config.toml` (tinted app background + branded sidebar) plus targeted CSS. The top-bar
**Deploy** button and developer menu are hidden (`[client] toolbarMode = "minimal"`).

#### Navigation (left sidebar)

Built with **`st.navigation`** (the current Streamlit multipage pattern) — three logical pages:

| Page | Purpose |
|------|---------|
| 🔍 **Extract** | Run a **single** model (OCR 4.0 *or* v25.12) and explore the full result — overview, markdown, tables, images, per-page, annotations, raw JSON. |
| ⚖️ **Compare models** | Run **both** models on the same PDF and compare them **side by side**. |
| 📊 **Model comparison** | Static **feature / limits / parameters / pricing** reference (moved out of the viewport into its own page). |

Shared **Connection** (endpoint + key) and collapsible **OCR options** (model, advanced extraction,
OCR 4.0 features, annotations) live in the sidebar and persist as you switch pages.

#### Highlights

- **Branded page heroes** — each page has an Azure → Mistral gradient hero that makes the two-model
  comparison explicit.
- **Sample document viewer** — when you upload or pick a PDF, the app shows it inline in a native
  **`st.pdf`** viewer (Streamlit's built-in PDF component — no rasterization, no extra image libs)
  plus lightweight badges (page count, file size, and a `>30 pages → auto-chunked` hint) *before*
  extraction, so you can gauge how complex the document is.
- **⚖️ Live side-by-side comparison** — on the **Compare models** page, one click runs **both**
  OCR 4.0 **and** v25.12 and shows two columns: per-model metrics (latency, pages, words, tables,
  images, sections, blocks, confidence), scrollable rendered markdown, per-result download, and a
  consolidated diff table. Each model runs in its own `try/except`, so if OCR 4.0 is temporarily
  unavailable (Preview 503), the v25.12 column still renders.
- **Extract page** — rendered markdown with a raw-source toggle; table extraction with filtering,
  DataFrame display, and CSV download; image grid (base64); per-page breakdown with word counts,
  headers, footers; **Annotations** (bbox per-image + document-level); raw JSON; and save to
  `extraction/` (markdown, CSV, JSON).
- **OCR options** (sidebar): `table_format`, `extract_header`, `extract_footer`, `pages`,
  `image_limit`; OCR 4.0-only content blocks + bounding boxes (`include_blocks`) and inline
  confidence scores (`confidence_scores_granularity`).
- **Extraction history** in the sidebar.

## Authentication

Two options:

| Method       | Setup                                         |
| ------------ | --------------------------------------------- |
| **API Key**  | Set `AZURE_AI_KEY` in `.env`                  |
| **Azure AD** | Run `az login`, leave `AZURE_AI_KEY` empty    |

Azure AD (DefaultAzureCredential) is recommended for production.

## API Reference

The core OCR call is a single REST endpoint:

```text
POST {endpoint}/providers/mistral/azure/ocr?api-version=2024-05-01-preview
```

Request body:

```json
{
  "model": "mistral-document-ai-2512",
  "document": {
    "type": "document_url",
    "document_url": "data:application/pdf;base64,{base64_pdf}"
  },
  "include_image_base64": true,
  "table_format": "markdown",
  "extract_header": true,
  "extract_footer": true,
  "bbox_annotation_format": { "type": "json_schema", "json_schema": { "name": "ImageDescription", "schema": {...}, "strict": true } },
  "document_annotation_format": { "type": "json_schema", "json_schema": { "name": "DocumentSummary", "schema": {...}, "strict": true } },
  "document_annotation_prompt": "Summarize this document."
}
```

Response contains `pages[]` with `markdown`, `images[]`, `tables[]`, `hyperlinks[]`, `header`, `footer`, `dimensions` per page, plus top-level `document_annotation`. **OCR 4.0** additionally returns `pages[].blocks` (when `include_blocks` is set) and `pages[].confidence_scores` (when `confidence_scores_granularity` is set).

**OCR 4.0 example** (block classification + confidence scores):

```json
{
  "model": "mistral-ocr-4-0",
  "document": { "type": "document_url", "document_url": "data:application/pdf;base64,{base64_pdf}" },
  "include_blocks": true,
  "confidence_scores_granularity": "page"
}
```


### Advanced Features (v25.12 / OCR 4.0)

These parameters are supported with **`mistral-document-ai-2512`** and **`mistral-ocr-4-0`**.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `table_format` | `"markdown"` \| `"html"` \| `null` | `null` | Structured table output format (see below) |
| `extract_header` | `bool` | `false` | Extract page headers into a separate `header` field |
| `extract_footer` | `bool` | `false` | Extract page footers into a separate `footer` field |
| `pages` | `list[int]` | all pages | Select specific pages to process (0-indexed) |
| `image_limit` | `int` | unlimited | Maximum number of images to return across the document |
| `include_blocks` | `bool` | `false` | **OCR 4.0 only** — return content blocks with bounding boxes + type classification into `pages[].blocks` |
| `confidence_scores_granularity` | `"page"` \| `"word"` \| `null` | `null` | **OCR 4.0 only** — return inline confidence scores into `pages[].confidence_scores` |

#### `table_format` — structured table output

Controls how tables are returned in the response:

| Value | Behaviour |
|-------|-----------|
| `null` (default) | Tables are embedded **inline** in the page markdown as pipe tables (`\| col \| col \|`) |
| `"markdown"` | Tables are **also** returned as separate entries in `pages[].tables[]`, each containing a `markdown` key with a standalone markdown table. Useful for programmatic extraction. |
| `"html"` | Same as above, but each table entry contains an `html` key with a `<table>` element — preserves `colspan`, `rowspan`, and merged cells better than markdown. |

> When `table_format` is set, tables still appear inline in `pages[].markdown`, but are additionally structured in `pages[].tables[]` for easier downstream parsing.

#### `extract_header` / `extract_footer`

When enabled, each page in the response includes:

- `header` — the repeated header text at the top of the page (e.g. document title, chapter name)
- `footer` — the repeated footer text (e.g. page numbers, disclaimers, confidentiality notices)

These are returned as plain strings in `pages[].header` and `pages[].footer`. If a page has no header/footer, the field is `null`.

#### `pages` — selective extraction

Pass a list of **0-indexed** page numbers to extract only specific pages:

```json
{ "pages": [0, 2, 4] }
```

This extracts pages 1, 3, and 5 only — useful for large documents where you only need certain sections.

#### `image_limit`

Caps the total number of images returned across all pages. Useful to reduce response size when you only need the text/tables. Set to `0` or omit to return all images.

#### `include_blocks` — content blocks (OCR 4.0)

**OCR 4.0 only.** When `true`, each page returns a `blocks` array of paragraph-level
content blocks, each with a **bounding box** and a **type classification** (title,
paragraph, table, equation, signature, list, caption, ...):

```json
{ "include_blocks": true }
```

```json
"blocks": [
  { "type": "title",     "bbox": [x0, y0, x1, y1], "content": "...", "confidence": 0.98 },
  { "type": "paragraph", "bbox": [x0, y0, x1, y1], "content": "...", "confidence": 0.95 }
]
```

Ideal for **layout-aware pipelines, semantic chunking (RAG), and citation management**.
Older models (v25.12) return `blocks` as `null`.

#### `confidence_scores_granularity` — inline confidence (OCR 4.0)

**OCR 4.0 only.** Set to `"page"` or `"word"` to return inline confidence scores into
`pages[].confidence_scores`. Use it for **human-in-the-loop QA** and **automated error
flagging** (e.g. route low-confidence pages for review). `"word"` is the most detailed
(and the largest response). Older models return `confidence_scores` as `null`.

```json
{ "confidence_scores_granularity": "page" }
```

---

### Annotations

Annotations use **JSON Schema** to extract structured data from images (bbox) or the entire document.

| Parameter | Type | Description |
|-----------|------|-------------|
| `bbox_annotation_format` | JSON Schema | Applied to **each image** — classify and describe individual images |
| `document_annotation_format` | JSON Schema | Applied to the **entire document** — extract a structured summary |
| `document_annotation_prompt` | `string` | Optional prompt guiding the document-level annotation |

> **Limit**: Annotations are processed on the **first 8 pages** only (both Azure and La Plateforme).

#### How annotations work

**1. BBox annotations** (`bbox_annotation_format`) — per-image structured extraction:

You provide a JSON Schema describing what you want extracted from each image. Mistral applies it to every image found in the document and returns the structured result alongside the image data.

```json
{
  "bbox_annotation_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "ImageDescription",
      "schema": {
        "type": "object",
        "properties": {
          "image_type": { "type": "string", "description": "Type: bar chart, photo, logo, table, etc." },
          "summary": { "type": "string", "description": "Brief summary of image content" },
          "is_relevant": { "type": "boolean", "description": "Whether this image is relevant" }
        },
        "required": ["image_type", "summary", "is_relevant"],
        "additionalProperties": false
      },
      "strict": true
    }
  }
}
```

Each image in `pages[].images[]` will then include the structured annotation fields alongside `image_base64` and `id`.

**2. Document annotations** (`document_annotation_format` + `document_annotation_prompt`) — whole-document extraction:

You provide a JSON Schema for the entire document. Mistral reads all content (text + images) and returns a single structured object.

```json
{
  "document_annotation_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "DocumentSummary",
      "schema": {
        "type": "object",
        "properties": {
          "topics": { "type": "array", "items": { "type": "string" }, "description": "Key topics" },
          "entities": { "type": "array", "items": { "type": "string" }, "description": "Named entities" },
          "summary": { "type": "string", "description": "One-paragraph summary" }
        },
        "required": ["topics", "entities", "summary"],
        "additionalProperties": false
      },
      "strict": true
    }
  },
  "document_annotation_prompt": "Summarize this document with key topics and entities."
}
```

The result is returned in the top-level `document_annotation` field of the response.

**Practical uses**: document classification, invoice field extraction, contract clause detection, chart-to-table conversion, compliance tagging.

## Large PDFs (>30 pages)

Documents over 30 pages are automatically split into chunks and processed in sequence. Results are merged transparently.

## Requirements

- Python 3.12+
- **Streamlit >= 1.58** (latest GA) for the web UI — `numpy >= 2` with `pandas >= 2.2.2,<3`
- **Microsoft Azure subscription** with a [Microsoft Foundry](https://learn.microsoft.com/azure/ai-services/) account
- Mistral Document AI models deployed via `scripts/deploy_all.ps1` / `scripts/deploy_all.sh`
- `az` CLI logged in (`az login`)
- `uv` package manager (or `pip install -e .`)
