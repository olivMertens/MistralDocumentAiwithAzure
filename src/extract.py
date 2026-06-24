"""Mistral Document AI OCR client — standalone REST implementation."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path

import httpx
from collections.abc import Callable
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models for structured image annotations
# ---------------------------------------------------------------------------

class ImageDescription(BaseModel):
    """Structured description returned by Mistral bbox annotation."""
    image_type: str = Field(..., description="Type of image (bar chart, photo, logo, table, etc.)")
    summary: str = Field(..., description="Brief summary of image content.")
    details: str = Field(..., description="Key data points or text visible in the image.")
    is_relevant: bool = Field(..., description="Whether this image is relevant to the document context.")


class OCRPage(BaseModel):
    """Single page result from Mistral Document AI."""
    page_index: int
    markdown: str
    images: list[dict] = []
    tables: list[dict] = []
    hyperlinks: list[dict] = []
    header: str | None = None
    footer: str | None = None
    dimensions: dict = {}


class OCRResult(BaseModel):
    """Complete OCR result across all pages."""
    model: str = ""
    markdown: str
    pages: list[OCRPage]
    images: list[dict] = []
    usage: dict = {}
    elapsed_ms: float = 0.0
    document_annotation: dict | str | None = None


# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

MODELS: dict[str, dict] = {
    "2505": {
        "label": "v25.05",
        "description": "Mistral Document AI (May 2025) - baseline OCR",
        "env_var": "MISTRAL_DEPLOYMENT",
        "default_deployment": "mistral-document-ai-2505",
        "version": "25.05",
    },
    "2512": {
        "label": "v25.12",
        "description": "Mistral Document AI (Dec 2025) - table_format, headers/footers",
        "env_var": "MISTRAL_DEPLOYMENT_2512",
        "default_deployment": "mistral-document-ai-2512",
        "version": "25.12",
    },
}


# Supported image input formats → MIME type (Mistral OCR accepts these as image_url).
SUPPORTED_IMAGE_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def get_deployment_name(model_key: str = "2505") -> str:
    """Resolve deployment name from model key via env var or default."""
    info = MODELS.get(model_key)
    if not info:
        raise ValueError(f"Unknown model_key '{model_key}'. Choose from: {list(MODELS)}")
    return os.getenv(info["env_var"], info["default_deployment"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def _get_auth_headers(api_key: str | None = None) -> dict:
    """Build authentication headers.

    - If api_key is provided, use Bearer token directly.
    - Otherwise, use azure-identity DefaultAzureCredential.
    """
    if api_key:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    from azure.identity.aio import DefaultAzureCredential

    credential = DefaultAzureCredential()
    try:
        token = await credential.get_token("https://cognitiveservices.azure.com/.default")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token.token}",
        }
    finally:
        await credential.close()


# ---------------------------------------------------------------------------
# Schema helper (Mistral expects wrapped JSON schema for bbox annotations)
# ---------------------------------------------------------------------------

def _pydantic_to_mistral_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("$defs", None)
    schema.setdefault("additionalProperties", False)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model.__name__,
            "schema": schema,
            "strict": True,
        },
    }


# ---------------------------------------------------------------------------
# PDF splitting for large documents (>30 pages)
# ---------------------------------------------------------------------------

def _split_pdf_bytes(pdf_data: bytes, max_pages: int = 30) -> list[str]:
    """Split PDF into base64-encoded chunks of ≤max_pages."""
    import fitz

    doc = fitz.open(stream=pdf_data, filetype="pdf")
    chunks: list[str] = []
    for start in range(0, len(doc), max_pages):
        sub = fitz.open()
        sub.insert_pdf(doc, from_page=start, to_page=min(len(doc) - 1, start + max_pages - 1))
        chunks.append(base64.b64encode(sub.tobytes()).decode())
        sub.close()
    doc.close()
    return chunks


def _looks_like_pdf(data: bytes, filename: str) -> bool:
    """Detect whether the input is a PDF (by extension or magic bytes)."""
    if filename.lower().endswith(".pdf"):
        return True
    return data[:5].startswith(b"%PDF")


def _image_mime(filename: str) -> str:
    """Resolve the image MIME type from a filename extension (defaults to PNG)."""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    return SUPPORTED_IMAGE_MIME.get(ext, "image/png")


# ---------------------------------------------------------------------------
# Core OCR function
# ---------------------------------------------------------------------------

async def ocr_document(
    data: bytes,
    filename: str = "document.pdf",
    *,
    endpoint: str | None = None,
    deployment: str | None = None,
    model_key: str | None = None,
    api_version: str | None = None,
    api_key: str | None = None,
    include_images: bool = False,
    max_retries: int = 3,
    # v25.12 features
    table_format: str | None = None,
    extract_header: bool = False,
    extract_footer: bool = False,
    pages: list[int] | None = None,
    image_limit: int | None = None,
    # Annotations
    bbox_annotation_format: dict | None = None,
    document_annotation_format: dict | None = None,
    document_annotation_prompt: str | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> OCRResult:
    """
    Extract text (markdown) from a PDF *or* image using Mistral Document AI REST API.

    Accepts raw bytes so it works equally well with uploaded files and on-disk files.
    PDFs use the ``document_url`` chunk (auto-chunked over 30 pages); images
    (PNG/JPEG/AVIF/...) use the ``image_url`` chunk.

    Args:
        data: Raw bytes of the document (PDF) or image.
        filename: Original filename — used to detect type (PDF vs image) and MIME.
        endpoint: Microsoft Foundry endpoint URL.
        deployment: Model deployment name (overrides model_key).
        model_key: Model catalog key ("2505" or "2512"). Ignored if deployment is set.
        api_version: API version string.
        api_key: Optional API key (uses DefaultAzureCredential if empty).
        include_images: Request base64 image data in response.
        max_retries: Number of retries on transient failures.
        table_format: "markdown", "html", or None (v25.12+).
        extract_header: Extract page headers (v25.12+).
        extract_footer: Extract page footers (v25.12+).
        pages: List of 0-based page indices to process.
        image_limit: Maximum number of images to return.
        bbox_annotation_format: JSON-schema dict for per-image structured annotations.
        document_annotation_format: JSON-schema dict for whole-document annotation.
        document_annotation_prompt: Prompt for document-level annotation.

    Returns:
        OCRResult with markdown text, per-page data, and image metadata.
    """
    endpoint = endpoint or os.getenv("MISTRAL_ENDPOINT", "")
    if deployment:
        resolved_deployment = deployment
    elif model_key:
        resolved_deployment = get_deployment_name(model_key)
    else:
        resolved_deployment = os.getenv("MISTRAL_DEPLOYMENT", "mistral-document-ai-2505")
    api_version = api_version or os.getenv("MISTRAL_API_VERSION", "2024-05-01-preview")
    api_key = api_key or os.getenv("AZURE_AI_KEY", "")

    if not endpoint:
        raise RuntimeError(
            "MISTRAL_ENDPOINT not set. Provide it as argument or in .env / environment."
        )

    # Build URL
    base = endpoint.rstrip("/")
    if not base.endswith("/providers/mistral/azure/ocr"):
        base = f"{base}/providers/mistral/azure/ocr"
    url = f"{base}?api-version={api_version}"

    headers = await _get_auth_headers(api_key or None)

    is_pdf = _looks_like_pdf(data, filename)

    def _build_payload(document: dict) -> dict:
        payload: dict = {
            "model": resolved_deployment,
            "document": document,
            "include_image_base64": include_images,
        }
        # v25.12 features
        if table_format:
            payload["table_format"] = table_format
        if extract_header:
            payload["extract_header"] = True
        if extract_footer:
            payload["extract_footer"] = True
        if pages is not None:
            payload["pages"] = pages
        if image_limit is not None:
            payload["image_limit"] = image_limit
        # Annotations
        if bbox_annotation_format:
            payload["bbox_annotation_format"] = bbox_annotation_format
        if document_annotation_format:
            payload["document_annotation_format"] = document_annotation_format
        if document_annotation_prompt:
            payload["document_annotation_prompt"] = document_annotation_prompt
        return payload

    payloads: list[dict] = []
    if is_pdf:
        # Build PDF payloads (chunk if >30 pages)
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        page_count = len(doc)
        doc.close()

        if progress_callback:
            progress_callback(0.15, f"{page_count} page(s) detected")

        def _pdf_doc(b64: str) -> dict:
            return {"type": "document_url", "document_url": f"data:application/pdf;base64,{b64}"}

        if page_count > 30:
            for chunk_b64 in _split_pdf_bytes(data, max_pages=30):
                payloads.append(_build_payload(_pdf_doc(chunk_b64)))
        else:
            payloads.append(_build_payload(_pdf_doc(base64.b64encode(data).decode())))
    else:
        # Single image input → image_url chunk (no chunking; an image is one page).
        mime = _image_mime(filename)
        if progress_callback:
            progress_callback(0.15, f"image input ({mime})")
        img_b64 = base64.b64encode(data).decode()
        payloads.append(
            _build_payload({"type": "image_url", "image_url": f"data:{mime};base64,{img_b64}"})
        )

    # Execute requests
    all_pages: list[OCRPage] = []
    all_images: list[dict] = []
    total_usage: dict = {}
    doc_annotation = None
    t0 = time.perf_counter()

    async with httpx.AsyncClient(timeout=120) as client:
        for payload_idx, payload in enumerate(payloads):
            if progress_callback:
                pct = 0.2 + (payload_idx / len(payloads)) * 0.7
                progress_callback(pct, f"Processing chunk {payload_idx + 1}/{len(payloads)}...")
            last_error: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"OCR request chunk={payload_idx} attempt={attempt}/{max_retries}")
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()

                    pages_raw = data.get("pages", [])
                    usage = data.get("usage", {})

                    for k, v in usage.items():
                        total_usage[k] = total_usage.get(k, 0) + v

                    # Capture document-level annotation
                    if data.get("document_annotation"):
                        doc_annotation = data["document_annotation"]

                    for pg_idx, page in enumerate(pages_raw):
                        md = page.get("markdown", "")
                        imgs = page.get("images", [])
                        global_idx = len(all_pages)
                        all_pages.append(OCRPage(
                            page_index=global_idx,
                            markdown=md,
                            images=imgs,
                            tables=page.get("tables", []),
                            hyperlinks=page.get("hyperlinks", []),
                            header=page.get("header"),
                            footer=page.get("footer"),
                            dimensions=page.get("dimensions", {}),
                        ))
                        for img in imgs:
                            img["page_index"] = global_idx
                            all_images.append(img)

                    last_error = None
                    if progress_callback:
                        pct = 0.2 + ((payload_idx + 1) / len(payloads)) * 0.7
                        progress_callback(pct, f"Chunk {payload_idx + 1}/{len(payloads)} complete")
                    break  # success

                except httpx.HTTPStatusError as e:
                    last_error = e
                    status = e.response.status_code
                    if status in (429, 500, 502, 503, 504):
                        wait = 2 ** attempt
                        logger.warning(f"OCR {status}, retrying in {wait}s...")
                        await asyncio.sleep(wait)
                    else:
                        raise
                except httpx.TimeoutException as e:
                    last_error = e
                    wait = 2 ** attempt
                    logger.warning(f"OCR timeout, retrying in {wait}s...")
                    await asyncio.sleep(wait)

            if last_error is not None:
                raise last_error

    elapsed = (time.perf_counter() - t0) * 1000
    combined_md = "\n\n".join(p.markdown for p in all_pages)

    return OCRResult(
        model=resolved_deployment,
        markdown=combined_md,
        pages=all_pages,
        images=all_images,
        usage=total_usage,
        elapsed_ms=elapsed,
        document_annotation=doc_annotation,
    )


async def ocr_pdf(pdf_path: str | Path, **kwargs) -> OCRResult:
    """Backward-compatible wrapper: OCR a file on disk (PDF or image).

    Reads the file and delegates to :func:`ocr_document`. All keyword arguments
    are forwarded unchanged.
    """
    pdf_path = Path(pdf_path)
    return await ocr_document(pdf_path.read_bytes(), pdf_path.name, **kwargs)


async def compare_models(
    data: bytes,
    filename: str,
    *,
    model_keys: tuple[str, ...] = ("2505", "2512"),
    endpoint: str | None = None,
    api_key: str | None = None,
    include_images: bool = False,
    table_format: str | None = None,
    extract_header: bool = False,
    extract_footer: bool = False,
) -> dict[str, OCRResult | Exception]:
    """Run the same input through several models concurrently for comparison.

    v25.12-only parameters (``table_format``, ``extract_header``, ``extract_footer``)
    are applied only to the ``2512`` model. Returns a mapping of model key →
    ``OCRResult`` (or the raised ``Exception`` if that model failed, so one failure
    does not hide the other model's result).
    """

    async def _one(mk: str) -> OCRResult:
        is_2512 = MODELS.get(mk, {}).get("version", "").startswith("25.12") or mk == "2512"
        return await ocr_document(
            data,
            filename,
            endpoint=endpoint,
            model_key=mk,
            api_key=api_key,
            include_images=include_images,
            table_format=table_format if is_2512 else None,
            extract_header=extract_header if is_2512 else False,
            extract_footer=extract_footer if is_2512 else False,
        )

    results = await asyncio.gather(
        *[_one(mk) for mk in model_keys], return_exceptions=True
    )
    return dict(zip(model_keys, results))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    """CLI: extract markdown from PDFs in data/ and save to extraction/."""
    import asyncio
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    # Load .env if present
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    data_dir = Path(__file__).resolve().parent.parent / "data"
    out_dir = Path(__file__).resolve().parent.parent / "extraction"
    out_dir.mkdir(exist_ok=True)

    pdfs = sorted(data_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {data_dir}")
        sys.exit(1)

    async def run():
        for pdf in pdfs:
            print(f"\n{'='*60}")
            print(f"Processing: {pdf.name}")
            print(f"{'='*60}")
            result = await ocr_pdf(pdf, include_images=True)

            # Save markdown
            md_path = out_dir / f"{pdf.stem}.md"
            md_path.write_text(result.markdown, encoding="utf-8")
            print(f"  Markdown saved: {md_path.name} ({len(result.markdown)} chars)")

            # Save JSON metadata
            meta_path = out_dir / f"{pdf.stem}_meta.json"
            meta = {
                "source": pdf.name,
                "pages": len(result.pages),
                "images": len(result.images),
                "usage": result.usage,
                "elapsed_ms": round(result.elapsed_ms, 1),
                "per_page": [
                    {
                        "page": p.page_index,
                        "chars": len(p.markdown),
                        "images": len(p.images),
                    }
                    for p in result.pages
                ],
            }
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  Metadata saved: {meta_path.name}")
            print(f"  Pages: {len(result.pages)}, Images: {len(result.images)}")
            print(f"  Tokens: {result.usage}")
            print(f"  Time: {result.elapsed_ms:.0f}ms")

    asyncio.run(run())


if __name__ == "__main__":
    main()
