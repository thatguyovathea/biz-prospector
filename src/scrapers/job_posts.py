"""Job posting scraper.

Searches for active job postings from target businesses
and flags roles that indicate manual/outdated processes.
"""

from __future__ import annotations

import httpx
from rich.console import Console
from src.models import Lead

console = Console()


def search_jobs_serpapi(
    company_name: str, location: str, api_key: str
) -> list[dict]:
    """Search for job postings by company via SerpAPI Google Jobs."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_jobs",
                "q": f"{company_name} jobs",
                "location": location,
                "api_key": api_key,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("jobs_results", [])


def search_jobs_apify(
    company_name: str, location: str, api_token: str
) -> list[dict]:
    """Search Indeed for job postings via Apify."""
    actor_id = "hMvNSpz3JnHgl5jkh"  # Indeed Scraper
    run_input = {
        "position": "",
        "country": "US",
        "location": location,
        "company": company_name,
        "maxItems": 20,
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items",
            params={"token": api_token},
            json=run_input,
        )
        resp.raise_for_status()
        return resp.json()


def analyze_job_postings(
    postings: list[dict],
    manual_keywords: list[str],
) -> dict:
    """Analyze job postings for manual process signals.

    Returns:
        dict with:
            - total_postings: int
            - manual_process_count: int
            - manual_process_titles: list[str]
    """
    manual_matches = []

    for posting in postings:
        title = posting.get("title", "").lower()
        description = posting.get("description", "").lower()
        combined = f"{title} {description}"

        for keyword in manual_keywords:
            if keyword.lower() in combined:
                manual_matches.append(posting.get("title", "Unknown"))
                break

    return {
        "total_postings": len(postings),
        "manual_process_count": len(manual_matches),
        "manual_process_titles": manual_matches,
    }


def enrich_lead_with_jobs(lead: Lead, job_analysis: dict) -> Lead:
    """Apply job posting analysis to a Lead."""
    lead.active_job_postings = job_analysis["total_postings"]
    lead.manual_process_postings = job_analysis["manual_process_count"]
    lead.manual_process_titles = job_analysis["manual_process_titles"]
    return lead
