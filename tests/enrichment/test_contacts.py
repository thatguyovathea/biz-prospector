"""Tests for contact enrichment (Apollo/Hunter waterfall)."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.enrichment.contacts import (
    search_apollo,
    search_hunter,
    verify_email_hunter,
    _title_priority,
    _pick_best_contact,
    enrich_lead_contacts,
)
from tests.conftest import make_lead


class TestTitlePriority:
    def test_owner_is_highest(self):
        assert _title_priority("Owner") < _title_priority("Office Manager")

    def test_founder_is_high(self):
        assert _title_priority("Co-Founder") < _title_priority("Administrator")

    def test_unknown_title_is_lowest(self):
        assert _title_priority("Janitor") == 999

    def test_case_insensitive(self):
        assert _title_priority("CEO") == _title_priority("ceo")


class TestPickBestContact:
    def test_prefers_higher_title(self):
        people = [
            {"name": "Jane", "email": "jane@co.com", "title": "Office Manager"},
            {"name": "Bob", "email": "bob@co.com", "title": "Owner"},
        ]
        best = _pick_best_contact(people)
        assert best["name"] == "Bob"

    def test_prefers_email_over_no_email(self):
        people = [
            {"name": "Alice", "email": "", "title": "Owner"},
            {"name": "Bob", "email": "bob@co.com", "title": "General Manager"},
        ]
        best = _pick_best_contact(people)
        assert best["name"] == "Bob"

    def test_returns_none_for_empty(self):
        assert _pick_best_contact([]) is None

    def test_falls_back_to_name_only(self):
        people = [
            {"name": "Alice", "email": "", "title": "Owner"},
        ]
        best = _pick_best_contact(people)
        assert best["name"] == "Alice"


class TestSearchApollo:
    @respx.mock
    def test_returns_contacts(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [
                    {
                        "first_name": "John",
                        "last_name": "Smith",
                        "email": "john@acme.com",
                        "title": "Owner",
                        "linkedin_url": "https://linkedin.com/in/jsmith",
                        "phone_number": "555-1234",
                    }
                ]
            })
        )
        results = search_apollo("Acme HVAC", "acmehvac.com", "fake-key")
        assert len(results) == 1
        assert results[0]["name"] == "John Smith"
        assert results[0]["email"] == "john@acme.com"
        assert results[0]["title"] == "Owner"

    @respx.mock
    def test_empty_results(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        results = search_apollo("Nobody Inc", "nobody.com", "fake-key")
        assert results == []


class TestSearchHunter:
    @respx.mock
    def test_returns_contacts(self):
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "emails": [
                        {
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "value": "jane@example.com",
                            "position": "CEO",
                            "linkedin": "https://linkedin.com/in/jdoe",
                        }
                    ]
                }
            })
        )
        results = search_hunter("example.com", "fake-key")
        assert len(results) == 1
        assert results[0]["name"] == "Jane Doe"
        assert results[0]["email"] == "jane@example.com"

    def test_empty_domain_returns_empty(self):
        results = search_hunter("", "fake-key")
        assert results == []


class TestVerifyEmailHunter:
    @respx.mock
    def test_returns_verification(self):
        respx.get("https://api.hunter.io/v2/email-verifier").mock(
            return_value=httpx.Response(200, json={
                "data": {"status": "valid", "score": 95}
            })
        )
        result = verify_email_hunter("test@example.com", "fake-key")
        assert result["status"] == "valid"
        assert result["score"] == 95


class TestEnrichLeadContacts:
    @respx.mock
    def test_apollo_success(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Bob",
                    "last_name": "Owner",
                    "email": "bob@acme.com",
                    "title": "Owner",
                    "linkedin_url": "",
                    "phone_number": "",
                }]
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake-key")
        assert lead.contact_name == "Bob Owner"
        assert lead.contact_email == "bob@acme.com"
        assert lead.contact_title == "Owner"

    @respx.mock
    def test_waterfall_to_hunter(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            side_effect=httpx.HTTPStatusError(
                "error",
                request=httpx.Request("POST", "https://api.apollo.io/v1/mixed_people/search"),
                response=httpx.Response(500),
            )
        )
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "emails": [{
                        "first_name": "Jane",
                        "last_name": "Fallback",
                        "value": "jane@acme.com",
                        "position": "Manager",
                    }]
                }
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake-key", hunter_key="fake-key")
        assert lead.contact_name == "Jane Fallback"
        assert lead.contact_email == "jane@acme.com"

    def test_no_keys_no_enrichment(self):
        lead = make_lead()
        enrich_lead_contacts(lead)
        assert lead.contact_name == ""
        assert lead.contact_email == ""
