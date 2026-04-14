"""Tests for job posting scraper and analyzer."""

import httpx
import pytest
import respx

from src.scrapers.job_posts import (
    analyze_job_postings,
    enrich_lead_with_jobs,
    search_jobs_serpapi,
)
from tests.conftest import make_lead


class TestAnalyzeJobPostings:
    def test_detects_keyword_in_title(self):
        postings = [{"title": "Data Entry Clerk", "description": "Fast-paced office environment"}]
        result = analyze_job_postings(postings, ["data entry"])
        assert result["manual_process_count"] == 1
        assert result["manual_process_titles"] == ["Data Entry Clerk"]

    def test_detects_keyword_in_description(self):
        postings = [{"title": "Office Associate", "description": "Maintain spreadsheet records and filing"}]
        result = analyze_job_postings(postings, ["spreadsheet", "filing"])
        assert result["manual_process_count"] == 1

    def test_counts_total_postings(self):
        postings = [
            {"title": "Developer", "description": "Build software"},
            {"title": "Designer", "description": "Design UI"},
            {"title": "Data Entry", "description": "Enter data"},
        ]
        result = analyze_job_postings(postings, ["data entry"])
        assert result["total_postings"] == 3
        assert result["manual_process_count"] == 1

    def test_no_matches(self):
        postings = [{"title": "Software Engineer", "description": "Write Python code"}]
        result = analyze_job_postings(postings, ["data entry", "filing"])
        assert result["manual_process_count"] == 0
        assert result["manual_process_titles"] == []

    def test_empty_postings(self):
        result = analyze_job_postings([], ["data entry"])
        assert result["total_postings"] == 0
        assert result["manual_process_count"] == 0

    def test_one_match_per_posting(self):
        postings = [{"title": "Admin Filing Clerk", "description": "Data entry and spreadsheet work"}]
        result = analyze_job_postings(postings, ["filing", "data entry", "spreadsheet"])
        assert result["manual_process_count"] == 1


class TestSearchJobsSerpapi:
    @respx.mock
    def test_fetches_jobs(self):
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={
                "jobs_results": [
                    {"title": "HVAC Technician", "description": "Install and repair"},
                    {"title": "Receptionist", "description": "Answer phones"},
                ]
            })
        )
        results = search_jobs_serpapi("Acme HVAC", "Portland, OR", "fake-key")
        assert len(results) == 2
        assert results[0]["title"] == "HVAC Technician"

    @respx.mock
    def test_empty_results(self):
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={})
        )
        results = search_jobs_serpapi("Nobody Inc", "Nowhere", "fake-key")
        assert results == []


class TestEnrichLeadWithJobs:
    def test_applies_analysis_to_lead(self):
        lead = make_lead()
        analysis = {
            "total_postings": 5,
            "manual_process_count": 2,
            "manual_process_titles": ["Receptionist", "Filing Clerk"],
        }
        enrich_lead_with_jobs(lead, analysis)
        assert lead.active_job_postings == 5
        assert lead.manual_process_postings == 2
        assert lead.manual_process_titles == ["Receptionist", "Filing Clerk"]
