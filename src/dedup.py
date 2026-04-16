"""Deduplication across pipeline runs.

Tracks which leads have been processed to avoid duplicate
enrichment, scoring, and outreach across multiple runs.

Delegates to the SQLite backend in src.db.
"""

from __future__ import annotations

from rich.console import Console

from src import db
from src.db import get_db
from src.models import Lead

console = Console()


def _get_conn():
    """Return a database connection. Extracted for test patching."""
    return get_db()


def filter_new_leads(
    leads: list[Lead],
    stage: str,
) -> tuple[list[Lead], int]:
    """Filter out leads already processed in a given stage.

    Returns:
        Tuple of (new_leads, skipped_count)
    """
    conn = _get_conn()
    new, skipped = db.filter_new_leads(conn, leads, stage)

    if skipped > 0:
        console.print(
            f"  [dim]Dedup: {skipped} already processed for {stage}, "
            f"{len(new)} new[/]"
        )

    return new, skipped


def mark_processed(
    leads: list[Lead],
    stage: str,
):
    """Mark leads as processed for a stage."""
    conn = _get_conn()
    db.mark_processed(conn, leads, stage)


def reset_stage(stage: str):
    """Clear all dedup tracking for a stage."""
    conn = _get_conn()
    conn.execute("DELETE FROM dedup WHERE stage = ?", (stage,))
    conn.commit()
    console.print(f"[yellow]Reset dedup tracking for {stage}[/]")


def get_stats() -> dict[str, int]:
    """Get count of processed leads per stage."""
    conn = _get_conn()
    return db.get_dedup_stats(conn)
