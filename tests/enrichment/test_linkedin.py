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


from src.enrichment.linkedin import analyze_employee_titles


class TestAnalyzeEmployeeTitles:
    def test_counts_manual_roles(self):
        titles = ["Owner", "Data Entry Clerk", "Receptionist", "Sales Manager"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry", "receptionist"],
            tech_keywords=["it manager", "developer"],
        )
        assert result["manual_role_count"] == 2
        assert result["tech_role_count"] == 0

    def test_counts_tech_roles(self):
        titles = ["Owner", "IT Manager", "Software Developer", "CRM Administrator"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry", "receptionist"],
            tech_keywords=["it manager", "developer", "crm"],
        )
        assert result["manual_role_count"] == 0
        assert result["tech_role_count"] == 3

    def test_mixed_roles(self):
        titles = ["Data Entry Clerk", "IT Manager", "Office Manager"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 1
        assert result["tech_role_count"] == 1

    def test_no_matching_titles(self):
        titles = ["Owner", "Sales Manager", "Accountant"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 0
        assert result["tech_role_count"] == 0

    def test_empty_titles(self):
        result = analyze_employee_titles(
            [],
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 0
        assert result["tech_role_count"] == 0

    def test_case_insensitive(self):
        titles = ["DATA ENTRY SPECIALIST", "IT MANAGER"]
        result = analyze_employee_titles(
            titles,
            manual_keywords=["data entry"],
            tech_keywords=["it manager"],
        )
        assert result["manual_role_count"] == 1
        assert result["tech_role_count"] == 1
