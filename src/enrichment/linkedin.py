"""LinkedIn enrichment module.

Fetches employee rosters from Apollo People Search API and analyzes
job titles for manual-process vs. tech-maturity signals.
"""

from __future__ import annotations

import httpx
from rich.console import Console

console = Console()


def fetch_company_employees(
    domain: str,
    api_key: str,
    max_results: int = 25,
) -> dict:
    """Fetch employees at a company via Apollo People Search.

    Uses the free People Search endpoint (no credits consumed).
    Returns dict with: titles (list[str]), employee_count, founded_year,
    company_linkedin_url.
    """
    empty = {
        "titles": [],
        "employee_count": None,
        "founded_year": None,
        "company_linkedin_url": "",
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                "https://api.apollo.io/v1/mixed_people/search",
                json={
                    "api_key": api_key,
                    "q_organization_domains": domain,
                    "per_page": max_results,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        console.print(f"    [yellow]Employee fetch failed: {e}[/]")
        return empty

    people = data.get("people", [])
    if not people:
        return empty

    titles = [p.get("title", "") for p in people if p.get("title")]

    # Extract company metadata from first person with organization data
    employee_count = None
    founded_year = None
    company_linkedin_url = ""
    for person in people:
        org = person.get("organization", {})
        if org.get("estimated_num_employees") is not None:
            employee_count = org["estimated_num_employees"]
        if org.get("founded_year") is not None:
            founded_year = org["founded_year"]
        if org.get("linkedin_url"):
            company_linkedin_url = org["linkedin_url"]
        if employee_count is not None and founded_year is not None:
            break

    return {
        "titles": titles,
        "employee_count": employee_count,
        "founded_year": founded_year,
        "company_linkedin_url": company_linkedin_url,
    }
