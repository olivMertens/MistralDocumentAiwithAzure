"""Generate a complex sample PDF with tables, charts, and images for OCR demo.

Usage:
    uv run python scripts/generate_sample_pdf.py

Creates data/sample_complex_report.pdf — a multi-page document with:
- Mixed text sections and headers
- Multiple tables with different structures (financial, technical, nested headers)
- Plot charts (bar, line, pie) rendered as images via matplotlib
- Mermaid diagrams (flowchart, sequence, class) rendered via mermaid.ink API
- ASCII art diagrams (architecture, flowchart)
- Bullet lists and numbered items
- A dense multi-column table spanning a full page
"""

from __future__ import annotations

import base64
import io
import tempfile
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from fpdf import FPDF


# ---------------------------------------------------------------------------
# Mermaid diagram renderer (returns PNG bytes via mermaid.ink)
# ---------------------------------------------------------------------------

def _render_mermaid(diagram: str) -> bytes | None:
    """Render a Mermaid diagram to PNG via the mermaid.ink public API."""
    encoded = base64.urlsafe_b64encode(diagram.encode()).decode()
    url = f"https://mermaid.ink/img/{encoded}?type=png"
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "image/png",
            "User-Agent": "Mozilla/5.0 (MistralDocAI/1.0)",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception as exc:
        print(f"  Warning: Mermaid rendering failed ({exc}), skipping diagram.")
        return None


# ---------------------------------------------------------------------------
# Mermaid diagram definitions
# ---------------------------------------------------------------------------

MERMAID_FLOWCHART = """
flowchart TD
    A[Upload PDF] --> B{File Valid?}
    B -->|Yes| C[Split into Chunks]
    B -->|No| D[Return Error]
    C --> E[Send to Mistral OCR API]
    E --> F[Parse Response]
    F --> G{Has Tables?}
    G -->|Yes| H[Extract Tables]
    G -->|No| I[Markdown Only]
    H --> J[Merge Results]
    I --> J
    J --> K[Return OCRResult]
"""

MERMAID_SEQUENCE = """
sequenceDiagram
    participant U as User
    participant S as Streamlit App
    participant E as Extract Module
    participant M as Mistral OCR API
    participant A as Microsoft Foundry

    U->>S: Upload PDF
    S->>S: Validate file size & format
    S->>E: ocr_pdf(file_bytes, model)
    E->>E: Split PDF into 30-page chunks
    loop Each Chunk
        E->>M: POST /ocr (base64 PDF)
        M->>A: Forward to model deployment
        A-->>M: OCR response (markdown + images)
        M-->>E: JSON response
    end
    E->>E: Merge chunk results
    E-->>S: OCRResult
    S->>S: Render tabs (Markdown, Tables, Images)
    S-->>U: Display results
"""

MERMAID_CLASS = """
classDiagram
    class OCRResult {
        +List~OCRPage~ pages
        +str model
        +float total_time
        +to_markdown() str
    }
    class OCRPage {
        +int index
        +str markdown
        +List~ImageDescription~ images
        +Dict dimensions
    }
    class ImageDescription {
        +str id
        +str base64
        +str description
    }
    OCRResult --> OCRPage : contains
    OCRPage --> ImageDescription : contains
"""


# ---------------------------------------------------------------------------
# Chart generators (return PNG bytes)
# ---------------------------------------------------------------------------

