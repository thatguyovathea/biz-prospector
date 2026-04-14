"""Tests for outreach email generation via Claude API."""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.outreach.generate import _build_lead_context, generate_outreach
from tests.conftest import make_lead


class TestBuildLeadContext:
    def test_includes_basic_info(self):
        lead = make_lead()
        context = _build_lead_context(lead)
        assert "Acme HVAC Services" in context
        assert "HVAC" in context
        assert "123 Main St" in context
        assert "acmehvac.com" in context

    def test_includes_contact(self):
        lead = make_lead(contact_name="Bob Smith", contact_title="Owner")
        context = _build_lead_context(lead)
        assert "Bob Smith" in context
        assert "Owner" in context

    def test_includes_missing_tools(self):
        lead = make_lead(has_crm=False, has_chat_widget=False, has_scheduling=False)
        context = _build_lead_context(lead)
        assert "No CRM" in context
        assert "No chat widget" in context
        assert "No online scheduling" in context

    def test_omits_none_fields(self):
        lead = make_lead(has_crm=None, has_scheduling=None)
        context = _build_lead_context(lead)
        assert "No CRM" not in context
        assert "No online scheduling" not in context

    def test_includes_review_complaints(self):
        lead = make_lead(
            ops_complaint_count=5,
            reviews_analyzed=50,
            ops_complaint_samples=["never called back", "lost paperwork"],
        )
        context = _build_lead_context(lead)
        assert "5 complaints" in context
        assert "50 reviews" in context

    def test_includes_job_signals(self):
        lead = make_lead(
            manual_process_postings=2,
            manual_process_titles=["Receptionist", "Data Entry Clerk"],
        )
        context = _build_lead_context(lead)
        assert "2 roles" in context
        assert "Receptionist" in context

    def test_includes_score(self):
        lead = make_lead(
            score=72.5,
            score_breakdown={"no_crm_detected": 1.0, "website_outdated": 0.5, "manual_job_postings": 0.3},
        )
        context = _build_lead_context(lead)
        assert "72.5/100" in context
        assert "no_crm_detected" in context

    def test_includes_low_owner_response_rate(self):
        lead = make_lead(owner_response_rate=0.1)
        context = _build_lead_context(lead)
        assert "10%" in context

    def test_normal_owner_response_rate_omitted(self):
        lead = make_lead(owner_response_rate=0.5)
        context = _build_lead_context(lead)
        assert "responds to only" not in context


class TestGenerateOutreach:
    def test_sets_outreach_fields(self, sample_settings):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "subject": "Quick question about your HVAC scheduling",
            "body": "Hi Bob, your customers mention difficulty booking appointments...",
            "followups": ["Following up on my email...", "Last note..."],
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        lead = make_lead(contact_name="Bob", score=72.5)

        with patch("src.outreach.generate.load_settings", return_value=sample_settings), \
             patch("src.outreach.generate.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            generate_outreach(lead)

        assert "Quick question" in lead.outreach_email
        assert len(lead.followups) == 2
        assert lead.contacted_at is not None

    def test_handles_markdown_wrapped_json(self, sample_settings):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '```json\n{"subject": "Test", "body": "Hello", "followups": []}\n```'

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        lead = make_lead()

        with patch("src.outreach.generate.load_settings", return_value=sample_settings), \
             patch("src.outreach.generate.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            generate_outreach(lead)

        assert "Test" in lead.outreach_email

    def test_handles_api_error_gracefully(self, sample_settings):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        lead = make_lead()

        with patch("src.outreach.generate.load_settings", return_value=sample_settings), \
             patch("src.outreach.generate.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result = generate_outreach(lead)

        assert result.outreach_email == ""
        assert result.contacted_at is None
