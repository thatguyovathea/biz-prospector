"""BuiltWith API integration for tech stack detection.

Calls the BuiltWith Domain API (v22) to get comprehensive technology
data for a website, then merges with HTML-based detection results.
"""

from __future__ import annotations

import re

import httpx
from rich.console import Console

from src.rate_limit import retry_with_rate_limit

console = Console()

BUILTWITH_API_URL = "https://api.builtwith.com/v22/api.json"


def _normalize_tech_name(name: str) -> str:
    """Normalize a technology name to a lowercase slug.

    Examples:
        "WordPress 6.4" → "wordpress"
        "jQuery 3.7.1" → "jquery"
        "Google Analytics" → "google_analytics"
        "HubSpot CRM" → "hubspot_crm"
    """
    # Remove version numbers
    name = re.sub(r"\s+[\d.]+.*$", "", name.strip())
    # Lowercase and replace spaces/special chars with underscores
    name = re.sub(r"[^a-z0-9]+", "_", name.lower())
    # Strip leading/trailing underscores
    return name.strip("_")


def parse_builtwith_response(data: dict) -> list[dict]:
    """Extract technology entries from BuiltWith API response.

    Returns list of dicts with keys: name, normalized, tag, categories.
    """
    techs = []
    results = data.get("Results", [])
    if not results:
        return techs

    result = results[0].get("Result", {})
    paths = result.get("Paths", [])

    for path in paths:
        for tech in path.get("Technologies", []):
            name = tech.get("Name", "")
            if not name:
                continue
            techs.append({
                "name": name,
                "normalized": _normalize_tech_name(name),
                "tag": tech.get("Tag", ""),
                "categories": tech.get("Categories", []),
            })

    return techs


def merge_tech_stacks(html_tech: list[str], builtwith_tech: list[dict]) -> list[str]:
    """Merge HTML-detected and BuiltWith tech into a deduplicated list.

    HTML tech names are already normalized lowercase slugs.
    BuiltWith tech is normalized via _normalize_tech_name.
    Returns sorted unique list of normalized tech names.
    """
    seen = set(html_tech)
    merged = list(html_tech)

    for tech in builtwith_tech:
        normalized = tech["normalized"]
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)

    return sorted(merged)


@retry_with_rate_limit("builtwith", max_attempts=3)
def fetch_builtwith(domain: str, api_key: str, timeout: int = 15) -> list[dict]:
    """Fetch tech stack from BuiltWith API.

    Args:
        domain: Domain to look up (e.g., "acmehvac.com").
        api_key: BuiltWith API key.
        timeout: Request timeout in seconds.

    Returns:
        List of parsed technology dicts from parse_builtwith_response.
        Empty list on any failure.
    """
    if not domain or not api_key:
        return []

    # Strip protocol if present
    domain = re.sub(r"^https?://", "", domain).strip("/")

    try:
        resp = httpx.get(
            BUILTWITH_API_URL,
            params={
                "KEY": api_key,
                "LOOKUP": domain,
                "HIDETEXT": "yes",
                "HIDEDL": "yes",
                "NOPII": "yes",
                "NOATTR": "yes",
            },
            timeout=timeout,
        )

        if resp.status_code in (401, 403):
            console.print("[yellow]BuiltWith: invalid API key, skipping[/]")
            return []

        resp.raise_for_status()
        data = resp.json()
        return parse_builtwith_response(data)

    except httpx.TimeoutException:
        console.print("[yellow]BuiltWith: timeout, skipping[/]")
        return []
    except httpx.HTTPStatusError:
        raise  # Let retry_with_rate_limit handle retryable errors
    except Exception as e:
        console.print(f"[yellow]BuiltWith: {str(e)[:100]}, skipping[/]")
        return []