def _chart_bar_regions() -> bytes:
    """Bar chart: monthly cost by Azure region."""
    regions = ["West EU", "North EU", "East US", "SE Asia", "AU East", "UK South"]
    costs = [2340, 1120, 1950, 380, 1080, 920]
    colors = ["#0078d4", "#50e6ff", "#00bcf2", "#b4ec51", "#ffaa44", "#d83b01"]

    fig, ax = plt.subplots(figsize=(5.5, 3))
    bars = ax.bar(regions, costs, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_ylabel("Monthly Cost ($)")
    ax.set_title("Infrastructure Cost by Azure Region", fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("${x:,.0f}"))
    for bar, v in zip(bars, costs):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 40, f"${v:,}", ha="center", va="bottom", fontsize=7)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def _chart_line_accuracy() -> bytes:
    """Line chart: OCR accuracy trend over 6 months."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    printed = [99.0, 99.1, 99.2, 99.2, 99.3, 99.2]
    handwritten = [96.5, 96.8, 97.1, 97.4, 97.6, 97.8]
    tables = [98.5, 98.7, 98.8, 98.9, 99.0, 99.1]

    fig, ax = plt.subplots(figsize=(5.5, 3))
    ax.plot(months, printed, "o-", label="Printed", color="#0078d4", linewidth=2)
    ax.plot(months, handwritten, "s-", label="Handwritten", color="#d83b01", linewidth=2)
    ax.plot(months, tables, "^-", label="Tables", color="#107c10", linewidth=2)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("OCR Accuracy Trend (H1 2025)", fontsize=11, fontweight="bold")
    ax.set_ylim(95.5, 100)
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def _chart_pie_documents() -> bytes:
    """Pie chart: document type distribution."""
    labels = ["Invoice", "Purchase Order", "Delivery Note", "Contract",
              "Tax Document", "Bank Statement", "Correspondence", "Other"]
    sizes = [2345, 1890, 1456, 987, 1234, 876, 2430, 1629]
    colors = ["#0078d4", "#50e6ff", "#00bcf2", "#b4ec51",
              "#ffaa44", "#d83b01", "#8661c5", "#cccccc"]
    explode = [0.04] * len(labels)

    fig, ax = plt.subplots(figsize=(5, 3.5))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct="%1.1f%%", startangle=140, pctdistance=0.8,
        textprops={"fontsize": 7},
    )
    for t in autotexts:
        t.set_fontsize(6)
    ax.set_title("Document Type Distribution (12,847 docs)", fontsize=11, fontweight="bold")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def _chart_stacked_bar_tokens() -> bytes:
    """Stacked bar chart: token usage by model."""
    models = ["Mistral Doc AI", "GPT-4.1-mini", "GPT-4.1-nano"]
    input_tok = [8.23, 3.46, 1.23]
    output_tok = [2.15, 0.89, 0.35]

    fig, ax = plt.subplots(figsize=(4.5, 3))
    x = range(len(models))
    ax.bar(x, input_tok, label="Input Tokens", color="#0078d4")
    ax.bar(x, output_tok, bottom=input_tok, label="Output Tokens", color="#50e6ff")
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=8)
    ax.set_ylabel("Millions of Tokens")
    ax.set_title("Monthly Token Usage by Model", fontsize=11, fontweight="bold")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# ASCII art strings
# ---------------------------------------------------------------------------

ASCII_ARCHITECTURE = """\
+---------------------------------------------------------------------+
|                   DOCUMENT PROCESSING PIPELINE                      |
+---------------------------------------------------------------------+
|                                                                     |
|   +----------+     +-----------+     +------------+     +--------+  |
|   |  Upload  | --> |  Mistral  | --> |  Classify  | --> | Store  |  |
|   |  (Blob)  |     | Doc AI    |     | (GPT-4.1)  |     |(Cosmos)|  |
|   +----------+     +-----------+     +------------+     +--------+  |
|        |                |                  |                |       |
|        v                v                  v                v       |
|   +---------+     +-----------+     +------------+     +--------+  |
|   |  Queue  |     |  Extract  |     |  Annotate  |     | Index  |  |
|   | (SvcBus)|     |  Tables   |     |  (BBox)    |     |(Search)|  |
|   +---------+     +-----------+     +------------+     +--------+  |
|                                                                     |
+---------------------------------------------------------------------+
"""

ASCII_FLOWCHART = """\
          START
            |
            v
    +---------------+
    | Receive PDF   |
    +-------+-------+
            |
            v
    +---------------+       +------------------+
    | Pages <= 30?  |--No-->| Split into chunks|
    +-------+-------+       +--------+---------+
            |                        |
           Yes                       |
            |                        v
            +<-----------------------+
            |
            v
    +------------------+
    | Call Mistral OCR  |
    | (REST API)       |
    +--------+---------+
            |
            v
    +------------------+
    | Parse response   |
    | - markdown       |
    | - tables         |
    | - images         |
    +--------+---------+
            |
            v
    +------------------+        +------------------+
    | Annotations?     |--Yes-->| Apply JSON Schema|
    +--------+---------+        +--------+---------+
            |                            |
            No                           |
            |                            v
            +<---------------------------+
            |
            v
    +------------------+
    | Return OCRResult |
    +------------------+
            |
            v
          END
"""

ASCII_LOGO = """\
 __  __ _     _             _
