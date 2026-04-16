"""Outreach message generator using Claude API.

Takes scored leads and generates personalized cold emails
referencing specific findings from enrichment data.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import anthropic
from rich.console import Console

from src.config import load_settings, get_api_key
from src.models import Lead

console = Console()

SYSTEM_PROMPT = """You are a cold email writer for a business modernization consultancy.
Your job is to write short, specific, non-salesy cold emails to business owners or operations managers.

Rules:
- Max 150 words for initial email, 80 words for follow-ups
- Reference specific, concrete observations about their business (provided in the lead data)
- Never use buzzwords like "synergy", "leverage", "cutting-edge", "revolutionary"
- Never say "I noticed that..." — just state what you found directly
- Tone: direct, knowledgeable, peer-to-peer. Not salesy, not subservient
- The goal is to get a reply, not close a deal. Ask a specific question at the end
- Subject lines: short, specific to their business, no clickbait

You will receive structured data about a lead and must generate:
1. Subject line
2. Email body
3. Follow-up emails (as requested)

Output valid JSON with keys: subject, body, followups (array of strings)."""


def _build_lead_context(lead: Lead) -> str:
    """Build a context string from lead data for the prompt."""
    parts = [
        f"Business: {lead.business_name}",
        f"Category: {lead.category}",
        f"Location: {lead.address}",
        f"Website: {lead.website}",
    ]

    if lead.contact_name:
        parts.append(f"Contact: {lead.contact_name} ({lead.contact_title})")

    # Website findings
    findings = []
    if lead.has_crm is False:
        findings.append("No CRM system detected on their website")
    if lead.has_chat_widget is False:
        findings.append("No chat widget or chatbot on website")
    if lead.has_scheduling is False:
        findings.append("No online scheduling/booking tool")
    if lead.has_ssl is False:
        findings.append("Website lacks SSL certificate")
    if lead.is_mobile_responsive is False:
        findings.append("Website is not mobile-responsive")
    if findings:
        parts.append("Website gaps: " + "; ".join(findings))

    # Tech stack
    if lead.tech_stack:
        parts.append(f"Detected tech: {', '.join(lead.tech_stack)}")

    # Review signals
    if lead.ops_complaint_count > 0:
        parts.append(
            f"Customer reviews: {lead.ops_complaint_count} complaints about "
            f"operational issues out of {lead.reviews_analyzed} reviews analyzed"
        )
        if lead.ops_complaint_samples:
            parts.append(
                "Example complaints: " + " | ".join(lead.ops_complaint_samples[:3])
            )
    if lead.owner_response_rate is not None and lead.owner_response_rate < 0.3:
        parts.append(
            f"Owner responds to only {lead.owner_response_rate:.0%} of reviews"
        )

    # Job posting signals
    if lead.manual_process_postings > 0:
        parts.append(
            f"Currently hiring for {lead.manual_process_postings} roles "
            f"that suggest manual processes: {', '.join(lead.manual_process_titles[:3])}"
        )

    # Score
    if lead.score is not None:
        parts.append(f"Modernization score: {lead.score}/100")
        if lead.score_breakdown:
            top_factors = sorted(
                lead.score_breakdown.items(), key=lambda x: x[1], reverse=True
            )[:3]
            parts.append(
                "Top scoring factors: "
                + ", ".join(f"{k}={v:.2f}" for k, v in top_factors)
            )

    return "\n".join(parts)


def generate_outreach(
    lead: Lead,
    followup_count: int = 2,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 500,
) -> Lead:
    """Generate personalized outreach email + follow-ups for a lead."""
    settings = load_settings()
    api_key = get_api_key(settings, "anthropic_key")

    client = anthropic.Anthropic(api_key=api_key)
    context = _build_lead_context(lead)

    prompt = (
        f"Generate a cold email sequence for this lead:\n\n"
        f"{context}\n\n"
        f"Generate 1 initial email and {followup_count} follow-ups.\n"
        f"Output as JSON: {{\"subject\": \"...\", \"body\": \"...\", "
        f"\"followups\": [\"...\", \"...\"]}}"
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text

        # Parse JSON from response (handle potential markdown wrapping)
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]

        result = json.loads(cleaned)

        lead.outreach_email = f"Subject: {result['subject']}\n\n{result['body']}"
        lead.followups = result.get("followups", [])
        lead.contacted_at = datetime.now(timezone.utc)

    except Exception as e:
        console.print(f"[yellow]Outreach generation failed for {lead.business_name}: {e}[/]")

    return lead


def generate_batch_outreach(
    leads: list[Lead],
    followup_count: int = 2,
) -> list[Lead]:
    """Generate outreach for a batch of leads."""
    settings = load_settings()
    outreach_config = settings.get("outreach", {})
    model = outreach_config.get("model", "claude-sonnet-4-20250514")
    max_tokens = outreach_config.get("max_tokens", 500)
    fc = outreach_config.get("followup_count", followup_count)

    console.print(f"[bold]Generating outreach for {len(leads)} leads[/]")

    for i, lead in enumerate(leads):
        console.print(f"  [{i + 1}/{len(leads)}] {lead.business_name}...")
        generate_outreach(lead, fc, model, max_tokens)

    success = sum(1 for l in leads if l.outreach_email)
    console.print(f"[green]Generated {success}/{len(leads)} emails[/]")

    return leads
