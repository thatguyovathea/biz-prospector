"""Deduplication across pipeline runs.

Tracks which leads have been processed to avoid duplicate
enrichment, scoring, and outreach across multiple runs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console

from src.models import Lead

console = Console()

DEDUP_DIR = Path("data/.dedup")


def _get_dedup_path(stage: str) -> Path:
    """Get the dedup tracking file for a pipeline stage."""
    DEDUP_DIR.mkdir(parents=True, exist_ok=True)
    return DEDUP_DIR / f"{stage}_processed.json"


def _load_processed(stage: str) -> dict[str, str]:
    """Load set of processed lead IDs + timestamps for a stage."""
    path = _get_dedup_path(stage)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_processed(stage: str, processed: dict[str, str]):
    """Save processed lead IDs."""
    path = _get_dedup_path(stage)
    with open(path, "w") as f:
        json.dump(processed, f, indent=2)


def filter_new_leads(
    leads: list[Lead],
    stage: str,
) -> tuple[list[Lead], int]:
    """Filter out leads already processed in a given stage.

    Returns:
        Tuple of (new_leads, skipped_count)
    """
    processed = _load_processed(stage)
    new = [l for l in leads if l.id not in processed]
    skipped = len(leads) - len(new)

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
    processed = _load_processed(stage)
    now = datetime.now(timezone.utc).isoformat()

    for lead in leads:
        processed[lead.id] = now

    _save_processed(stage, processed)


def reset_stage(stage: str):
    """Clear all dedup tracking for a stage."""
    path = _get_dedup_path(stage)
    if path.exists():
        path.unlink()
        console.print(f"[yellow]Reset dedup tracking for {stage}[/]")


def get_stats() -> dict[str, int]:
    """Get count of processed leads per stage."""
    stats = {}
    if DEDUP_DIR.exists():
        for path in DEDUP_DIR.glob("*_processed.json"):
            stage = path.stem.replace("_processed", "")
            with open(path) as f:
                data = json.load(f)
            stats[stage] = len(data)
    return stats
