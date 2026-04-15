"""Tests for contact enrichment (Apollo/Hunter waterfall)."""

from unittest.mock import patch

import httpx
import respx

from src.enrichment.contacts import (
    search_apollo,
    search_hunter,
    verify_email_hunter,
    _title_priority,
    _pick_best_contact,
    _extract_domain,
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


class TestExtractDomain:
    def test_normal_url(self):
        assert _extract_domain("https://acmehvac.com/about") == "acmehvac.com"

    def test_empty_string(self):
        assert _extract_domain("") == ""

    def test_no_suffix(self):
        assert _extract_domain("http://localhost") == ""


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

    @respx.mock
    def test_apollo_returns_empty_falls_to_hunter(self):
        """Apollo succeeds but returns no people — should fall to Hunter."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "emails": [{
                        "first_name": "Hunter",
                        "last_name": "Result",
                        "value": "hunter@acme.com",
                        "position": "Owner",
                    }]
                }
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake", hunter_key="fake")
        assert lead.contact_name == "Hunter Result"
        assert lead.contact_email == "hunter@acme.com"

    @respx.mock
    def test_hunter_exception_doesnt_crash(self):
        """Hunter failing should not crash the enrichment."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake", hunter_key="fake")
        assert lead.contact_name == ""

    @respx.mock
    def test_email_verification_invalid_clears_email(self):
        """Invalid email verification should clear the contact_email."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Bob",
                    "last_name": "Test",
                    "email": "bob@invalid.com",
                    "title": "Owner",
                    "linkedin_url": "",
                    "phone_number": "",
                }]
            })
        )
        respx.get("https://api.hunter.io/v2/email-verifier").mock(
            return_value=httpx.Response(200, json={
                "data": {"status": "invalid", "score": 10}
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake", hunter_key="fake", verify=True)
        assert lead.contact_name == "Bob Test"
        assert lead.contact_email == ""

    @respx.mock
    def test_email_verification_valid_keeps_email(self):
        """Valid email verification should keep the contact_email."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Bob",
                    "last_name": "Test",
                    "email": "bob@valid.com",
                    "title": "Owner",
                    "linkedin_url": "",
                    "phone_number": "",
                }]
            })
        )
        respx.get("https://api.hunter.io/v2/email-verifier").mock(
            return_value=httpx.Response(200, json={
                "data": {"status": "valid", "score": 95}
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake", hunter_key="fake", verify=True)
        assert lead.contact_email == "bob@valid.com"

    @respx.mock
    def test_verification_exception_doesnt_crash(self):
        """Verification failure should not crash — email stays."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Bob",
                    "last_name": "Test",
                    "email": "bob@acme.com",
                    "title": "Owner",
                    "linkedin_url": "",
                    "phone_number": "",
                }]
            })
        )
        respx.get("https://api.hunter.io/v2/email-verifier").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake", hunter_key="fake", verify=True)
        assert lead.contact_email == "bob@acme.com"

    @respx.mock
    def test_apollo_with_company_name_no_domain(self):
        """When lead has no website, Apollo should use company name."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Alice",
                    "last_name": "Owner",
                    "email": "alice@acme.com",
                    "title": "Owner",
                    "linkedin_url": "",
                    "phone_number": "",
                }]
            })
        )
        lead = make_lead(website="")
        enrich_lead_contacts(lead, apollo_key="fake")
        assert lead.contact_name == "Alice Owner"


class TestLinkedInUrlCapture:
    @respx.mock
    def test_captures_linkedin_url_from_apollo(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Bob",
                    "last_name": "Owner",
                    "email": "bob@acme.com",
                    "title": "Owner",
                    "linkedin_url": "https://linkedin.com/in/bobowner",
                    "phone_number": "",
                }]
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake-key")
        assert lead.linkedin_url == "https://linkedin.com/in/bobowner"

    @respx.mock
    def test_captures_linkedin_url_from_hunter(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "emails": [{
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "value": "jane@acme.com",
                        "position": "CEO",
                        "linkedin": "https://linkedin.com/in/janedoe",
                    }]
                }
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake", hunter_key="fake")
        assert lead.linkedin_url == "https://linkedin.com/in/janedoe"
