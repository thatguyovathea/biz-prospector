"""Scoring engine.

Takes enriched leads and produces a 0-100 modernization score
based on configurable weighted factors.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console

from src.config import load_settings, load_vertical
from src.models import Lead

console = Console()


# Default weights (overridden by config)
DEFAULT_WEIGHTS = {
    "website_outdated": 20,
    "no_crm_detected": 15,
    "no_scheduling_tool": 10,
    "no_chat_widget": 5,
    "manual_job_postings": 25,
    "negative_reviews_ops": 15,
    "business_age": 5,
    "employee_count": 5,
}


def _normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize a value to 0-1 range."""
    if max_val == min_val:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def score_lead(lead: Lead, weights: dict[str, float] | None = None) -> Lead:
    """Score a single lead based on enrichment data.

    Each factor produces a 0-1 sub-score, multiplied by its weight.
    Final score is normalized to 0-100.
    """
    w = weights or DEFAULT_WEIGHTS
    total_weight = sum(w.values())
    breakdown = {}
    raw_score = 0.0

    # --- Website outdatedness ---
    website_score = 0.0
    if lead.has_ssl is False:
        website_score += 0.3
    if lead.is_mobile_responsive is False:
        website_score += 0.4
    if lead.tech_stack:
        # Penalize if using very old tech
        old_tech = {"wordpress"}  # WP alone isn't bad, but combined with other signals
        # Bonus if no modern framework detected
        modern = {"react", "angular", "vue", "tailwind"}
        if not any(t in modern for t in lead.tech_stack):
            website_score += 0.3
    website_score = min(1.0, website_score)
    breakdown["website_outdated"] = website_score
    raw_score += website_score * w.get("website_outdated", 0)

    # --- No CRM ---
    crm_score = 1.0 if lead.has_crm is False else 0.0
    breakdown["no_crm_detected"] = crm_score
    raw_score += crm_score * w.get("no_crm_detected", 0)

    # --- No scheduling tool ---
    sched_score = 1.0 if lead.has_scheduling is False else 0.0
    breakdown["no_scheduling_tool"] = sched_score
    raw_score += sched_score * w.get("no_scheduling_tool", 0)

    # --- No chat widget ---
    chat_score = 1.0 if lead.has_chat_widget is False else 0.0
    breakdown["no_chat_widget"] = chat_score
    raw_score += chat_score * w.get("no_chat_widget", 0)

    # --- Manual process job postings ---
    if lead.active_job_postings > 0:
        job_score = _normalize(lead.manual_process_postings, 0, 3)
    else:
        job_score = 0.0  # No data, don't penalize or reward
    breakdown["manual_job_postings"] = job_score
    raw_score += job_score * w.get("manual_job_postings", 0)

    # --- Negative reviews about operations ---
    if lead.reviews_analyzed > 0:
        complaint_ratio = lead.ops_complaint_count / lead.reviews_analyzed
        review_score = _normalize(complaint_ratio, 0, 0.15)

        # Bonus: low owner response rate compounds the signal
        if lead.owner_response_rate is not None and lead.owner_response_rate < 0.2:
            review_score = min(1.0, review_score + 0.2)
    else:
        review_score = 0.0
    breakdown["negative_reviews_ops"] = review_score
    raw_score += review_score * w.get("negative_reviews_ops", 0)

    # --- Business age (placeholder — would need external data) ---
    breakdown["business_age"] = 0.0  # TODO: enrich with founding date

    # --- Employee count (placeholder) ---
    breakdown["employee_count"] = 0.0  # TODO: enrich with headcount

    # Normalize to 0-100
    if total_weight > 0:
        final_score = (raw_score / total_weight) * 100
    else:
        final_score = 0.0

    lead.score = round(final_score, 1)
    lead.score_breakdown = {k: round(v, 3) for k, v in breakdown.items()}
    lead.scored_at = datetime.now(timezone.utc)

    return lead


def score_leads(
    leads: list[Lead],
    vertical: str | None = None,
) -> list[Lead]:
    """Score a batch of leads. Returns sorted by score descending."""
    settings = load_settings()
    weights = settings.get("scoring", {}).get("weights", DEFAULT_WEIGHTS)

    # Apply vertical overrides if specified
    if vertical:
        vert_config = load_vertical(vertical)
        if vert_config.get("weights"):
            weights = {**weights, **vert_config["weights"]}

    console.print(f"[bold]Scoring {len(leads)} leads[/]")
    scored = [score_lead(lead, weights) for lead in leads]
    scored.sort(key=lambda l: l.score or 0, reverse=True)

    # Summary stats
    scores = [l.score for l in scored if l.score is not None]
    if scores:
        console.print(
            f"  Score range: {min(scores):.1f} - {max(scores):.1f}, "
            f"Mean: {sum(scores) / len(scores):.1f}"
        )

    return scored
