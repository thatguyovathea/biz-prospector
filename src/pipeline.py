"""Main pipeline orchestrator.

Chains: scrape → enrich → score → generate outreach → save results.
Can run full pipeline or individual stages.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.config import load_settings
from src.models import Lead
from src.scrapers.google_maps import scrape_google_maps, save_leads
from src.enrichment.website_audit import audit_website, enrich_lead_with_audit
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
from src.scoring.score import score_leads
from src.outreach.generate import generate_batch_outreach
from src.outreach.delivery import push_to_instantly
from src.enrichment.async_processor import run_async_enrichment
from src.dedup import filter_new_leads, mark_processed, get_stats
from src.reporting.html_report import save_report
from src.notifications.email_summary import send_run_summary

console = Console()
DATA_DIR = Path("data")


def _load_leads(path: str) -> list[Lead]:
    """Load leads from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    return [Lead(**item) for item in data]


def _save_json(leads: list[Lead], subdir: str, filename: str) -> Path:
    """Save leads to a JSON file in the specified data subdirectory."""
    out_dir = DATA_DIR / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    with open(path, "w") as f:
        json.dump([l.model_dump(mode="json") for l in leads], f, indent=2)
    console.print(f"[green]Saved {len(leads)} leads to {path}[/]")
    return path


def _print_top_leads(leads: list[Lead], n: int = 10):
    """Print a summary table of top scored leads."""
    table = Table(title=f"Top {n} Leads by Score")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Business", style="cyan")
    table.add_column("Category")
    table.add_column("CRM", justify="center")
    table.add_column("Chat", justify="center")
    table.add_column("Sched", justify="center")
    table.add_column("Job Flags", justify="right")
    table.add_column("Rev Complaints", justify="right")

    for lead in leads[:n]:
        table.add_row(
            f"{lead.score:.1f}" if lead.score else "—",
            lead.business_name[:30],
            lead.category[:20],
            "✗" if lead.has_crm is False else ("✓" if lead.has_crm else "?"),
            "✗" if lead.has_chat_widget is False else ("✓" if lead.has_chat_widget else "?"),
            "✗" if lead.has_scheduling is False else ("✓" if lead.has_scheduling else "?"),
            str(lead.manual_process_postings),
            str(lead.ops_complaint_count),
        )

    console.print(table)


@click.group()
def cli():
    """biz-prospector: find and reach businesses needing modernization."""
    pass


@cli.command()
@click.option("--vertical", required=True)
@click.option("--metro", required=True)
@click.option("--count", default=100)
@click.option("--provider", default="serpapi", type=click.Choice(["serpapi", "apify"]))
def scrape(vertical: str, metro: str, count: int, provider: str):
    """Stage 1: Scrape business listings from Google Maps."""
    leads = scrape_google_maps(vertical, metro, count, provider)
    slug = f"{vertical}_{metro}_{datetime.now().strftime('%Y%m%d')}"
    save_leads(leads, f"{slug}.json")


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
def enrich(input_path: str):
    """Stage 2: Enrich leads with website audit, reviews, and job postings."""
    settings = load_settings()
    leads = _load_leads(input_path)
    console.print(f"[bold]Enriching {len(leads)} leads[/]")

    complaint_kw = settings.get("scoring", {}).get("ops_complaint_keywords", [])
    manual_kw = settings.get("scoring", {}).get("manual_process_keywords", [])

    for i, lead in enumerate(leads):
        console.print(f"  [{i + 1}/{len(leads)}] {lead.business_name}")

        # Website audit
        if lead.website:
            audit = audit_website(lead.website)
            enrich_lead_with_audit(lead, audit)

        # Reviews (if we have a place_id and outscraper key)
        if lead.place_id:
            try:
                outscraper_key = settings["apis"].get("outscraper_key", "")
                if outscraper_key:
                    reviews = fetch_reviews_outscraper(
                        lead.place_id, outscraper_key
                    )
                    analysis = analyze_reviews(reviews, complaint_kw)
                    enrich_lead_with_reviews(lead, analysis)
            except Exception as e:
                console.print(f"    [yellow]Review fetch failed: {e}[/]")

        # Job postings
        try:
            serpapi_key = settings["apis"].get("serpapi_key", "")
            if serpapi_key:
                postings = search_jobs_serpapi(
                    lead.business_name, lead.metro, serpapi_key
                )
                job_analysis = analyze_job_postings(postings, manual_kw)
                enrich_lead_with_jobs(lead, job_analysis)
        except Exception as e:
            console.print(f"    [yellow]Job search failed: {e}[/]")

    slug = Path(input_path).stem + "_enriched"
    _save_json(leads, "raw", f"{slug}.json")


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
@click.option("--vertical", default=None)
@click.option("--threshold", default=None, type=float)
def score(input_path: str, vertical: str | None, threshold: float | None):
    """Stage 3: Score enriched leads."""
    settings = load_settings()
    leads = _load_leads(input_path)
    scored = score_leads(leads, vertical)

    # Apply threshold
    if threshold is None:
        threshold = settings.get("pipeline", {}).get("score_threshold", 55)
    qualified = [l for l in scored if (l.score or 0) >= threshold]

    console.print(
        f"[bold]{len(qualified)}/{len(scored)} leads above threshold ({threshold})[/]"
    )
    _print_top_leads(qualified)

    slug = Path(input_path).stem.replace("_enriched", "") + "_scored"
    _save_json(qualified, "scored", f"{slug}.json")


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
def outreach(input_path: str):
    """Stage 4: Generate personalized outreach emails."""
    leads = _load_leads(input_path)
    results = generate_batch_outreach(leads)

    slug = Path(input_path).stem.replace("_scored", "") + "_outreach"
    _save_json(results, "outreach", f"{slug}.json")


