"""HTML report generator for pipeline run results.

Produces a single self-contained HTML file with:
- Run summary (counts, date, vertical/metro)
- Score distribution histogram (pure CSS)
- Top leads table with key signals
- Tech stack breakdown
- Missing tools breakdown (CRM, chat, scheduling)
"""

from __future__ import annotations

import html
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models import Lead

REPORT_DIR = Path("data/reports")


def _score_histogram_bins(leads: list[Lead], num_bins: int = 10) -> list[dict]:
    """Bucket scores into histogram bins.

    Returns list of dicts: {label, count, pct}.
    """
    scores = [l.score for l in leads if l.score is not None]
    if not scores:
        return []

    bin_width = 100 / num_bins
    bins = []
    for i in range(num_bins):
        lo = i * bin_width
        hi = lo + bin_width
        label = f"{lo:.0f}-{hi:.0f}"
        count = sum(1 for s in scores if lo <= s < hi or (i == num_bins - 1 and s == 100))
        bins.append({"label": label, "count": count})

    max_count = max(b["count"] for b in bins) if bins else 1
    for b in bins:
        b["pct"] = (b["count"] / max_count * 100) if max_count > 0 else 0

    return bins


def _tech_stack_counts(leads: list[Lead]) -> list[tuple[str, int]]:
    """Count tech occurrences across all leads, sorted descending."""
    counter: Counter[str] = Counter()
    for lead in leads:
        for tech in lead.tech_stack:
            counter[tech] += 1
    return counter.most_common(20)


def _missing_tools_counts(leads: list[Lead]) -> dict[str, dict[str, int]]:
    """Count leads missing/having each tool."""
    tools = {
        "CRM": "has_crm",
        "Chat Widget": "has_chat_widget",
        "Scheduling": "has_scheduling",
        "SSL": "has_ssl",
        "Mobile Responsive": "is_mobile_responsive",
    }
    result = {}
    for label, field in tools.items():
        values = [getattr(lead, field) for lead in leads]
        result[label] = {
            "missing": sum(1 for v in values if v is False),
            "present": sum(1 for v in values if v is True),
            "unknown": sum(1 for v in values if v is None),
        }
    return result


def _summary_stats(leads: list[Lead]) -> dict[str, Any]:
    """Compute summary statistics."""
    scores = [l.score for l in leads if l.score is not None]
    return {
        "total_leads": len(leads),
        "scored_leads": len(scores),
        "avg_score": sum(scores) / len(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "min_score": min(scores) if scores else 0,
        "with_email": sum(1 for l in leads if l.contact_email),
        "with_outreach": sum(1 for l in leads if l.outreach_email),
    }


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text))


def _tool_icon(value: bool | None) -> str:
    """Render a tool status as a colored indicator."""
    if value is True:
        return '<span class="present">Yes</span>'
    if value is False:
        return '<span class="missing">No</span>'
    return '<span class="unknown">?</span>'


def _render_histogram(bins: list[dict]) -> str:
    """Render score histogram as CSS bar chart."""
    if not bins:
        return "<p>No scores available.</p>"

    rows = []
    for b in bins:
        rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{b["label"]}</span>'
            f'<div class="bar-track">'
            f'<div class="bar-fill" style="width:{b["pct"]:.1f}%"></div>'
            f'</div>'
            f'<span class="bar-count">{b["count"]}</span>'
            f'</div>'
        )
    return "\n".join(rows)


def _render_top_leads_table(leads: list[Lead], n: int = 25) -> str:
    """Render the top N leads as an HTML table."""
    sorted_leads = sorted(leads, key=lambda l: l.score or 0, reverse=True)[:n]

    rows = []
    for lead in sorted_leads:
        score_str = f"{lead.score:.1f}" if lead.score is not None else "—"
        rows.append(
            f"<tr>"
            f'<td class="score">{_esc(score_str)}</td>'
            f"<td>{_esc(lead.business_name)}</td>"
            f"<td>{_esc(lead.category)}</td>"
            f"<td>{_esc(lead.metro)}</td>"
            f"<td>{_tool_icon(lead.has_crm)}</td>"
            f"<td>{_tool_icon(lead.has_chat_widget)}</td>"
            f"<td>{_tool_icon(lead.has_scheduling)}</td>"
            f"<td>{lead.manual_process_postings}</td>"
            f"<td>{lead.ops_complaint_count}</td>"
            f"<td>{_esc(lead.contact_name)}</td>"
            f"<td>{_esc(lead.contact_email)}</td>"
            f"</tr>"
        )

    return "\n".join(rows)


def _render_tech_table(tech_counts: list[tuple[str, int]]) -> str:
    """Render tech stack breakdown table."""
    if not tech_counts:
        return "<p>No tech stack data.</p>"

    rows = []
    for tech, count in tech_counts:
        rows.append(f"<tr><td>{_esc(tech)}</td><td>{count}</td></tr>")
    return (
        '<table class="data-table"><thead><tr>'
        "<th>Technology</th><th>Count</th>"
        "</tr></thead><tbody>" + "\n".join(rows) + "</tbody></table>"
    )


