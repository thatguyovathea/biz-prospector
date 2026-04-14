"""Review scraper and analyzer.

Pulls Google/Yelp reviews and analyzes for operational complaints
that signal a business needs modernization.
"""

from __future__ import annotations

import re

import httpx
from rich.console import Console

from src.config import load_settings, get_api_key
from src.models import Lead

console = Console()


def fetch_reviews_outscraper(
    place_id: str, api_key: str, limit: int = 50
) -> list[dict]:
    """Fetch Google reviews via Outscraper API."""
    with httpx.Client(timeout=60) as client:
        resp = client.get(
            "https://api.app.outscraper.com/maps/reviews-v3",
            params={
                "query": place_id,
                "reviewsLimit": limit,
                "language": "en",
                "sort": "newest",
            },
            headers={"X-API-KEY": api_key},
        )
        resp.raise_for_status()
        data = resp.json()

        # Outscraper returns nested structure
        if data.get("data") and len(data["data"]) > 0:
            place_data = data["data"][0]
            return place_data.get("reviews_data", [])
        return []


def analyze_reviews(
    reviews: list[dict],
    complaint_keywords: list[str],
) -> dict:
    """Analyze reviews for operational complaint signals.

    Returns:
        dict with keys:
            - total_analyzed: int
            - ops_complaint_count: int
            - ops_complaint_samples: list[str] (up to 5 example snippets)
            - owner_response_rate: float (0-1)
    """
    if not reviews:
        return {
            "total_analyzed": 0,
            "ops_complaint_count": 0,
            "ops_complaint_samples": [],
            "owner_response_rate": 0.0,
        }

    ops_complaints = []
    owner_responses = 0

    for review in reviews:
        text = review.get("review_text", review.get("text", "")).lower()
        rating = review.get("review_rating", review.get("rating", 5))
        has_owner_reply = bool(
            review.get("owner_answer", review.get("response", ""))
        )

        if has_owner_reply:
            owner_responses += 1

        # Only check negative/neutral reviews for complaints
        if rating <= 3 and text:
            for keyword in complaint_keywords:
                if keyword.lower() in text:
                    # Grab a snippet around the keyword for context
                    idx = text.find(keyword.lower())
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(keyword) + 50)
                    snippet = text[start:end].strip()
                    ops_complaints.append(snippet)
                    break  # One match per review is enough

    return {
        "total_analyzed": len(reviews),
        "ops_complaint_count": len(ops_complaints),
        "ops_complaint_samples": ops_complaints[:5],
        "owner_response_rate": (
            owner_responses / len(reviews) if reviews else 0.0
        ),
    }


def enrich_lead_with_reviews(
    lead: Lead,
    review_analysis: dict,
) -> Lead:
    """Apply review analysis results to a Lead."""
    lead.reviews_analyzed = review_analysis["total_analyzed"]
    lead.ops_complaint_count = review_analysis["ops_complaint_count"]
    lead.ops_complaint_samples = review_analysis["ops_complaint_samples"]
    lead.owner_response_rate = review_analysis["owner_response_rate"]
    return lead
