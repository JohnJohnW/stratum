"""
Customer Due Diligence (CDD) PDF report generator.

Produces a professional PDF using WeasyPrint + Jinja2 containing identified
beneficial owners, contradiction flags with supporting passages, matched
typology information, and document hashes.
"""

import logging
from datetime import datetime, timezone

from jinja2 import Template
from weasyprint import HTML

from backend.documents import get_matter

logger = logging.getLogger(__name__)

CDD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {
    size: A4;
    margin: 2cm;
    @bottom-center {
      content: "Page " counter(page) " of " counter(pages);
      font-size: 9px;
      color: #718096;
    }
  }
  body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 11px;
    line-height: 1.5;
    color: #2d3748;
  }
  h1 {
    color: #1e3a5f;
    font-size: 22px;
    border-bottom: 3px solid #1e3a5f;
    padding-bottom: 8px;
    margin-bottom: 5px;
  }
  h2 {
    color: #1e3a5f;
    font-size: 15px;
    border-bottom: 1px solid #cbd5e0;
    padding-bottom: 5px;
    margin-top: 25px;
  }
  h3 {
    color: #2c5282;
    font-size: 13px;
    margin-top: 15px;
  }
  .subtitle {
    color: #718096;
    font-size: 12px;
    margin-bottom: 20px;
  }
  .meta-table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
  }
  .meta-table td {
    padding: 4px 10px;
    border-bottom: 1px solid #e2e8f0;
  }
  .meta-table td:first-child {
    font-weight: bold;
    width: 200px;
    color: #4a5568;
  }
  table.data-table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 10px;
  }
  table.data-table th {
    background: #1e3a5f;
    color: white;
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
  }
  table.data-table td {
    padding: 6px 10px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
  }
  table.data-table tr:nth-child(even) td {
    background: #f7fafc;
  }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 9px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .badge-critical { background: #fed7d7; color: #c53030; }
  .badge-high { background: #feebc8; color: #c05621; }
  .badge-medium { background: #fefcbf; color: #975a16; }
  .badge-clean { background: #c6f6d5; color: #276749; }
  .monospace { font-family: 'Courier New', monospace; font-size: 10px; }
  .passage-box {
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #4299e1;
    padding: 8px 12px;
    margin: 5px 0;
    font-size: 10px;
    line-height: 1.4;
  }
  .passage-box.target {
    border-left-color: #e53e3e;
  }
  .passage-label {
    font-size: 9px;
    font-weight: bold;
    color: #718096;
    text-transform: uppercase;
    margin-bottom: 3px;
  }
  .risk-box {
    padding: 12px 16px;
    border-radius: 4px;
    margin: 10px 0;
  }
  .risk-low { background: #c6f6d5; border: 1px solid #38a169; }
  .risk-medium { background: #fefcbf; border: 1px solid #d69e2e; }
  .risk-high { background: #fed7d7; border: 1px solid #e53e3e; }
  .signoff-box {
    border: 2px solid #1e3a5f;
    padding: 15px;
    margin-top: 30px;
  }
  .signoff-line {
    border-bottom: 1px solid #2d3748;
    margin: 20px 0 5px 0;
    width: 250px;
  }
  .disclaimer {
    margin-top: 30px;
    padding: 10px;
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    font-size: 9px;
    color: #718096;
  }
</style>
</head>
<body>

<h1>Customer Due Diligence Record</h1>
<p class="subtitle">Beneficial Ownership Contradiction Analysis Report</p>

<table class="meta-table">
  <tr><td>Matter Reference</td><td class="monospace">{{ matter_id }}</td></tr>
  <tr><td>Entity Name</td><td>{{ entity_name }}</td></tr>
  <tr><td>ACN</td><td>{{ acn }}</td></tr>
  <tr><td>Report Generated</td><td>{{ timestamp }}</td></tr>
  <tr><td>Prepared By</td><td>STRATUM Automated Analysis</td></tr>
  <tr><td>Documents Analysed</td><td>{{ documents|length }}</td></tr>
</table>

<h2>1. Document Register</h2>
<table class="data-table">
  <thead>
    <tr>
      <th>Document</th>
      <th>Type</th>
      <th>Pages</th>
      <th>SHA-256 Hash</th>
    </tr>
  </thead>
  <tbody>
    {% for doc in documents %}
    <tr>
      <td>{{ doc.filename }}</td>
      <td>{{ doc.doc_type }}</td>
      <td>{{ doc.page_count }}</td>
      <td class="monospace">{{ doc.sha256_hash[:16] }}...</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>2. Beneficial Ownership Analysis</h2>
{% if contradictions %}
<div class="risk-box risk-high">
  <strong>Risk Assessment: HIGH</strong>: {{ contradictions|length }} contradiction(s) detected
  across uploaded documents. Manual investigation required.
</div>
{% else %}
<div class="risk-box risk-low">
  <strong>Risk Assessment: LOW</strong>
  <span class="badge badge-clean">CLEAN</span>:
  No contradictions detected. All documents are consistent.
</div>
{% endif %}

<h2>3. Contradiction Findings</h2>
{% if contradictions %}
<table class="data-table">
  <thead>
    <tr>
      <th>#</th>
      <th>Typology</th>
      <th>Severity</th>
      <th>Similarity</th>
      <th>Source</th>
      <th>Target</th>
    </tr>
  </thead>
  <tbody>
    {% for c in contradictions %}
    <tr>
      <td>{{ loop.index }}</td>
      <td>{{ c.typology_label }}</td>
      <td><span class="badge badge-{{ c.severity }}">{{ c.severity }}</span></td>
      <td class="monospace">{{ "%.3f"|format(c.cosine_similarity) }}</td>
      <td>{{ c.source_document }}</td>
      <td>{{ c.target_document }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

{% for c in contradictions %}
<h3>Finding {{ loop.index }}: {{ c.typology_label }}</h3>
<p><span class="badge badge-{{ c.severity }}">{{ c.severity }}</span>
   Cosine similarity: <span class="monospace">{{ "%.3f"|format(c.cosine_similarity) }}</span></p>

<div class="passage-label">Source: {{ c.source_document }} ({{ c.source_section }})</div>
<div class="passage-box">{{ c.source_text }}</div>

<div class="passage-label">Target: {{ c.target_document }} ({{ c.target_section }})</div>
<div class="passage-box target">{{ c.target_text }}</div>

<p><strong>Matched Typology:</strong> {{ c.typology_label }}</p>
<p style="font-size: 10px; color: #4a5568;">{{ c.typology_description }}</p>

<p><strong>Assessment:</strong> {{ c.explanation }}</p>
{% endfor %}
{% else %}
<p>No contradictions were detected across the analysed documents. All corporate
structure information is consistent between the ASIC extract, company constitution,
and shareholder register.</p>
{% endif %}

<h2>4. Document Integrity</h2>
<table class="data-table">
  <thead>
    <tr><th>Document</th><th>SHA-256 Hash</th></tr>
  </thead>
  <tbody>
    {% for doc in documents %}
    <tr>
      <td>{{ doc.filename }}</td>
      <td class="monospace">{{ doc.sha256_hash }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>5. AML Officer Sign-Off</h2>
<div class="signoff-box">
  <p>I have reviewed the above Customer Due Diligence Record and the supporting
  documentation. I confirm that the beneficial ownership analysis has been
  conducted in accordance with the firm's AML/CTF Tranche 2 compliance
  obligations.</p>
  <div class="signoff-line"></div>
  <p style="font-size: 10px;">AML/CTF Compliance Officer, Name and Signature</p>
  <div class="signoff-line"></div>
  <p style="font-size: 10px;">Date</p>
  <div class="signoff-line"></div>
  <p style="font-size: 10px;">Partner / Principal, Name and Signature</p>
</div>

<div class="disclaimer">
  <strong>Disclaimer:</strong> This report is generated by STRATUM
  for demonstration purposes. It is a compliance aid requiring human review and is not
  an automated decision system. The analysis uses the gemini-embedding-2-preview model
  which is in public preview and not suitable for production use. All findings should be
  independently verified by qualified legal and compliance professionals.
</div>

</body>
</html>
"""


async def generate_cdd_report(matter_id: str) -> bytes:
    """Generate a CDD PDF report for a matter. Returns PDF bytes."""
    matter = get_matter(matter_id)
    if not matter:
        raise ValueError(f"Matter {matter_id} not found")

    template = Template(CDD_TEMPLATE)
    html_str = template.render(
        matter_id=matter.matter_id,
        entity_name=matter.entity_name or "Unknown Entity",
        acn=matter.acn or "N/A",
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        documents=[
            {
                "filename": d.filename,
                "doc_type": d.doc_type.value.replace("_", " ").title(),
                "page_count": d.page_count,
                "sha256_hash": d.sha256_hash,
            }
            for d in matter.documents
        ],
        contradictions=[
            c if isinstance(c, dict) else c
            for c in matter.contradictions
        ],
    )

    pdf_bytes = HTML(string=html_str).write_pdf()
    logger.info("Generated CDD report for matter %s: %d bytes", matter_id, len(pdf_bytes))
    return pdf_bytes
