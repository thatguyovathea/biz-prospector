"""Data models shared across all pipeline stages."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LeadSource(str, Enum):
    GOOGLE_MAPS = "google_maps"
    LINKEDIN = "linkedin"
    DIRECTORY = "directory"
    MANUAL = "manual"


class Lead(BaseModel):
    """Core lead record that flows through the entire pipeline."""

    id: str = ""
    business_name: str
    address: str = ""
    phone: str = ""
    website: str = ""
    category: str = ""
    metro: str = ""
    source: LeadSource = LeadSource.GOOGLE_MAPS

    # Google Maps data
    rating: Optional[float] = None
    review_count: Optional[int] = None
    place_id: str = ""

    # Enrichment data (populated in enrichment stage)
    tech_stack: list[str] = Field(default_factory=list)
    has_crm: Optional[bool] = None
    has_chat_widget: Optional[bool] = None
    has_scheduling: Optional[bool] = None
    has_ssl: Optional[bool] = None
    is_mobile_responsive: Optional[bool] = None
    page_speed_score: Optional[int] = None

    # Review analysis
    reviews_analyzed: int = 0
    ops_complaint_count: int = 0
    ops_complaint_samples: list[str] = Field(default_factory=list)
    owner_response_rate: Optional[float] = None

    # Job posting signals
    active_job_postings: int = 0
    manual_process_postings: int = 0
    manual_process_titles: list[str] = Field(default_factory=list)

    # Contact info (populated in enrichment)
    contact_name: str = ""
    contact_email: str = ""
    contact_title: str = ""

    # Scoring (populated in scoring stage)
    score: Optional[float] = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)

    # Outreach (populated in outreach stage)
    outreach_email: str = ""
    followups: list[str] = Field(default_factory=list)

    # Metadata
    scraped_at: Optional[datetime] = None
    enriched_at: Optional[datetime] = None
    scored_at: Optional[datetime] = None
    contacted_at: Optional[datetime] = None


class PipelineConfig(BaseModel):
    """Runtime config loaded from settings.yaml."""

    batch_size: int = 100
    score_threshold: float = 55.0
    daily_send_limit: int = 50


class VerticalConfig(BaseModel):
    """Per-vertical scoring weight overrides."""

    name: str
    weights: dict[str, float] = Field(default_factory=dict)
    extra_manual_keywords: list[str] = Field(default_factory=list)
    extra_complaint_keywords: list[str] = Field(default_factory=list)
