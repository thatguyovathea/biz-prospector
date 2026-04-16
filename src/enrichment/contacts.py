"""Contact enrichment module.

Finds decision-maker contact info (name, email, title) for leads
using Apollo.io and Hunter.io as fallback.
"""

from __future__ import annotations

import httpx
from rich.console import Console
from src.models import Lead

console = Console()

# Titles we want to reach — ordered by priority
TARGET_TITLES = [
    "owner",
    "founder",
    "ceo",
    "president",
    "general manager",
    "operations manager",
    "office manager",
    "managing partner",
    "partner",
    "director of operations",
    "vp operations",
    "chief operating officer",
    "coo",
    "administrator",
]


def _title_priority(title: str) -> int:
    """Lower number = higher priority contact."""
    title_lower = title.lower()
    for i, target in enumerate(TARGET_TITLES):
        if target in title_lower:
            return i
    return 999


def search_apollo(
    company_name: str,
    domain: str,
    api_key: str,
    max_results: int = 5,
) -> list[dict]:
    """Search Apollo.io for contacts at a company.

    Returns list of person dicts with: name, email, title, linkedin_url.
    """
    with httpx.Client(timeout=30) as client:
        # First try domain-based search (more accurate)
        payload = {
            "api_key": api_key,
            "per_page": max_results,
            "person_titles": TARGET_TITLES[:8],  # Apollo limits title filters
        }

        if domain:
            payload["q_organization_domains"] = domain
        else:
            payload["q_organization_name"] = company_name

        resp = client.post(
            "https://api.apollo.io/v1/mixed_people/search",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        people = []
        for person in data.get("people", []):
            people.append({
                "name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                "email": person.get("email", ""),
                "title": person.get("title", ""),
                "linkedin_url": person.get("linkedin_url", ""),
                "phone": person.get("phone_number", ""),
            })

        return people


def search_hunter(
    domain: str,
    api_key: str,
    max_results: int = 5,
) -> list[dict]:
    """Search Hunter.io for contacts at a domain.

    Returns list of person dicts with: name, email, title.
    """
    if not domain:
        return []

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": domain,
                "api_key": api_key,
                "limit": max_results,
                "type": "personal",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        people = []
        for email_obj in data.get("data", {}).get("emails", []):
            name_parts = []
            if email_obj.get("first_name"):
                name_parts.append(email_obj["first_name"])
            if email_obj.get("last_name"):
                name_parts.append(email_obj["last_name"])

            people.append({
                "name": " ".join(name_parts),
                "email": email_obj.get("value", ""),
                "title": email_obj.get("position", ""),
                "linkedin_url": email_obj.get("linkedin", ""),
                "phone": "",
            })

        return people


def verify_email_hunter(email: str, api_key: str) -> dict:
    """Verify an email address via Hunter.io.

    Returns dict with: status (valid/invalid/accept_all), score (0-100).
    """
    with httpx.Client(timeout=15) as client:
        resp = client.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": api_key},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {
            "status": data.get("status", "unknown"),
            "score": data.get("score", 0),
        }


def _extract_domain(website: str) -> str:
    """Extract clean domain from a website URL."""
    if not website:
        return ""
    import tldextract
    ext = tldextract.extract(website)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    return ""


def _pick_best_contact(people: list[dict]) -> dict | None:
    """Pick the best contact from a list based on title priority and email availability."""
    # Filter to those with emails
    with_email = [p for p in people if p.get("email")]
    if not with_email:
        # Fall back to anyone with a name
        with_email = [p for p in people if p.get("name")]
    if not with_email:
        return None

    # Sort by title priority
    with_email.sort(key=lambda p: _title_priority(p.get("title", "")))
    return with_email[0]


def enrich_lead_with_contacts(
    lead: Lead,
    apollo_key: str = "",
    hunter_key: str = "",
    verify: bool = False,
) -> Lead:
    """Find and attach the best contact for a lead.

    Waterfall: Apollo first, Hunter as fallback.
    """
    domain = _extract_domain(lead.website)
    best = None

    # Try Apollo first
    if apollo_key:
        try:
            people = search_apollo(lead.business_name, domain, apollo_key)
            best = _pick_best_contact(people)
            if best:
                console.print(f"    Apollo: found {best['name']} ({best['title']})", style="dim")
        except Exception as e:
            console.print(f"    [yellow]Apollo failed: {e}[/]")

    # Fallback to Hunter
    if not best and hunter_key and domain:
        try:
            people = search_hunter(domain, hunter_key)
            best = _pick_best_contact(people)
            if best:
                console.print(f"    Hunter: found {best['name']} ({best['title']})", style="dim")
        except Exception as e:
            console.print(f"    [yellow]Hunter failed: {e}[/]")

    # Apply to lead
    if best:
        lead.contact_name = best.get("name", "")
        lead.contact_email = best.get("email", "")
        lead.contact_title = best.get("title", "")
        lead.linkedin_url = best.get("linkedin_url", "")

        # Optional email verification
        if verify and lead.contact_email and hunter_key:
            try:
                result = verify_email_hunter(lead.contact_email, hunter_key)
                if result["status"] == "invalid":
                    console.print(f"    [yellow]Email invalid, clearing: {lead.contact_email}[/]")
                    lead.contact_email = ""
            except Exception as e:
                console.print(f"    [yellow]Email verification failed: {e}[/]")

    return lead