def _render_tools_table(tools: dict[str, dict[str, int]]) -> str:
    """Render missing tools breakdown table."""
    rows = []
    for label, counts in tools.items():
        total = counts["missing"] + counts["present"] + counts["unknown"]
        pct = (counts["missing"] / total * 100) if total > 0 else 0
        rows.append(
            f"<tr>"
            f"<td>{_esc(label)}</td>"
            f'<td class="missing">{counts["missing"]}</td>'
            f'<td class="present">{counts["present"]}</td>'
            f"<td>{counts['unknown']}</td>"
            f"<td>{pct:.0f}%</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def generate_report(
    leads: list[Lead],
    title: str = "Pipeline Run Report",
    vertical: str = "",
    metro: str = "",
) -> str:
    """Generate a complete HTML report string from leads.

    Args:
        leads: List of scored leads.
        title: Report title.
        vertical: Business vertical name.
        metro: Metro area name.

    Returns:
        Complete HTML string.
    """
    stats = _summary_stats(leads)
    bins = _score_histogram_bins(leads)
    tech_counts = _tech_stack_counts(leads)
    tools = _missing_tools_counts(leads)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         color: #1a1a2e; background: #f5f5f7; padding: 2rem; line-height: 1.5; }}
  h1 {{ font-size: 1.8rem; margin-bottom: 0.3rem; }}
  h2 {{ font-size: 1.3rem; margin: 2rem 0 1rem; border-bottom: 2px solid #e0e0e0;
        padding-bottom: 0.4rem; }}
  .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 2rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: #fff; border-radius: 8px; padding: 1.2rem;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .card .num {{ font-size: 1.8rem; font-weight: 700; color: #2d5be3; }}
  .card .label {{ font-size: 0.85rem; color: #666; margin-top: 0.2rem; }}
  .bar-row {{ display: flex; align-items: center; margin: 0.3rem 0; }}
  .bar-label {{ width: 60px; font-size: 0.8rem; text-align: right; padding-right: 8px; }}
  .bar-track {{ flex: 1; background: #e8e8e8; border-radius: 4px; height: 20px; }}
  .bar-fill {{ background: #2d5be3; border-radius: 4px; height: 100%;
               min-width: 2px; transition: width 0.3s; }}
  .bar-count {{ width: 40px; font-size: 0.8rem; padding-left: 8px; }}
  table.data-table {{ width: 100%; border-collapse: collapse; background: #fff;
                      border-radius: 8px; overflow: hidden;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .data-table th {{ background: #2d5be3; color: #fff; padding: 0.7rem 1rem;
                    text-align: left; font-size: 0.85rem; }}
  .data-table td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #f0f0f0;
                    font-size: 0.85rem; }}
  .data-table tr:hover {{ background: #f8f9ff; }}
  .score {{ font-weight: 700; color: #2d5be3; }}
  .missing {{ color: #e53e3e; font-weight: 600; }}
  .present {{ color: #38a169; font-weight: 600; }}
  .unknown {{ color: #999; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }}
  @media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
  footer {{ margin-top: 3rem; color: #999; font-size: 0.8rem; text-align: center; }}
</style>
</head>
<body>

<h1>{_esc(title)}</h1>
<p class="meta">
  {f"Vertical: {_esc(vertical)} | " if vertical else ""}
  {f"Metro: {_esc(metro)} | " if metro else ""}
  Generated: {now}
</p>

<div class="cards">
  <div class="card">
    <div class="num">{stats['total_leads']}</div>
    <div class="label">Total Leads</div>
  </div>
  <div class="card">
    <div class="num">{stats['scored_leads']}</div>
    <div class="label">Scored</div>
  </div>
  <div class="card">
    <div class="num">{stats['avg_score']:.1f}</div>
    <div class="label">Avg Score</div>
  </div>
  <div class="card">
    <div class="num">{stats['max_score']:.1f}</div>
    <div class="label">Max Score</div>
  </div>
  <div class="card">
    <div class="num">{stats['with_email']}</div>
    <div class="label">With Contact Email</div>
  </div>
  <div class="card">
    <div class="num">{stats['with_outreach']}</div>
    <div class="label">Outreach Generated</div>
  </div>
</div>

<h2>Score Distribution</h2>
{_render_histogram(bins)}

<h2>Top Leads</h2>
<table class="data-table">
<thead><tr>
  <th>Score</th><th>Business</th><th>Category</th><th>Metro</th>
  <th>CRM</th><th>Chat</th><th>Sched</th>
  <th>Job Flags</th><th>Complaints</th>
  <th>Contact</th><th>Email</th>
</tr></thead>
<tbody>
{_render_top_leads_table(leads)}
</tbody>
</table>

<div class="two-col">
  <div>
    <h2>Tech Stack</h2>
    {_render_tech_table(tech_counts)}
  </div>
  <div>
    <h2>Tool Gaps</h2>
    <table class="data-table">
    <thead><tr>
      <th>Tool</th><th>Missing</th><th>Present</th><th>Unknown</th><th>Gap %</th>
    </tr></thead>
    <tbody>
    {_render_tools_table(tools)}
    </tbody>
    </table>
  </div>
</div>

<footer>Generated by biz-prospector</footer>
</body>
</html>"""


def save_report(
    leads: list[Lead],
    filename: str = "",
    title: str = "Pipeline Run Report",
    vertical: str = "",
    metro: str = "",
) -> Path:
    """Generate and save an HTML report to data/reports/.

    Args:
        leads: List of leads to report on.
        filename: Output filename. Auto-generated if empty.
        title: Report title.
        vertical: Business vertical.
        metro: Metro area.

    Returns:
        Path to the saved report file.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts = [vertical, metro, ts] if vertical else [ts]
        filename = "_".join(p for p in parts if p) + ".html"

    report_html = generate_report(leads, title, vertical, metro)
    path = REPORT_DIR / filename
    path.write_text(report_html)
    return path
