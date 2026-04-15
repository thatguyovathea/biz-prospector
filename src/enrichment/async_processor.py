"""Async enrichment processor.

Runs website audits and API enrichment concurrently instead of
sequentially, with rate limiting per service.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from src.config import load_settings
from src.models import Lead
from src.enrichment.website_audit import audit_website, enrich_lead_with_audit
from src.enrichment.contacts import enrich_lead_contacts, _extract_domain
from src.enrichment.linkedin import fetch_company_employees, enrich_lead_with_titles
from src.scrapers.reviews import (
    fetch_reviews_outscraper,
    analyze_reviews,
    enrich_lead_with_reviews,
)
from src.scrapers.job_posts import (
    search_jobs_serpapi,
    analyze_job_postings,
    enrich_lead_with_jobs,
)
from src.rate_limit import get_limiter

console = Console()


async def _enrich_single(
    lead: Lead,
    settings: dict,
    semaphore: asyncio.Semaphore,
    complaint_kw: list[str],
    manual_kw: list[str],
    manual_role_kw: list[str],
    tech_role_kw: list[str],
) -> Lead:
    """Enrich a single lead with all available data sources."""
    async with semaphore:
        loop = asyncio.get_running_loop()

        # Website audit (CPU-bound-ish, run in thread)
        if lead.website:
            limiter = get_limiter("website_audit")
            await limiter.async_wait()
            builtwith_key = settings.get("apis", {}).get("builtwith_key", "")
            audit = await loop.run_in_executor(
                None, lambda: audit_website(lead.website, builtwith_key=builtwith_key)
            )
            enrich_lead_with_audit(lead, audit)

        # Reviews
        outscraper_key = settings.get("apis", {}).get("outscraper_key", "")
        if lead.place_id and outscraper_key:
            try:
                limiter = get_limiter("outscraper")
                await limiter.async_wait()
                reviews = await loop.run_in_executor(
                    None, fetch_reviews_outscraper, lead.place_id, outscraper_key
                )
                analysis = analyze_reviews(reviews, complaint_kw)
                enrich_lead_with_reviews(lead, analysis)
            except Exception:
                pass

        # Job postings
        serpapi_key = settings.get("apis", {}).get("serpapi_key", "")
        if serpapi_key:
            try:
                limiter = get_limiter("serpapi")
                await limiter.async_wait()
                postings = await loop.run_in_executor(
                    None, search_jobs_serpapi, lead.business_name, lead.metro, serpapi_key
                )
                job_analysis = analyze_job_postings(postings, manual_kw)
                enrich_lead_with_jobs(lead, job_analysis)
            except Exception:
                pass

        # Contact enrichment
        apollo_key = settings.get("apis", {}).get("apollo_key", "")
        hunter_key = settings.get("apis", {}).get("hunter_key", "")
        if apollo_key or hunter_key:
            try:
                contact_limiter = get_limiter("apollo" if apollo_key else "hunter")
                await contact_limiter.async_wait()
                await loop.run_in_executor(
                    None, enrich_lead_contacts, lead, apollo_key, hunter_key, True
                )
            except Exception:
                pass

        # Employee title analysis (uses Apollo People Search — free endpoint)
        if apollo_key and lead.website:
            try:
                limiter = get_limiter("apollo")
                await limiter.async_wait()
                domain = _extract_domain(lead.website)
                if domain:
                    employees = await loop.run_in_executor(
                        None, fetch_company_employees, domain, apollo_key
                    )
                    enrich_lead_with_titles(lead, employees, manual_role_kw, tech_role_kw)
            except Exception:
                pass

        lead.enriched_at = datetime.now(timezone.utc)
        return lead


async def enrich_leads_async(
    leads: list[Lead],
    max_concurrent: int = 10,
) -> list[Lead]:
    """Enrich leads concurrently with rate limiting.

    Args:
        leads: List of leads to enrich.
        max_concurrent: Max simultaneous enrichment tasks.
    """
    settings = load_settings()
    complaint_kw = settings.get("scoring", {}).get("ops_complaint_keywords", [])
    manual_kw = settings.get("scoring", {}).get("manual_process_keywords", [])
    manual_role_kw = settings.get("scoring", {}).get("manual_role_keywords", [])
    tech_role_kw = settings.get("scoring", {}).get("tech_role_keywords", [])
    semaphore = asyncio.Semaphore(max_concurrent)

    console.print(
        f"[bold]Enriching {len(leads)} leads "
        f"(max {max_concurrent} concurrent)[/]"
    )

    tasks = [
        _enrich_single(lead, settings, semaphore, complaint_kw, manual_kw,
                        manual_role_kw, tech_role_kw)
        for lead in leads
    ]

    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task_id = progress.add_task("Enriching...", total=len(tasks))

        for coro in asyncio.as_completed(tasks):
            lead = await coro
            results.append(lead)
            progress.advance(task_id)

    # Preserve original order
    lead_map = {l.id: l for l in results}
    ordered = [lead_map.get(l.id, l) for l in leads]

    enriched_count = sum(1 for l in ordered if l.enriched_at)
    console.print(f"[green]Enriched {enriched_count}/{len(leads)} leads[/]")

    return ordered


def run_async_enrichment(leads: list[Lead], max_concurrent: int = 10) -> list[Lead]:
    """Synchronous wrapper for async enrichment."""
    return asyncio.run(enrich_leads_async(leads, max_concurrent))
