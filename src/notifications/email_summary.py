"""Email summary notifications for scheduled pipeline runs.

Composes HTML digest emails with top leads and run stats,
sends via SMTP (stdlib smtplib — no external dependencies).
"""

from __future__ import annotations

import html as html_lib
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from rich.console import Console

from src.models import Lead

console = Console()


def _get_smtp_config(settings: dict) -> dict:
    """Get SMTP config from settings, with env var fallback."""
    email_cfg = settings.get("schedule", {}).get("summary_email", {})
    return {
        "host": email_cfg.get("smtp_host", "smtp.gmail.com"),
        "port": email_cfg.get("smtp_port", 587),
        "user": email_cfg.get("smtp_user") or os.environ.get("BIZ_SMTP_USER", ""),
        "password": email_cfg.get("smtp_password") or os.environ.get("BIZ_SMTP_PASSWORD", ""),
        "to": email_cfg.get("to", ""),
        "subject_prefix": email_cfg.get("subject_prefix", "[biz-prospector]"),
    }


def _build_signals(lead: Lead) -> str:
    """Build a short signal summary string for a lead."""
    signals = []
    if lead.has_crm is False:
        signals.append("No CRM")
    if lead.has_scheduling is False:
        signals.append("No scheduling")
    if lead.has_chat_widget is False:
        signals.append("No chat")
    if lead.manual_role_count > 0:
        signals.append(f"{lead.manual_role_count} manual roles")
    if lead.ops_complaint_count > 0:
        signals.append(f"{lead.ops_complaint_count} complaints")
    return ", ".join(signals) if signals else "—"


def compose_summary_html(leads: list[Lead], run_info: dict) -> str:
    """Compose an HTML email body summarizing a pipeline run."""
    vertical = run_info.get("vertical", "").upper()
    metro = run_info.get("metro", "")
    timestamp = run_info.get("timestamp", "")
    scraped = run_info.get("scraped_count", 0)
    qualified = run_info.get("qualified_count", len(leads))
    threshold = run_info.get("threshold", 55)
    is_re_enrich = run_info.get("is_re_enrich", False)

    run_type = "Re-enrichment Update" if is_re_enrich else "Run Summary"

    # Stats
    scores = [l.score for l in leads if l.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_score = max(scores) if scores else 0
    with_email = sum(1 for l in leads if l.contact_email)

    # Top 10 leads table rows
    top_leads = sorted(leads, key=lambda l: l.score or 0, reverse=True)[:10]
    rows = ""
    for lead in top_leads:
        score_str = f"{lead.score:.1f}" if lead.score else "—"
        name = html_lib.escape(lead.business_name[:30])
        contact = html_lib.escape(f"{lead.contact_name} ({lead.contact_title})" if lead.contact_name else "—")
        signals = html_lib.escape(_build_signals(lead))
        rows += f"<tr><td>{score_str}</td><td>{name}</td><td>{contact}</td><td>{signals}</td></tr>\n"

    return f"""<html>
<body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<h2>{run_type}: {vertical} {metro}</h2>
<p>
  <strong>Run time:</strong> {html_lib.escape(timestamp)}<br>
  <strong>Scraped:</strong> {scraped} |
  <strong>Qualified:</strong> {qualified} (threshold: {threshold})
</p>

<h3>Top Leads</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">
<tr style="background: #f0f0f0;">
  <th>Score</th><th>Business</th><th>Contact</th><th>Signals</th>
</tr>
{rows if rows else '<tr><td colspan="4">No qualified leads this run.</td></tr>'}
</table>

<h3>Quick Stats</h3>
<p>
  Average score: {avg_score:.1f} | Highest: {max_score:.1f}<br>
  With contact email: {with_email}/{len(leads)}{f' ({with_email*100//len(leads)}%)' if leads else ''}<br>
</p>

<p style="color: #888; font-size: 12px;">Full report attached.</p>
</body>
</html>"""
