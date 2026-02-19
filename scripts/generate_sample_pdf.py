"""Generate a complex sample PDF with multiple tables for OCR demo.

Usage:
    uv run python scripts/generate_sample_pdf.py

Creates data/sample_complex_report.pdf — a multi-page document with:
- Mixed text sections and headers
- Multiple tables with different structures (financial, technical, nested headers)
- Bullet lists and numbered items
- A dense multi-column table spanning a full page
"""

from __future__ import annotations

from fpdf import FPDF


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
        "The Mistral Document AI model was deployed on Azure AI Foundry in West Europe, processing "
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
            ["AI Foundry", "S0", "1", "$1.50/1k", "$3,450.00", "20%", "$2,760.00", "-3.8%"],
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
            ["AI_FOUNDRY_ENDPOINT", "API + Worker", "Terraform", "AI Foundry project endpoint"],
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
            ["UAMI (worker)", "Cognitive Svc User", "AI Foundry", "Call OCR + LLM"],
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

    # Save
    from pathlib import Path
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf.output(output_path)
    print(f"Generated: {output_path} (5 pages, 11 tables)")


if __name__ == "__main__":
    build_pdf()
