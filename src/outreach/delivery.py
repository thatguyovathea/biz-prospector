"""Instantly.ai email delivery integration.

Pushes generated outreach sequences to Instantly for
sending, warmup management, and follow-up automation.
"""

from __future__ import annotations

import json

import httpx
from rich.console import Console

from src.config import load_settings, get_api_key
from src.models import Lead

console = Console()

BASE_URL = "https://api.instantly.ai/api/v1"


class InstantlyClient:
    """Wrapper around Instantly.ai API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.Client(timeout=30)

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        params = params or {}
        params["api_key"] = self.api_key
        resp = self.client.get(f"{BASE_URL}/{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, data: dict) -> dict:
        data["api_key"] = self.api_key
        resp = self.client.post(f"{BASE_URL}/{endpoint}", json=data)
        resp.raise_for_status()
        return resp.json()

    def list_campaigns(self) -> list[dict]:
        """List all campaigns."""
        return self._get("campaign/list")

    def create_campaign(self, name: str) -> dict:
        """Create a new campaign."""
        return self._post("campaign/create", {"name": name})

    def add_leads_to_campaign(
        self,
        campaign_id: str,
        leads: list[dict],
    ) -> dict:
        """Add leads to a campaign.

        Each lead dict should have:
            - email: str
            - first_name: str (optional)
            - last_name: str (optional)
            - company_name: str (optional)
            - custom_variables: dict (optional)
        """
        return self._post(
            "lead/add",
            {
                "campaign_id": campaign_id,
                "leads": leads,
            },
        )

    def set_campaign_sequences(
        self,
        campaign_id: str,
        sequences: list[dict],
    ) -> dict:
        """Set email sequences for a campaign.

        Each sequence step dict:
            - subject: str (only for first step)
            - body: str
            - delay: int (days to wait before sending, 0 for first)
        """
        return self._post(
            "campaign/set-sequences",
            {
                "campaign_id": campaign_id,
                "sequences": [{"steps": sequences}],
            },
        )

    def launch_campaign(self, campaign_id: str) -> dict:
        """Activate a campaign for sending."""
        return self._post(
            "campaign/launch",
            {"campaign_id": campaign_id},
        )

    def get_campaign_stats(self, campaign_id: str) -> dict:
        """Get campaign analytics."""
        return self._get("analytics/campaign/summary", {"campaign_id": campaign_id})


def _parse_outreach_email(lead: Lead) -> tuple[str, str]:
    """Extract subject and body from generated outreach email."""
    if not lead.outreach_email:
        return "", ""

    lines = lead.outreach_email.strip().split("\n", 2)
    subject = ""
    body = lead.outreach_email

    if lines[0].lower().startswith("subject:"):
        subject = lines[0].replace("Subject:", "").replace("subject:", "").strip()
        body = "\n".join(lines[1:]).strip()

    return subject, body


def _lead_to_instantly_format(lead: Lead) -> dict:
    """Convert a Lead to Instantly's lead format."""
    name_parts = lead.contact_name.split(" ", 1) if lead.contact_name else ["", ""]
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    return {
        "email": lead.contact_email,
        "first_name": first_name,
        "last_name": last_name,
        "company_name": lead.business_name,
        "custom_variables": {
            "business_name": lead.business_name,
            "contact_title": lead.contact_title,
            "category": lead.category,
            "score": str(lead.score or 0),
            "website": lead.website,
        },
    }


def push_to_instantly(
    leads: list[Lead],
    campaign_name: str,
    followup_interval_days: int = 3,
    auto_launch: bool = False,
) -> dict:
    """Push scored leads with outreach to Instantly.

    Creates a campaign, adds leads, sets sequences, and optionally launches.

    Returns:
        dict with campaign_id, leads_added, status.
    """
    settings = load_settings()
    api_key = get_api_key(settings, "instantly_key")
    client = InstantlyClient(api_key)

    # Filter to leads with email + outreach
    sendable = [
        l for l in leads
        if l.contact_email and l.outreach_email
    ]

    if not sendable:
        console.print("[yellow]No sendable leads (need email + outreach)[/]")
        return {"campaign_id": None, "leads_added": 0, "status": "empty"}

    console.print(f"[bold]Pushing {len(sendable)} leads to Instantly[/]")

    # Create campaign
    campaign = client.create_campaign(campaign_name)
    campaign_id = campaign.get("id")
    console.print(f"  Created campaign: {campaign_name} ({campaign_id})")

    # Build sequences from first lead as template
    # (Instantly uses campaign-level sequences, not per-lead)
    # For true personalization, we use custom variables in the template
    first_lead = sendable[0]
    subject, body = _parse_outreach_email(first_lead)

    steps = [
        {"subject": subject, "body": body, "delay": 0},
    ]
    for i, followup in enumerate(first_lead.followups):
        steps.append({
            "body": followup,
            "delay": followup_interval_days * (i + 1),
        })

    client.set_campaign_sequences(campaign_id, steps)
    console.print(f"  Set {len(steps)} sequence steps")

    # Add leads
    instantly_leads = [_lead_to_instantly_format(l) for l in sendable]
    client.add_leads_to_campaign(campaign_id, instantly_leads)
    console.print(f"  Added {len(instantly_leads)} leads")

    # Optionally launch
    status = "ready"
    if auto_launch:
        client.launch_campaign(campaign_id)
        status = "launched"
        console.print("[green]  Campaign launched![/]")
    else:
        console.print("  [dim]Campaign ready — launch manually in Instantly dashboard[/]")

    return {
        "campaign_id": campaign_id,
        "leads_added": len(instantly_leads),
        "status": status,
    }
