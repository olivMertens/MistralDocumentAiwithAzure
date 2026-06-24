# Mistral Document AI — OCR & Model Comparison Demo

Standalone, self-contained project demonstrating **Mistral Document AI** OCR deployed and served through **Microsoft Foundry**.

This project leverages **Microsoft Foundry** as the hosting platform to deploy Mistral's Document AI models via the REST API. Both model versions are deployed as **GlobalStandard** SKU endpoints in the same Foundry project.

Extract text, tables, and images from PDFs **and images** using Python, and compare **v25.05** (baseline) vs **v25.12** (table_format, header/footer extraction, enhanced annotations) **side-by-side** — built to show the difference on **handwriting** and **multilingual** documents (EN/FR/ES/DE/IT and 中文/日本語/한국어). Paste your endpoint + key once in the UI (saved in your browser), click **Test**, pick a sample, and **Compare**.

## Why Microsoft Foundry?

- **Managed deployment** — deploy Mistral models with a single CLI command, no infrastructure to manage
- **GlobalStandard SKU** — pay-per-token pricing with automatic scaling
- **Enterprise security** — Azure AD / Managed Identity authentication, VNET integration, private endpoints
- **Unified endpoint** — both model versions share the same Foundry account endpoint

## Available Models

| Model | Version | Deployment Name | Key Features |
|-------|---------|-----------------|-------------|
| Mistral Document AI 2505 | v25.05 | `mistral-document-ai-2505` | OCR, images, bbox annotations |
| Mistral Document AI 2512 | v25.12 | `mistral-document-ai-2512` | + `table_format`, `extract_header/footer`, enhanced accuracy |

## v25.05 vs v25.12 — Detailed Comparison

| Feature | v25.05 (`mistral-ocr-2505`) | v25.12 (`mistral-ocr-2512`) |
|---------|----------------------------|----------------------------|
| **OCR engine** | `mistral-ocr-2505` | `mistral-ocr-2512` + `mistral-small-2506` |
| **Markdown output** | Yes | Yes |
| **Image extraction (bbox)** | Yes | Yes |
| **Hyperlink detection** | Yes | Yes |
| **Complex layouts** | Basic multi-column | Advanced multi-column, mixed content |
| **`table_format` parameter** | No (tables inline in markdown) | `null` / `"markdown"` / `"html"` — structured table output |
| **`extract_header`** | No | Yes — extract page headers separately |
| **`extract_footer`** | No | Yes — extract page footers separately |
| **`pages` selection** | No — processes all pages | Yes — select specific pages (0-indexed) |
| **`image_limit`** | No | Yes — limit number of returned images |
| **BBox annotations** | JSON Schema structured output | JSON Schema structured output |
| **Document annotations** | JSON Schema structured output | JSON Schema structured output + `document_annotation_prompt` |
| **Document classification** | Via annotations | Via annotations (improved accuracy) |
| **Chart-to-table conversion** | Via bbox annotation | Via bbox annotation (enhanced) |
| **Handwriting support** | Basic | Improved |
| **Supported formats** | PDF, PNG, JPEG, AVIF, PPTX, DOCX | PDF, PNG, JPEG, AVIF, PPTX, DOCX |
| **Batch inference** | Yes | Yes |

