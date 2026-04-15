"""Tests for LinkedIn employee title analysis."""

import httpx
import respx

from tests.conftest import make_lead
from src.enrichment.linkedin import fetch_company_employees


class TestLeadLinkedInFields:
    def test_default_values(self):
        lead = make_lead()
        assert lead.linkedin_url == ""
        assert lead.company_linkedin_url == ""
        assert lead.employee_count is None
        assert lead.founded_year is None
        assert lead.employee_titles == []
        assert lead.manual_role_count == 0
        assert lead.tech_role_count == 0


class TestFetchCompanyEmployees:
    @respx.mock
    def test_returns_titles_and_metadata(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [
                    {
                        "title": "Owner",
                        "linkedin_url": "https://linkedin.com/in/owner",
                        "organization": {
                            "estimated_num_employees": 45,
                            "founded_year": 2008,
                            "linkedin_url": "https://linkedin.com/company/acme",
                        },
                    },
                    {
                        "title": "Data Entry Clerk",
                        "linkedin_url": "",
                        "organization": {
                            "estimated_num_employees": 45,
                            "founded_year": 2008,
                            "linkedin_url": "https://linkedin.com/company/acme",
                        },
                    },
                    {
                        "title": "Office Manager",
                        "linkedin_url": "",
                        "organization": {},
                    },
                ],
            })
        )
        result = fetch_company_employees("acmehvac.com", "fake-key")
        assert result["titles"] == ["Owner", "Data Entry Clerk", "Office Manager"]
        assert result["employee_count"] == 45
        assert result["founded_year"] == 2008
        assert result["company_linkedin_url"] == "https://linkedin.com/company/acme"

    @respx.mock
    def test_empty_response(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        result = fetch_company_employees("nobody.com", "fake-key")
        assert result["titles"] == []
        assert result["employee_count"] is None
        assert result["founded_year"] is None
        assert result["company_linkedin_url"] == ""

    @respx.mock
    def test_http_error_returns_empty(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(500)
        )
        result = fetch_company_employees("error.com", "fake-key")
        assert result["titles"] == []
        assert result["employee_count"] is None

    @respx.mock
    def test_timeout_returns_empty(self):
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        result = fetch_company_employees("slow.com", "fake-key")
        assert result["titles"] == []
