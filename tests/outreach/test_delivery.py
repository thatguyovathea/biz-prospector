"""Tests for Instantly.ai delivery integration."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.outreach.delivery import (
    InstantlyClient,
    _parse_outreach_email,
    _lead_to_instantly_format,
    push_to_instantly,
)
from tests.conftest import make_lead


class TestParseOutreachEmail:
    def test_extracts_subject_and_body(self):
        email = "Subject: Quick question\n\nHi Bob, I wanted to reach out..."
        subject, body = _parse_outreach_email(make_lead(outreach_email=email))
        assert subject == "Quick question"
        assert body == "Hi Bob, I wanted to reach out..."

    def test_no_subject_line(self):
        lead = make_lead(outreach_email="Just a plain email body")
        subject, body = _parse_outreach_email(lead)
        assert subject == ""
        assert "plain email body" in body

    def test_empty_outreach(self):
        subject, body = _parse_outreach_email(make_lead(outreach_email=""))
        assert subject == ""
        assert body == ""


class TestLeadToInstantlyFormat:
    def test_formats_correctly(self):
        lead = make_lead(
            contact_name="Bob Smith",
            contact_email="bob@acme.com",
            contact_title="Owner",
            score=72.5,
        )
        result = _lead_to_instantly_format(lead)
        assert result["email"] == "bob@acme.com"
        assert result["first_name"] == "Bob"
        assert result["last_name"] == "Smith"
        assert result["company_name"] == "Acme HVAC Services"
        assert result["custom_variables"]["contact_title"] == "Owner"
        assert result["custom_variables"]["score"] == "72.5"

    def test_single_name(self):
        lead = make_lead(contact_name="Bob", contact_email="bob@co.com")
        result = _lead_to_instantly_format(lead)
        assert result["first_name"] == "Bob"
        assert result["last_name"] == ""

    def test_no_contact_name(self):
        lead = make_lead(contact_name="", contact_email="info@co.com")
        result = _lead_to_instantly_format(lead)
        assert result["first_name"] == ""
        assert result["last_name"] == ""


class TestInstantlyClient:
    @respx.mock
    def test_create_campaign(self):
        respx.post("https://api.instantly.ai/api/v1/campaign/create").mock(
            return_value=httpx.Response(200, json={"id": "camp_123", "name": "Test"})
        )
        client = InstantlyClient("fake-key")
        result = client.create_campaign("Test Campaign")
        assert result["id"] == "camp_123"

    @respx.mock
    def test_add_leads(self):
        respx.post("https://api.instantly.ai/api/v1/lead/add").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client = InstantlyClient("fake-key")
        result = client.add_leads_to_campaign("camp_123", [{"email": "test@co.com"}])
        assert result["status"] == "ok"

    @respx.mock
    def test_set_sequences(self):
        respx.post("https://api.instantly.ai/api/v1/campaign/set-sequences").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client = InstantlyClient("fake-key")
        steps = [{"subject": "Hi", "body": "Hello", "delay": 0}]
        result = client.set_campaign_sequences("camp_123", steps)
        assert result["status"] == "ok"

    @respx.mock
    def test_launch_campaign(self):
        respx.post("https://api.instantly.ai/api/v1/campaign/launch").mock(
            return_value=httpx.Response(200, json={"status": "launched"})
        )
        client = InstantlyClient("fake-key")
        result = client.launch_campaign("camp_123")
        assert result["status"] == "launched"


class TestPushToInstantly:
    @respx.mock
    def test_full_push(self, sample_settings):
        respx.post("https://api.instantly.ai/api/v1/campaign/create").mock(
            return_value=httpx.Response(200, json={"id": "camp_123"})
        )
        respx.post("https://api.instantly.ai/api/v1/campaign/set-sequences").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.post("https://api.instantly.ai/api/v1/lead/add").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        leads = [
            make_lead(
                contact_email="bob@acme.com",
                outreach_email="Subject: Hi\n\nHello Bob",
                followups=["Follow up 1"],
            ),
        ]

        with patch("src.outreach.delivery.load_settings", return_value=sample_settings):
            result = push_to_instantly(leads, "Test Campaign")

        assert result["campaign_id"] == "camp_123"
        assert result["leads_added"] == 1
        assert result["status"] == "ready"

    @respx.mock
    def test_auto_launch(self, sample_settings):
        respx.post("https://api.instantly.ai/api/v1/campaign/create").mock(
            return_value=httpx.Response(200, json={"id": "camp_123"})
        )
        respx.post("https://api.instantly.ai/api/v1/campaign/set-sequences").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.post("https://api.instantly.ai/api/v1/lead/add").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.post("https://api.instantly.ai/api/v1/campaign/launch").mock(
            return_value=httpx.Response(200, json={"status": "launched"})
        )

        leads = [
            make_lead(
                contact_email="bob@acme.com",
                outreach_email="Subject: Hi\n\nHello",
                followups=[],
            ),
        ]

        with patch("src.outreach.delivery.load_settings", return_value=sample_settings):
            result = push_to_instantly(leads, "Test", auto_launch=True)

        assert result["status"] == "launched"

    def test_filters_unsendable(self, sample_settings):
        leads = [
            make_lead(contact_email="", outreach_email="Subject: Hi\n\nHello"),
            make_lead(contact_email="bob@acme.com", outreach_email=""),
            make_lead(contact_email="", outreach_email=""),
        ]

        with patch("src.outreach.delivery.load_settings", return_value=sample_settings):
            result = push_to_instantly(leads, "Empty Campaign")

        assert result["leads_added"] == 0
        assert result["status"] == "empty"