@cli.command()
@click.option("--vertical", required=True)
@click.option("--metro", required=True)
@click.option("--count", default=100)
@click.option("--provider", default="serpapi", type=click.Choice(["serpapi", "apify"]))
@click.option("--concurrent", default=10, help="Max concurrent enrichment tasks")
@click.option("--skip-dedup", is_flag=True, help="Process all leads even if seen before")
@click.option("--push-instantly", is_flag=True, help="Push results to Instantly.ai")
@click.option("--notify", is_flag=True, help="Send summary email after completion")
def run(
    vertical: str,
    metro: str,
    count: int,
    provider: str,
    concurrent: int,
    skip_dedup: bool,
    push_instantly: bool,
    notify: bool,
):
    """Run the full pipeline: scrape → enrich → score → outreach → [deliver]."""
    settings = load_settings()
    timestamp = datetime.now().strftime("%Y%m%d")
    slug = f"{vertical}_{metro}_{timestamp}"

    # Stage 1: Scrape
    console.rule("[bold blue]Stage 1: Scraping")
    leads = scrape_google_maps(vertical, metro, count, provider)
    _save_json(leads, "raw", f"{slug}.json")

    # Dedup against previous runs
    if not skip_dedup:
        leads, skipped = filter_new_leads(leads, "enrich")
        if skipped:
            console.print(f"  Skipped {skipped} previously enriched leads")

    if not leads:
        console.print("[yellow]No new leads to process.[/]")
        return

    # Stage 2: Enrich (async)
    console.rule("[bold blue]Stage 2: Enriching")
    leads = run_async_enrichment(leads, max_concurrent=concurrent)
    mark_processed(leads, "enrich")
    _save_json(leads, "raw", f"{slug}_enriched.json")

    # Stage 3: Score
    console.rule("[bold blue]Stage 3: Scoring")
    scored = score_leads(leads, vertical)
    threshold = settings.get("pipeline", {}).get("score_threshold", 55)
    qualified = [l for l in scored if (l.score or 0) >= threshold]
    _print_top_leads(qualified)
    _save_json(qualified, "scored", f"{slug}_scored.json")

    if not qualified:
        console.print("[yellow]No leads above threshold.[/]")
        return

    # Stage 4: Outreach
    console.rule("[bold blue]Stage 4: Generating Outreach")
    results = generate_batch_outreach(qualified)
    _save_json(results, "outreach", f"{slug}_outreach.json")

    # Stage 5: Delivery (optional)
    if push_instantly:
        console.rule("[bold blue]Stage 5: Pushing to Instantly")
        followup_days = settings.get("outreach", {}).get("followup_interval_days", 3)
        delivery = push_to_instantly(
            results,
            campaign_name=f"{vertical} {metro} {timestamp}",
            followup_interval_days=followup_days,
        )
        console.print(f"  Campaign: {delivery.get('campaign_id')}")
        console.print(f"  Leads added: {delivery.get('leads_added')}")

    # Generate HTML report
    report_path = save_report(
        results,
        title=f"{vertical} {metro} Pipeline Report",
        vertical=vertical,
        metro=metro,
    )
    console.print(f"  Report: {report_path}")

    # Email notification (for scheduled runs)
    if notify:
        run_info = {
            "vertical": vertical,
            "metro": metro,
            "timestamp": timestamp,
            "scraped_count": len(leads),
            "qualified_count": len(qualified),
            "threshold": threshold,
            "is_re_enrich": False,
        }
        send_run_summary(results, run_info, settings, report_path=report_path)

    console.rule("[bold green]Pipeline Complete")
    console.print(
        f"Scraped {len(leads)} → Qualified {len(qualified)} → "
        f"Emails generated for {sum(1 for l in results if l.outreach_email)}"
    )


@cli.command()
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
@click.option("--vertical", default="")
@click.option("--metro", default="")
@click.option("--output", "output_path", default="", help="Output HTML filename")
def report(input_path: str, vertical: str, metro: str, output_path: str):
    """Generate an HTML report from scored/outreach leads."""
    leads = _load_leads(input_path)
    title = f"{vertical} {metro} Report".strip() if vertical or metro else "Pipeline Run Report"
    path = save_report(
        leads,
        filename=output_path,
        title=title,
        vertical=vertical,
        metro=metro,
    )
    console.print(f"[green]Report saved to {path}[/]")


@cli.command()
def stats():
    """Show dedup stats across pipeline stages."""
    s = get_stats()
    if not s:
        console.print("No leads processed yet.")
        return
    for stage, count in s.items():
        console.print(f"  {stage}: {count} leads processed")


if __name__ == "__main__":
    cli()