|  \\/  (_)___| |_ _ __ __ _| |
| |\\/| | / __| __| '__/ _` | |
| |  | | \\__ \\ |_| | | (_| | |
|_|  |_|_|___/\\__|_|  \\__,_|_|
     ____                     _
    |  _ \\  ___   ___   _   _| |_ __ _ _
    | | | |/ _ \\ / __| | | | | __/ _` (_)
    | |_| | (_) | (__  | |_| | || (_| |_
    |____/ \\___/ \\___|  \\__,_|\\__\\__,_(_)
         _    ___
        / \\  |_ _|
       / _ \\  | |
      / ___ \\ | |
     /_/   \\_\\___|
"""


class ReportPDF(FPDF):
    """Custom A4 PDF with header/footer."""

    def header(self):
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 5, "Annual Infrastructure Compliance Report - INTERNAL", align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_title(self, title: str):
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def add_table(self, headers: list[str], rows: list[list[str]], col_widths: list[float]):
        """Draw a table with header row and data rows."""
        row_h = 6

        # Header
        self.set_font("Helvetica", "B", 7)
        self.set_fill_color(200, 200, 200)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], row_h, h, border=1, fill=True, align="C")
        self.ln(row_h)

        # Rows
        self.set_font("Helvetica", "", 7)
        self.set_fill_color(245, 245, 245)
        for r_idx, row in enumerate(rows):
            fill = r_idx % 2 == 1
            for i, cell in enumerate(row):
                w = col_widths[i] if i < len(col_widths) else col_widths[-1]
                self.cell(w, row_h, cell, border=1, fill=fill)
            self.ln(row_h)
        self.ln(3)

    def add_chart_image(self, png_bytes: bytes, w: float = 140):
        """Insert a matplotlib chart rendered as PNG."""
        tmp = Path(tempfile.mktemp(suffix=".png"))
        tmp.write_bytes(png_bytes)
        self.image(str(tmp), x=self.get_x(), y=self.get_y(), w=w)
        # Compute height from aspect ratio to advance cursor
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(png_bytes))
        aspect = img.height / img.width
        h = w * aspect
        self.set_y(self.get_y() + h + 4)
        tmp.unlink(missing_ok=True)

    def add_ascii_block(self, title: str, text: str, font_size: float = 6):
        """Insert a monospaced ASCII art block with a light background."""
        self.sub_title(title)
        self.set_font("Courier", "", font_size)
        self.set_fill_color(240, 240, 248)
        self.set_draw_color(180, 180, 200)

        lines = text.strip().split("\n")
        line_h = font_size * 0.5 + 1
        block_h = line_h * len(lines) + 4
        block_w = 190

        # Background rect
        y0 = self.get_y()
        self.rect(self.l_margin, y0, block_w, block_h, style="DF")
        self.set_y(y0 + 2)

        for line in lines:
            self.cell(block_w, line_h, line, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)


def build_pdf(output_path: str = "data/sample_complex_report.pdf") -> None:
    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ===== PAGE 1 — Title + Summary =====
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Annual Infrastructure Compliance Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, "Document Classification & OCR Performance Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "Report Date: 2025-06-15  |  Classification: INTERNAL  |  Version: 3.2", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    pdf.section_title("Executive Summary")
    pdf.body_text(
        "This report summarizes the infrastructure compliance status across all Azure regions. "
        "Key metrics include resource utilization rates, security posture scores, cost optimization "
        "opportunities, and SLA adherence. The OCR extraction pipeline processed 12,847 documents "
        "with a 99.2% accuracy rate on structured content and 97.8% on handwritten annotations."
    )
    pdf.body_text(
        "The Mistral Document AI model was deployed on Microsoft Foundry in West Europe, processing "
        "an average of 1,285 documents per day. Table extraction accuracy reached 99.1% on printed "
        "content. The multi-stage classification pipeline achieves an overall F1-score of 0.983 across "
        "10 document types."
    )

    pdf.sub_title("Table 1: Key Performance Indicators")
    pdf.add_table(
        ["KPI", "Target", "Actual", "Status", "Trend"],
        [
            ["OCR Accuracy (structured)", "99.0%", "99.2%", "PASS", "Improving"],
            ["OCR Accuracy (handwritten)", "95.0%", "97.8%", "PASS", "Stable"],
            ["Processing Time p95", "<5s", "3.2s", "PASS", "Improving"],
            ["Documents Processed/Day", "1,000", "1,285", "PASS", "Increasing"],
            ["Error Rate", "<1.0%", "0.3%", "PASS", "Decreasing"],
            ["API Availability", "99.9%", "99.97%", "PASS", "Stable"],
            ["Cost per Document", "<$0.05", "$0.032", "PASS", "Decreasing"],
            ["Model Drift Score", "<0.15", "0.08", "PASS", "Stable"],
        ],
        [52, 30, 30, 25, 30],
    )

    pdf.sub_title("Table 2: Regional Deployment Status")
    pdf.add_table(
        ["Region", "Status", "Instances", "CPU %", "Memory %", "Cost/mo"],
        [
            ["West Europe", "Active", "4", "62%", "71%", "$2,340"],
            ["North Europe", "Active", "2", "45%", "58%", "$1,120"],
            ["East US", "Active", "3", "78%", "82%", "$1,950"],
            ["Southeast Asia", "Standby", "1", "12%", "25%", "$380"],
            ["Australia East", "Active", "2", "55%", "63%", "$1,080"],
            ["UK South", "Migrating", "2", "31%", "44%", "$920"],
        ],
        [35, 25, 25, 20, 25, 25],
    )

    # ===== PAGE 2 — Dense financial table =====
    pdf.add_page()
    pdf.section_title("Section 2: Cost Analysis")

    pdf.sub_title("Table 3: Detailed Cost Breakdown by Service (Monthly)")
    pdf.add_table(
        ["Service", "SKU", "Qty", "Unit Price", "Subtotal", "Discount", "Net Cost", "vs Budget"],
        [
            ["Container Apps", "Consumption", "4", "$0.000012/s", "$1,244.80", "10%", "$1,120.32", "-5.2%"],
            ["Cosmos DB", "Serverless", "1", "$0.25/RU", "$892.50", "0%", "$892.50", "+2.1%"],
            ["Service Bus", "Standard", "3", "$0.05/msg", "$456.30", "15%", "$387.86", "-12.4%"],
            ["Blob Storage", "Hot", "500GB", "$0.018/GB", "$9.00", "0%", "$9.00", "-8.3%"],
            ["Key Vault", "Standard", "2", "$0.03/op", "$45.60", "0%", "$45.60", "+1.2%"],
            ["Microsoft Foundry", "S0", "1", "$1.50/1k", "$3,450.00", "20%", "$2,760.00", "-3.8%"],
            ["App Insights", "Pay-as-go", "1", "$2.30/GB", "$234.60", "0%", "$234.60", "+5.7%"],
            ["Container Reg", "Basic", "1", "$5.00/day", "$150.00", "0%", "$150.00", "0.0%"],
            ["DNS Zone", "Public", "2", "$0.50/zone", "$1.00", "0%", "$1.00", "0.0%"],
            ["Load Balancer", "Standard", "1", "$0.025/hr", "$18.00", "0%", "$18.00", "-2.1%"],
            ["Virtual Network", "Basic", "2", "$0.00", "$0.00", "0%", "$0.00", "0.0%"],
            ["Managed Identity", "-", "3", "$0.00", "$0.00", "0%", "$0.00", "0.0%"],
            ["Log Analytics", "Pay-as-go", "1", "$2.76/GB", "$345.00", "5%", "$327.75", "+4.3%"],
            ["TOTAL", "", "", "", "$6,846.80", "", "$5,946.63", "-2.7%"],
        ],
        [28, 24, 15, 24, 22, 20, 22, 22],
    )

    pdf.sub_title("Table 4: SLA Compliance Matrix")
    pdf.add_table(
        ["Service", "SLA Target", "Jan", "Feb", "Mar", "Apr", "May", "Jun"],
        [
            ["API Gateway", "99.95%", "99.98%", "99.97%", "99.99%", "99.96%", "99.98%", "99.99%"],
            ["OCR Pipeline", "99.90%", "99.95%", "99.92%", "99.94%", "99.91%", "99.93%", "99.97%"],
            ["Database", "99.99%", "100.0%", "99.99%", "100.0%", "100.0%", "99.99%", "100.0%"],
            ["Queue System", "99.95%", "99.99%", "99.98%", "99.97%", "99.99%", "99.96%", "99.99%"],
            ["Storage", "99.99%", "100.0%", "100.0%", "100.0%", "100.0%", "100.0%", "100.0%"],
            ["Auth Service", "99.99%", "99.99%", "100.0%", "99.99%", "100.0%", "99.99%", "100.0%"],
        ],
        [28, 22, 22, 22, 22, 22, 22, 22],
    )

    pdf.body_text(
        "Notes:\n"
        "1. All percentages represent uptime measured on 5-minute intervals.\n"
        "2. Discount rates are negotiated enterprise agreement terms.\n"
        "3. Budget variance is calculated against Q2 2025 forecast.\n"
        "4. Cost optimization recommendations are in Appendix B."
    )

    # ===== PAGE 3 — Classification results =====
    pdf.add_page()
    pdf.section_title("Section 3: Document Classification Results")
    pdf.body_text(
        "The classification pipeline categorizes incoming documents into predefined types "
        "using a multi-stage approach: (1) OCR extraction via Mistral Document AI, "
        "(2) structural analysis of headers, tables, and layout, (3) LLM-based semantic "
        "classification using GPT-4.1-mini, and (4) confidence scoring with human review "
        "for low-confidence results."
    )

    pdf.sub_title("Table 5: Classification Accuracy by Document Type")
    pdf.add_table(
        ["Document Type", "Total", "Correct", "Accuracy", "Precision", "Recall", "F1-Score"],
        [
            ["Invoice", "2,345", "2,312", "98.6%", "0.987", "0.986", "0.986"],
            ["Purchase Order", "1,890", "1,852", "97.9%", "0.981", "0.979", "0.980"],
            ["Delivery Note", "1,456", "1,428", "98.1%", "0.983", "0.981", "0.982"],
            ["Contract", "987", "968", "98.1%", "0.984", "0.978", "0.981"],
            ["Insurance Claim", "654", "639", "97.7%", "0.979", "0.977", "0.978"],
            ["Tax Document", "1,234", "1,216", "98.5%", "0.987", "0.985", "0.986"],
            ["Bank Statement", "876", "862", "98.4%", "0.986", "0.984", "0.985"],
            ["Medical Record", "543", "527", "97.1%", "0.974", "0.971", "0.972"],
            ["Legal Filing", "432", "420", "97.2%", "0.975", "0.972", "0.973"],
            ["Correspondence", "2,430", "2,388", "98.3%", "0.985", "0.983", "0.984"],
        ],
        [32, 20, 22, 22, 22, 20, 22],
    )

    pdf.sub_title("Table 6: Error Analysis - Top Misclassifications")
    pdf.add_table(
        ["Actual Type", "Predicted As", "Count", "% of Errors", "Root Cause"],
        [
            ["Purchase Order", "Invoice", "18", "12.3%", "Similar header layout"],
            ["Delivery Note", "Invoice", "14", "9.6%", "Shared vendor template"],
            ["Contract", "Legal Filing", "11", "7.5%", "Legal terminology overlap"],
            ["Insurance Claim", "Medical Record", "9", "6.2%", "Medical content in claims"],
            ["Correspondence", "Contract", "8", "5.5%", "Formal letter format"],
            ["Bank Statement", "Invoice", "7", "4.8%", "Tabular financial data"],
            ["Tax Document", "Invoice", "6", "4.1%", "Numerical data patterns"],
        ],
        [32, 30, 18, 22, 55],
    )

    # ===== PAGE 4 — Infrastructure config =====
    pdf.add_page()
    pdf.section_title("Section 4: Infrastructure Configuration")

    pdf.sub_title("Table 7: Container App Environment Variables")
    pdf.add_table(
        ["Variable", "Service", "Source", "Description"],
        [
            ["COSMOS_ENDPOINT", "API + Worker", "Terraform", "Cosmos DB account endpoint"],
            ["COSMOS_DATABASE", "API + Worker", "Terraform", "Database name (classymail)"],
            ["COSMOS_CONTAINER", "API + Worker", "Terraform", "Container name (emails)"],
            ["SERVICEBUS_FQDN", "API + Worker", "Terraform", "Service Bus namespace FQDN"],
            ["SERVICEBUS_QUEUE", "Worker", "Terraform", "Queue name (pdf-queue)"],
            ["STORAGE_ACCOUNT", "API + Worker", "Terraform", "Blob storage account name"],
            ["STORAGE_CONTAINER", "API + Worker", "Terraform", "Blob container (attachments)"],
            ["AI_FOUNDRY_ENDPOINT", "API + Worker", "Terraform", "Microsoft Foundry project endpoint"],
            ["AI_FOUNDRY_KEY", "API + Worker", "Key Vault", "API key (managed identity)"],
            ["MISTRAL_DEPLOYMENT", "Worker", "Terraform", "OCR model deployment name"],
            ["GPT_DEPLOYMENT", "API + Worker", "Terraform", "LLM deployment name"],
            ["APPLICATIONINSIGHTS_CS", "API + Worker", "Terraform", "App Insights conn string"],
            ["AZURE_CLIENT_ID", "API + Worker", "Terraform", "UAMI client ID for RBAC"],
            ["ASPNETCORE_URLS", "API", "Static", "Listen port configuration"],
        ],
        [40, 28, 22, 65],
    )

    pdf.sub_title("Table 8: RBAC Role Assignments")
    pdf.add_table(
        ["Principal", "Role", "Scope", "Purpose"],
        [
            ["UAMI (api)", "Cosmos DB Data Contrib", "Cosmos Account", "Read/write docs"],
            ["UAMI (api)", "Storage Blob Reader", "Storage Account", "Read attachments"],
            ["UAMI (api)", "SB Data Sender", "Service Bus NS", "Enqueue messages"],
            ["UAMI (worker)", "Cosmos DB Data Contrib", "Cosmos Account", "Read/write docs"],
            ["UAMI (worker)", "Storage Blob Reader", "Storage Account", "Read PDF files"],
            ["UAMI (worker)", "SB Data Receiver", "Service Bus NS", "Dequeue + complete"],
            ["UAMI (worker)", "Cognitive Svc User", "Microsoft Foundry", "Call OCR + LLM"],
            ["UAMI (both)", "AcrPull", "Container Registry", "Pull images"],
            ["Developers", "KV Secrets User", "Key Vault", "Read secrets"],
        ],
        [30, 40, 35, 40],
    )

    # ===== PAGE 5 — Performance metrics =====
    pdf.add_page()
    pdf.section_title("Appendix A: Detailed OCR Performance Metrics")

    pdf.sub_title("Table 9: Per-Language OCR Accuracy (Test Suite: 500 docs/lang)")
    pdf.add_table(
        ["Language", "Printed", "Handwritten", "Mixed", "Tables", "Avg Time"],
        [
            ["English", "99.8%", "98.2%", "98.9%", "99.1%", "2.1s"],
            ["German", "99.6%", "97.5%", "98.4%", "98.8%", "2.3s"],
            ["French", "99.5%", "97.8%", "98.5%", "98.9%", "2.2s"],
            ["Spanish", "99.4%", "97.3%", "98.2%", "98.7%", "2.2s"],
            ["Dutch", "99.3%", "96.9%", "97.8%", "98.5%", "2.4s"],
            ["Italian", "99.4%", "97.1%", "98.0%", "98.6%", "2.3s"],
            ["Portuguese", "99.2%", "96.8%", "97.7%", "98.4%", "2.4s"],
            ["Japanese", "98.9%", "95.2%", "96.8%", "97.9%", "3.1s"],
            ["Chinese (Simplified)", "98.7%", "94.8%", "96.5%", "97.6%", "3.3s"],
            ["Korean", "98.8%", "95.0%", "96.6%", "97.8%", "3.0s"],
            ["Arabic", "98.1%", "93.5%", "95.4%", "96.8%", "3.5s"],
            ["Russian", "99.0%", "96.2%", "97.3%", "98.1%", "2.6s"],
        ],
        [35, 22, 30, 22, 22, 22],
    )

    pdf.sub_title("Table 10: Processing Time Distribution (p50/p90/p95/p99)")
    pdf.add_table(
        ["Document Type", "Pages", "p50", "p90", "p95", "p99", "Max"],
        [
            ["Single-page form", "1", "0.8s", "1.2s", "1.5s", "2.1s", "3.2s"],
            ["Multi-page report", "5-10", "2.1s", "3.4s", "4.0s", "5.8s", "8.1s"],
            ["Dense tables", "1-3", "1.5s", "2.8s", "3.5s", "5.2s", "7.4s"],
            ["Scanned (300dpi)", "1-5", "1.9s", "3.1s", "3.8s", "5.5s", "9.0s"],
            ["Mixed content", "10-20", "4.2s", "6.8s", "8.1s", "12.3s", "18.5s"],
            ["Large document", "30+", "8.5s", "14.2s", "18.0s", "25.1s", "42.0s"],
            ["Handwritten", "1-3", "2.8s", "4.5s", "5.2s", "7.8s", "11.2s"],
        ],
        [35, 18, 18, 18, 18, 18, 18],
    )

    pdf.sub_title("Table 11: Token Usage by Model (Monthly Average)")
    pdf.add_table(
        ["Model", "Input Tokens", "Output Tokens", "Total", "Cost", "$/1K tokens"],
        [
            ["Mistral Doc AI", "8,234,500", "2,145,300", "10,379,800", "$2,076", "$0.20"],
            ["GPT-4.1-mini", "3,456,000", "890,500", "4,346,500", "$652", "$0.15"],
            ["GPT-4.1-nano", "1,234,000", "345,600", "1,579,600", "$158", "$0.10"],
            ["Whisper", "-", "-", "2.3M seconds", "$1,150", "$0.50/hr"],
        ],
        [30, 28, 28, 28, 22, 28],
    )

    # ===== PAGE 6 — Charts (plot images) =====
    pdf.add_page()
    pdf.section_title("Appendix B: Visual Analytics")

    pdf.body_text("Figure 1: Infrastructure Cost by Azure Region")
    pdf.add_chart_image(_chart_bar_regions(), w=150)

    pdf.body_text("Figure 2: OCR Accuracy Trend (H1 2025)")
    pdf.add_chart_image(_chart_line_accuracy(), w=150)

    # ===== PAGE 7 — More charts =====
    pdf.add_page()

    pdf.body_text("Figure 3: Document Type Distribution")
    pdf.add_chart_image(_chart_pie_documents(), w=130)

    pdf.body_text("Figure 4: Monthly Token Usage by Model")
    pdf.add_chart_image(_chart_stacked_bar_tokens(), w=120)

    # ===== PAGE 8 — Mermaid diagrams =====
    pdf.add_page()
    pdf.section_title("Appendix C: Mermaid Diagrams")

    pdf.body_text("Figure 5: Document Processing Flowchart (Mermaid)")
    png = _render_mermaid(MERMAID_FLOWCHART)
    if png:
        pdf.add_chart_image(png, w=140)
    else:
        pdf.body_text("[Mermaid diagram could not be rendered - internet required]")

    pdf.body_text("Figure 6: API Sequence Diagram (Mermaid)")
    png = _render_mermaid(MERMAID_SEQUENCE)
    if png:
        pdf.add_chart_image(png, w=160)
    else:
        pdf.body_text("[Mermaid diagram could not be rendered - internet required]")

    # ===== PAGE 9 — More Mermaid + class diagram =====
    pdf.add_page()

    pdf.body_text("Figure 7: Data Model Class Diagram (Mermaid)")
    png = _render_mermaid(MERMAID_CLASS)
    if png:
        pdf.add_chart_image(png, w=140)
    else:
        pdf.body_text("[Mermaid diagram could not be rendered - internet required]")
    pdf.ln(4)

    # ===== PAGE 10 — ASCII art diagrams =====
    pdf.add_page()
    pdf.section_title("Appendix D: Architecture Diagrams (ASCII)")

    pdf.add_ascii_block("Architecture Overview", ASCII_ARCHITECTURE, font_size=6)
    pdf.ln(4)

    pdf.add_ascii_block("Processing Flowchart", ASCII_FLOWCHART, font_size=5.5)

    # ===== PAGE 9 — ASCII logo + summary =====
    pdf.add_page()
    pdf.add_ascii_block("Mistral Document AI - ASCII Art Logo", ASCII_LOGO, font_size=7)
    pdf.ln(6)

    pdf.section_title("End of Report")
    pdf.body_text(
        "This document was generated as a test artifact for the Mistral Document AI OCR demo. "
        "It contains tables, charts, Mermaid diagrams, and ASCII art to exercise v25.12 "
        "features such as chart-to-table extraction, image recognition, table_format options, "
        "and annotations."
    )

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)
    n_pages = pdf.pages_count
    print(f"Generated: {output_path} ({n_pages} pages — tables, charts, Mermaid diagrams, ASCII art)")


if __name__ == "__main__":
    build_pdf()