> **Note**: `table_format`, `extract_header`, and `extract_footer` parameters are **only available with OCR 2512 or newer** ([source](https://docs.mistral.ai/capabilities/document_ai/basic_ocr)).

### API Limits (Microsoft Foundry)

| Limit | Value | Notes |
|-------|-------|-------|
| **Max file size** | **30 MB** per request | Applies to both v25.05 and v25.12 on Microsoft Foundry |
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
- [Mistral Document AI 2505 — Azure Model Card](https://ai.azure.com/explore/models/mistral-document-ai-2505/version/1/registry/azureml-mistral)
- [Mistral Document AI 2512 — Azure Model Card](https://ai.azure.com/explore/models/mistral-document-ai-2512/version/1/registry/azureml-mistral)

### Cookbooks

- [Data Extraction with Structured Outputs](https://colab.research.google.com/github/mistralai/cookbook/blob/main/mistral/ocr/data_extraction.ipynb)
- [Tool Use with OCR](https://colab.research.google.com/github/mistralai/cookbook/blob/main/mistral/ocr/tool_usage.ipynb)
- [Batch OCR](https://colab.research.google.com/github/mistralai/cookbook/blob/main/mistral/ocr/batch_ocr.ipynb)

## Project Structure

```text
mistral-document-ai/
  pyproject.toml              # uv / pip dependencies
  .env.example                # Configuration template
  app.py                      # Streamlit UI (model selector + annotations)
  pages/
    1_Compare_Models.py       # Side-by-side v25.05 vs v25.12 comparison viewport
  demo_ocr.ipynb              # Jupyter notebook walkthrough
  src/
    extract.py                # Core OCR client (async, REST, multi-model, PDF + images)
  scripts/
    deploy_all.ps1            # Deploy both models + auto-generate .env
    deploy_all.sh             # Deploy both models (Bash)
    setup_env.ps1             # Resolve existing deployments → .env
    setup_env.sh              # Resolve existing deployments → .env (Bash)
    generate_sample_pdf.py    # Generate sample PDF with tables
    generate_sample_images.py # Generate multilingual printed + handwriting samples
  data/                       # Place your PDF / image files here
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

This creates `mistral-document-ai-2505` and `mistral-document-ai-2512` deployments and writes the `.env` file with endpoint, deployments, and API key.

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
uv sync --group scripts          # installs matplotlib for chart generation
uv run python scripts/generate_sample_pdf.py
```

Creates `data/sample_complex_report.pdf` — a multi-page document with tables, plot charts (bar, line, pie), ASCII art diagrams, and mixed text sections.

#### Sample images (multilingual printed + handwriting)

For the **model comparison** view, generate a curated set of images ranging from easy to
very hard — including **handwriting in five languages** (EN/FR/ES/DE/IT with accents) and
**printed CJK** (中文/日本語/한국어):

```bash
uv run python scripts/generate_sample_images.py
```

Creates `data/sample_*.png` (printed note, handwriting per language, CJK printed, and a
deliberately messy "doctor's note"). They populate the "Compare Models" sample picker —
sorted easy → very hard — so the v25.05 → v25.12 handwriting/multilingual improvement is
easy to demo. Samples whose font isn't installed are skipped gracefully.

### 5. Extract PDFs (CLI)

Place PDF files in `data/`, then:

```bash
uv run extract
```

Results (markdown + metadata JSON + CSVs) appear in `extraction/`.

### 6. Jupyter Notebook

```bash
uv sync --group notebook
uv run jupyter lab demo_ocr.ipynb
```

Interactive walkthrough: select model version, run OCR, view markdown, parse tables, inspect images, per-page analysis, annotations demo, and model comparison.

### 7. Streamlit UI

```bash
uv run streamlit run app.py
```

Web interface with:

- **Model selector**: Switch between v25.05 and v25.12
- PDF upload or pick from `data/`
- Side-by-side PDF viewer and extracted structure
- Rendered markdown with raw source toggle
- Table extraction with filtering, DataFrame display, and CSV download
- Image viewer with base64 rendering in grid layout
- Per-page breakdown with word counts, headers, footers
- **Annotations tab**: bbox annotations (per image) and document-level annotations
- v25.12 controls: table_format, extract_header, extract_footer
- Save results to `extraction/` (markdown, CSV, JSON)
- Extraction history in sidebar

The app is multipage — use the sidebar to switch between the main extractor and the
**Compare Models** page below.

### 8. Model Comparison view (v25.05 vs v25.12)

```bash
uv run streamlit run app.py
# then open "Compare Models" in the sidebar
```

A focused side-by-side **viewport** that runs the *same* input through both model versions
at once — ideal for clean demos of the accuracy and latency difference:

- **Browser-stored connection**: paste your **endpoint (DNS)** + **API key** once; they are
  saved in your browser's **local storage** and prefilled next time. Hit **Test** for an
  instant ✅/❌ connection check (and latency) before running anything.
- **One input, both models**: pick a **curated sample** (sorted easy → very hard, incl.
  multilingual handwriting) or upload your own PDF **or image**.
- **3-pane viewport**: source preview · v25.05 extraction · v25.12 extraction
- **Performance metrics**: per-model latency, word count, and character count (with deltas)
- **Word-level diff**: highlights exactly what v25.12 added or changed vs v25.05
- **Handwriting & multilingual**: both models run concurrently, so the comparison is fast and fair

> Tip: run `scripts/generate_sample_images.py` first, then pick a handwriting sample (e.g.
> French or the "doctor's note") to showcase the accuracy gap. Image inputs (PNG, JPEG,
> AVIF, WEBP, …) are sent to the OCR API as `image_url`; PDFs use `document_url`.
>
> ⚠️ The API key is stored in plain text in your browser's local storage — use a demo/dev key.

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

Response contains `pages[]` with `markdown`, `images[]`, `tables[]`, `hyperlinks[]`, `header`, `footer`, `dimensions` per page, plus top-level `document_annotation`.

### v25.12 Features

These parameters are **only supported with `mistral-document-ai-2512`** (v25.12). Sending them to v25.05 will have no effect or produce an error.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `table_format` | `"markdown"` \| `"html"` \| `null` | `null` | Structured table output format (see below) |
| `extract_header` | `bool` | `false` | Extract page headers into a separate `header` field |
| `extract_footer` | `bool` | `false` | Extract page footers into a separate `footer` field |
| `pages` | `list[int]` | all pages | Select specific pages to process (0-indexed) |
| `image_limit` | `int` | unlimited | Maximum number of images to return across the document |

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
- **Microsoft Azure subscription** with a [Microsoft Foundry](https://learn.microsoft.com/azure/ai-services/) account
- Mistral Document AI models deployed via `scripts/deploy_all.ps1` / `scripts/deploy_all.sh`
- `az` CLI logged in (`az login`)
- `uv` package manager (or `pip install -e .`)
