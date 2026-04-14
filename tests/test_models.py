"""Tests for Pydantic data models."""

from pydantic import ValidationError
import pytest

from src.models import Lead, LeadSource, PipelineConfig, VerticalConfig


class TestLead:
    def test_minimal_lead(self):
        lead = Lead(business_name="Test Biz")
        assert lead.business_name == "Test Biz"
        assert lead.id == ""
        assert lead.source == LeadSource.GOOGLE_MAPS

    def test_full_lead(self):
        lead = Lead(
            id="abc123",
            business_name="Full Biz",
            address="456 Oak Ave",
            phone="555-1234",
            website="https://fullbiz.com",
            category="HVAC",
            metro="portland-or",
            source=LeadSource.LINKEDIN,
            rating=4.5,
            review_count=100,
            tech_stack=["wordpress", "react"],
            has_crm=True,
            has_chat_widget=False,
            has_scheduling=True,
            score=72.5,
            score_breakdown={"no_crm_detected": 0.0, "website_outdated": 0.5},
        )
        assert lead.id == "abc123"
        assert lead.rating == 4.5
        assert lead.tech_stack == ["wordpress", "react"]
        assert lead.has_crm is True
        assert lead.score == 72.5

    def test_default_values(self):
        lead = Lead(business_name="Defaults")
        assert lead.tech_stack == []
        assert lead.score is None
        assert lead.score_breakdown == {}
        assert lead.has_crm is None
        assert lead.has_ssl is None
        assert lead.reviews_analyzed == 0
        assert lead.ops_complaint_samples == []
        assert lead.followups == []
        assert lead.scraped_at is None

    def test_invalid_source_raises(self):
        with pytest.raises(ValidationError):
            Lead(business_name="Bad", source="invalid_source")

    def test_lead_source_enum_values(self):
        assert LeadSource.GOOGLE_MAPS.value == "google_maps"
        assert LeadSource.LINKEDIN.value == "linkedin"
        assert LeadSource.DIRECTORY.value == "directory"
        assert LeadSource.MANUAL.value == "manual"


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig()
        assert config.batch_size == 100
        assert config.score_threshold == 55.0
        assert config.daily_send_limit == 50

    def test_custom_values(self):
        config = PipelineConfig(batch_size=50, score_threshold=70, daily_send_limit=25)
        assert config.batch_size == 50
        assert config.score_threshold == 70


class TestVerticalConfig:
    def test_minimal(self):
        config = VerticalConfig(name="hvac")
        assert config.name == "hvac"
        assert config.weights == {}
        assert config.extra_manual_keywords == []

    def test_full(self):
        config = VerticalConfig(
            name="dental",
            weights={"no_scheduling_tool": 25},
            extra_manual_keywords=["front desk"],
            extra_complaint_keywords=["long wait"],
        )
        assert config.weights["no_scheduling_tool"] == 25
        assert "front desk" in config.extra_manual_keywords
