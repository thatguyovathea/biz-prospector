"""Google Maps scraper using SerpAPI or Apify.

Pulls business listings by industry + metro area.
Outputs raw Lead objects with basic info populated.
"""

from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.progress import track

from src.config import load_settings, get_api_key
from src.models import Lead, LeadSource

console = Console()
DATA_DIR = Path("data/raw")


def scrape_serpapi(
    query: str, location: str, api_key: str, num_results: int = 100
) -> list[dict]:
    """Pull Google Maps results via SerpAPI."""
    results = []
    params = {
        "engine": "google_maps",
        "q": query,
        "ll": location,  # lat,lng format or location string
        "type": "search",
        "api_key": api_key,
    }

    with httpx.Client(timeout=30) as client:
        # SerpAPI paginates via start param
        start = 0
        while len(results) < num_results:
            params["start"] = start
            resp = client.get("https://serpapi.com/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            local_results = data.get("local_results", [])
            if not local_results:
                break

            results.extend(local_results)
            start += len(local_results)

            console.print(
                f"  Fetched {len(results)} results so far...", style="dim"
            )

    return results[:num_results]


def scrape_apify(
    query: str, location: str, api_token: str, num_results: int = 100
) -> list[dict]:
    """Pull Google Maps results via Apify Google Maps Scraper actor."""
    actor_id = "nwua9Gu5YrADL7ZDj"  # Google Maps Scraper
    run_input = {
        "searchStringsArray": [query],
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": num_results,
        "language": "en",
        "includeWebResults": False,
    }

    with httpx.Client(timeout=120) as client:
        # Start actor run
        resp = client.post(
            f"https://api.apify.com/v2/acts/{actor_id}/runs",
            params={"token": api_token},
            json=run_input,
        )
        resp.raise_for_status()
        run_data = resp.json()["data"]
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

        console.print(f"  Apify run started: {run_id}", style="dim")

        # Poll until finished (simplified — production would use webhooks)
        for _ in range(60):  # 5 min timeout
            status_resp = client.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}",
                params={"token": api_token},
            )
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify run failed with status: {status}")
            time.sleep(5)

        # Fetch results
        items_resp = client.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            params={"token": api_token, "format": "json"},
        )
        items_resp.raise_for_status()
        return items_resp.json()


def _make_id(name: str, address: str) -> str:
    """Generate a stable ID from business name + address."""
    raw = f"{name.lower().strip()}|{address.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def parse_serpapi_result(item: dict, metro: str) -> Lead:
    """Convert a SerpAPI result to a Lead."""
    return Lead(
        id=_make_id(item.get("title", ""), item.get("address", "")),
        business_name=item.get("title", ""),
        address=item.get("address", ""),
        phone=item.get("phone", ""),
        website=item.get("website", ""),
        category=item.get("type", ""),
        metro=metro,
        source=LeadSource.GOOGLE_MAPS,
        rating=item.get("rating"),
        review_count=item.get("reviews"),
        place_id=item.get("place_id", ""),
        scraped_at=datetime.now(timezone.utc),
    )


def parse_apify_result(item: dict, metro: str) -> Lead:
    """Convert an Apify result to a Lead."""
    return Lead(
        id=_make_id(item.get("title", ""), item.get("address", "")),
        business_name=item.get("title", ""),
        address=item.get("address", ""),
        phone=item.get("phone", ""),
        website=item.get("website", item.get("url", "")),
        category=item.get("categoryName", ""),
        metro=metro,
        source=LeadSource.GOOGLE_MAPS,
        rating=item.get("totalScore"),
        review_count=item.get("reviewsCount"),
        place_id=item.get("placeId", ""),
        scraped_at=datetime.now(timezone.utc),
    )


def scrape_google_maps(
    vertical: str,
    metro: str,
    num_results: int = 100,
    provider: str = "serpapi",
) -> list[Lead]:
    """Main entry point: scrape Google Maps for a vertical + metro."""
    settings = load_settings()
    query = f"{vertical} near {metro}"

    console.print(f"[bold]Scraping Google Maps:[/] {query}")
    console.print(f"  Provider: {provider}, Target: {num_results} results")

    if provider == "serpapi":
        api_key = get_api_key(settings, "serpapi_key")
        raw = scrape_serpapi(query, metro, api_key, num_results)
        leads = [parse_serpapi_result(r, metro) for r in raw]
    elif provider == "apify":
        api_token = get_api_key(settings, "apify_token")
        raw = scrape_apify(query, metro, api_token, num_results)
        leads = [parse_apify_result(r, metro) for r in raw]
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Deduplicate by ID
    seen = set()
    unique = []
    for lead in leads:
        if lead.id not in seen:
            seen.add(lead.id)
            unique.append(lead)

    console.print(
        f"[green]Got {len(unique)} unique leads[/] ({len(leads) - len(unique)} dupes removed)"
    )
    return unique


def save_leads(leads: list[Lead], filename: str) -> Path:
    """Save leads to JSON file in data/raw/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump([l.model_dump(mode="json") for l in leads], f, indent=2)
    console.print(f"[green]Saved {len(leads)} leads to {path}[/]")
    return path


@click.command()
@click.option("--vertical", required=True, help="Business vertical (e.g., hvac, dental, legal)")
@click.option("--metro", required=True, help="Metro area (e.g., portland-or, seattle-wa)")
@click.option("--count", default=100, help="Number of results to fetch")
@click.option("--provider", default="serpapi", type=click.Choice(["serpapi", "apify"]))
def main(vertical: str, metro: str, count: int, provider: str):
    leads = scrape_google_maps(vertical, metro, count, provider)
    slug = f"{vertical}_{metro}_{datetime.now().strftime('%Y%m%d')}"
    save_leads(leads, f"{slug}.json")


if __name__ == "__main__":
    main()
