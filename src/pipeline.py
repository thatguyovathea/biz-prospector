"""Main pipeline orchestrator.

Chains: scrape → enrich → score → generate outreach → save results.
Can run full pipeline or individual stages.
All data is persisted via SQLite (see src.db).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import click
from rich.console import Console
from rich.table import Table

from src.config import load_settings, get_scoring_keywords
from src.models import Lead
from src.db import (
    get_db,
    upsert_leads,
    get_leads,
    get_stale_leads,
    start_run,
    finish_run,
    get_run_history,
    get_dedup_stats,
)
from src.scrapers.google_maps import scrape_google_maps
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
from src.dedup import filter_new_leads, mark_processed
from src.reporting.html_report import save_report
from src.notifications.email_summary import send_run_summary
from src.scheduler import install_jobs, list_jobs, remove_jobs

console = Console()


def _get_conn():
    """Return a database connection. Extracted for test patching."""
    return get_db()


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
    conn = _get_conn()
    leads = scrape_google_maps(vertical, metro, count, provider)
    upsert_leads(conn, leads)
    console.print(f"[green]Saved {len(leads)} leads to database[/]")


@cli.command()
@click.option("--metro", default=None, help="Filter leads by metro area")
@click.option("--category", default=None, help="Filter leads by category")
def enrich(metro: str | None, category: str | None):
    """Stage 2: Enrich leads with website audit, reviews, and job postings."""
    conn = _get_conn()
    settings = load_settings()
    leads = get_leads(conn, metro=metro, category=category)

    if not leads:
        console.print("[yellow]No leads found matching filters.[/]")
        return

    console.print(f"[bold]Enriching {len(leads)} leads[/]")

    kw = get_scoring_keywords(settings)
    complaint_kw = kw["ops_complaint_keywords"]
    manual_kw = kw["manual_process_keywords"]

    for i, lead in enumerate(leads):
        console.print(f"  [{i + 1}/{len(leads)}] {lead.business_name}")

        # Website audit
        if lead.website:
            audit = audit_website(lead.website)
            enrich_lead_with_audit(lead, audit)

        # Reviews (if we have a place_id and outscraper key)
        if lead.place_id:
            try:
                outscraper_key = settings.get("apis", {}).get("outscraper_key", "")
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
            serpapi_key = settings.get("apis", {}).get("serpapi_key", "")
            if serpapi_key:
                postings = search_jobs_serpapi(
                    lead.business_name, lead.metro, serpapi_key
                )
                job_analysis = analyze_job_postings(postings, manual_kw)
                enrich_lead_with_jobs(lead, job_analysis)
        except Exception as e:
            console.print(f"    [yellow]Job search failed: {e}[/]")

    upsert_leads(conn, leads)
    console.print(f"[green]Enriched {len(leads)} leads in database[/]")


@cli.command()
@click.option("--metro", default=None, help="Filter leads by metro area")
@click.option("--category", default=None, help="Filter leads by category")
@click.option("--vertical", default=None)
@click.option("--threshold", default=None, type=float)
def score(metro: str | None, category: str | None, vertical: str | None, threshold: float | None):
    """Stage 3: Score enriched leads."""
    conn = _get_conn()
    settings = load_settings()
    leads = get_leads(conn, metro=metro, category=category)

    if not leads:
        console.print("[yellow]No leads found matching filters.[/]")
        return

    scored = score_leads(leads, vertical)

    # Apply threshold
    if threshold is None:
        threshold = settings.get("pipeline", {}).get("score_threshold", 55)
    qualified = [l for l in scored if (l.score or 0) >= threshold]

    console.print(
        f"[bold]{len(qualified)}/{len(scored)} leads above threshold ({threshold})[/]"
    )
    _print_top_leads(qualified)

    upsert_leads(conn, scored)
    console.print(f"[green]Scored {len(scored)} leads in database[/]")


@cli.command()
@click.option("--min-score", default=None, type=float, help="Minimum score threshold")
@click.option("--metro", default=None, help="Filter leads by metro area")
@click.option("--category", default=None, help="Filter leads by category")
def outreach(min_score: float | None, metro: str | None, category: str | None):
    """Stage 4: Generate personalized outreach emails."""
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category, min_score=min_score, scored_only=True)

    if not leads:
        console.print("[yellow]No scored leads found matching filters.[/]")
        return

    results = generate_batch_outreach(leads)
    upsert_leads(conn, results)
    console.print(f"[green]Generated outreach for {len(results)} leads in database[/]")


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
    conn = _get_conn()
    settings = load_settings()
    timestamp = datetime.now().strftime("%Y%m%d")

    threshold = settings.get("pipeline", {}).get("score_threshold", 55)
    run_id = start_run(conn, vertical, metro, threshold=threshold)

    # Stage 1: Scrape
    console.rule("[bold blue]Stage 1: Scraping")
    leads = scrape_google_maps(vertical, metro, count, provider)
    scraped_count = len(leads)
    upsert_leads(conn, leads, run_id=run_id)

    # Dedup against previous runs
    if not skip_dedup:
        leads, skipped = filter_new_leads(leads, "enrich")
        if skipped:
            console.print(f"  Skipped {skipped} previously enriched leads")

    if not leads:
        console.print("[yellow]No new leads to process.[/]")
        finish_run(conn, run_id, {"scraped_count": scraped_count})
        return

    # Stage 2: Enrich (async)
    console.rule("[bold blue]Stage 2: Enriching")
    leads = run_async_enrichment(leads, max_concurrent=concurrent)
    mark_processed(leads, "enrich")
    upsert_leads(conn, leads, run_id=run_id)

    # Stage 3: Score
    console.rule("[bold blue]Stage 3: Scoring")
    scored = score_leads(leads, vertical)
    qualified = [l for l in scored if (l.score or 0) >= threshold]
    _print_top_leads(qualified)
    upsert_leads(conn, qualified, run_id=run_id)

    if not qualified:
        console.print("[yellow]No leads above threshold.[/]")
        finish_run(conn, run_id, {
            "scraped_count": scraped_count,
            "enriched_count": len(leads),
            "qualified_count": 0,
        })
        return

    # Stage 4: Outreach
    console.rule("[bold blue]Stage 4: Generating Outreach")
    results = generate_batch_outreach(qualified)
    upsert_leads(conn, results, run_id=run_id)

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

    # Finalize run
    emailed_count = sum(1 for l in results if l.outreach_email)
    finish_run(conn, run_id, {
        "scraped_count": scraped_count,
        "enriched_count": len(leads),
        "qualified_count": len(qualified),
        "emailed_count": emailed_count,
    })

    # Email notification (for scheduled runs)
    if notify:
        run_info = {
            "vertical": vertical,
            "metro": metro,
            "timestamp": timestamp,
            "scraped_count": scraped_count,
            "qualified_count": len(qualified),
            "threshold": threshold,
            "is_re_enrich": False,
        }
        send_run_summary(results, run_info, settings, report_path=report_path)

    console.rule("[bold green]Pipeline Complete")
    console.print(
        f"Scraped {scraped_count} → Qualified {len(qualified)} → "
        f"Emails generated for {emailed_count}"
    )


@cli.command()
@click.option("--metro", default=None, help="Filter leads by metro area")
@click.option("--category", default=None, help="Filter leads by category")
@click.option("--vertical", default="", help="Vertical name for report title")
@click.option("--output", "output_path", default="", help="Output HTML filename")
def report(metro: str | None, category: str | None, vertical: str, output_path: str):
    """Generate an HTML report from scored/outreach leads."""
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category, scored_only=True)

    if not leads:
        console.print("[yellow]No scored leads found matching filters.[/]")
        return

    metro_label = metro or ""
    title = f"{vertical} {metro_label} Report".strip() if vertical or metro_label else "Pipeline Run Report"
    path = save_report(
        leads,
        filename=output_path,
        title=title,
        vertical=vertical,
        metro=metro_label,
    )
    console.print(f"[green]Report saved to {path}[/]")


@cli.command()
def stats():
    """Show pipeline run history and dedup stats."""
    conn = _get_conn()

    # Run history
    runs = get_run_history(conn)
    if runs:
        run_table = Table(title="Pipeline Run History")
        run_table.add_column("ID", justify="right")
        run_table.add_column("Vertical")
        run_table.add_column("Metro")
        run_table.add_column("Started")
        run_table.add_column("Scraped", justify="right")
        run_table.add_column("Enriched", justify="right")
        run_table.add_column("Qualified", justify="right")
        run_table.add_column("Emailed", justify="right")
        for r in runs:
            run_table.add_row(
                str(r["id"]),
                r["vertical"],
                r["metro"],
                r["started_at"][:16] if r["started_at"] else "—",
                str(r["scraped_count"] or 0),
                str(r["enriched_count"] or 0),
                str(r["qualified_count"] or 0),
                str(r["emailed_count"] or 0),
            )
        console.print(run_table)
    else:
        console.print("No pipeline runs recorded yet.")

    # Dedup stats
    dedup = get_dedup_stats(conn)
    if dedup:
        console.print("\n[bold]Dedup Stats:[/]")
        for stage, count in dedup.items():
            console.print(f"  {stage}: {count} leads processed")


@cli.command(name="re-enrich")
@click.option("--max-age", default=None, type=int, help="Override max_age_days from config")
@click.option("--notify", is_flag=True, help="Send summary email after completion")
def re_enrich(max_age: int | None, notify: bool):
    """Re-enrich and re-score stale leads."""
    conn = _get_conn()
    settings = load_settings()
    max_age_days = max_age or settings.get("schedule", {}).get(
        "re_enrich", {}
    ).get("max_age_days", 30)

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale = get_stale_leads(conn, cutoff)

    if not stale:
        console.print("[yellow]No stale leads to re-enrich.[/]")
        return

    console.print(f"[bold]Re-enriching {len(stale)} stale leads[/]")

    run_id = start_run(conn, "all", "all", is_re_enrich=True)

    enriched = run_async_enrichment(stale)
    scored = score_leads(enriched)
    upsert_leads(conn, scored, run_id=run_id)

    finish_run(conn, run_id, {
        "scraped_count": 0,
        "enriched_count": len(enriched),
        "qualified_count": len(scored),
    })

    console.rule("[bold green]Re-enrichment Complete")
    console.print(f"Refreshed {len(scored)} leads")

    if notify:
        run_info = {
            "vertical": "all",
            "metro": "all",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "scraped_count": 0,
            "qualified_count": len(scored),
            "threshold": settings.get("pipeline", {}).get("score_threshold", 55),
            "is_re_enrich": True,
        }
        send_run_summary(scored, run_info, settings)


@cli.group()
def schedule():
    """Manage scheduled pipeline runs (cron jobs)."""
    pass


@schedule.command(name="install")
def schedule_install():
    """Install cron jobs from settings.yaml schedule config."""
    settings = load_settings()
    try:
        names = install_jobs(settings)
        if names:
            console.print(f"[green]Installed {len(names)} scheduled jobs:[/]")
            for name in names:
                console.print(f"  • {name}")
        else:
            console.print("[yellow]No jobs configured in settings.yaml[/]")
    except ValueError as e:
        console.print(f"[red]{e}[/]")


@schedule.command(name="list")
def schedule_list():
    """List installed biz-prospector cron jobs."""
    jobs = list_jobs()
    if not jobs:
        console.print("No scheduled jobs found.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("Job", style="cyan")
    table.add_column("Schedule")
    for job in jobs:
        table.add_row(job["name"], job["schedule"])
    console.print(table)


@schedule.command(name="remove")
def schedule_remove():
    """Remove all biz-prospector cron jobs."""
    if not click.confirm("Remove all scheduled biz-prospector jobs?"):
        return
    count = remove_jobs()
    if count > 0:
        console.print(f"[green]Removed {count} scheduled job(s)[/]")
    else:
        console.print("No scheduled jobs to remove.")


@cli.command(name="import-json")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
def import_json(input_path: str):
    """Import leads from a JSON file into the database."""
    with open(input_path) as f:
        data = json.load(f)
    leads = [Lead(**item) for item in data]
    conn = _get_conn()
    count = upsert_leads(conn, leads)
    console.print(f"[green]Imported {count} leads from {input_path}[/]")


@cli.command(name="export-json")
@click.option("--output", "output_path", required=True, type=click.Path())
@click.option("--metro", default=None)
@click.option("--category", default=None)
@click.option("--min-score", default=None, type=float)
def export_json(output_path: str, metro: str | None, category: str | None, min_score: float | None):
    """Export leads from the database to a JSON file."""
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category, min_score=min_score)
    with open(output_path, "w") as f:
        json.dump([l.model_dump(mode="json") for l in leads], f, indent=2)
    console.print(f"[green]Exported {len(leads)} leads to {output_path}[/]")


if __name__ == "__main__":
    cli()
