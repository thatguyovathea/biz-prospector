"""Tests for LinkedIn employee title analysis."""

from tests.conftest import make_lead


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
