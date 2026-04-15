"""Tests for async enrichment processor."""

from unittest.mock import patch, MagicMock

import pytest

from src.enrichment.async_processor import enrich_leads_async, run_async_enrichment
from tests.conftest import make_lead


@pytest.fixture
def mock_settings(sample_settings):
    with patch("src.enrichment.async_processor.load_settings", return_value=sample_settings):
        yield sample_settings


class TestEnrichLeadsAsync:
    @pytest.mark.asyncio
    async def test_enriches_all_leads(self, mock_settings):
        leads = [make_lead(id="l1", website=""), make_lead(id="l2", website="")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 2
        for lead in results:
            assert lead.enriched_at is not None

    @pytest.mark.asyncio
    async def test_preserves_order(self, mock_settings):
        leads = [make_lead(id=f"l{i}", website="") for i in range(5)]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        result_ids = [l.id for l in results]
        assert result_ids == ["l0", "l1", "l2", "l3", "l4"]

    @pytest.mark.asyncio
    async def test_failure_doesnt_block_others(self, mock_settings):
        leads = [make_lead(id="good", website=""), make_lead(id="also_good", website="")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_calls_audit_with_builtwith_key(self, mock_settings):
        """Verify enrichment runs when lead has a website (BuiltWith key from settings)."""
        leads = [make_lead(id="l1", website="https://example.com")]
        mock_audit = MagicMock()

        with patch("src.enrichment.async_processor.audit_website", mock_audit), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"), \
             patch("src.enrichment.async_processor.fetch_company_employees", return_value={"titles": [], "employee_count": None, "founded_year": None, "company_linkedin_url": ""}):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 1
        assert results[0].enriched_at is not None

    @pytest.mark.asyncio
    async def test_skips_website_audit_for_no_website(self, mock_settings):
        """Leads without a website should skip website audit entirely."""
        leads = [make_lead(id="noweb", website="")]
        mock_audit = MagicMock()

        with patch("src.enrichment.async_processor.audit_website", mock_audit), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit") as mock_enrich, \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        mock_audit.assert_not_called()
        mock_enrich.assert_not_called()

    @pytest.mark.asyncio
    async def test_review_exception_swallowed(self, mock_settings):
        """Exception in review fetch doesn't crash enrichment."""
        leads = [make_lead(id="rev_err", website="", place_id="place_123")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", side_effect=Exception("API down")), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 1
        assert results[0].enriched_at is not None

    @pytest.mark.asyncio
    async def test_job_search_exception_swallowed(self, mock_settings):
        """Exception in job search doesn't crash enrichment."""
        leads = [make_lead(id="job_err", website="")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", side_effect=Exception("SerpAPI down")), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 1
        assert results[0].enriched_at is not None

    @pytest.mark.asyncio
    async def test_contact_enrichment_exception_swallowed(self, mock_settings):
        """Exception in contact enrichment doesn't crash enrichment."""
        leads = [make_lead(id="contact_err", website="")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts", side_effect=Exception("Apollo down")):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 1
        assert results[0].enriched_at is not None

    def test_sync_wrapper(self, mock_settings):
        """Test the synchronous wrapper around async enrichment."""
        leads = [make_lead(id="sync", website="")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = run_async_enrichment(leads, max_concurrent=2)

        assert len(results) == 1
        assert results[0].enriched_at is not None


class TestLinkedInEnrichment:
    @pytest.mark.asyncio
    async def test_title_enrichment_runs(self, mock_settings):
        leads = [make_lead(id="li1", website="https://acme.com")]
        mock_fetch = MagicMock(return_value={
            "titles": ["Owner", "Data Entry Clerk"],
            "employee_count": 10,
            "founded_year": 2010,
            "company_linkedin_url": "",
        })

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"), \
             patch("src.enrichment.async_processor.fetch_company_employees", mock_fetch), \
             patch("src.enrichment.async_processor.enrich_lead_with_titles") as mock_enrich:
            results = await enrich_leads_async(leads, max_concurrent=2)

        mock_fetch.assert_called_once()
        mock_enrich.assert_called_once()

    @pytest.mark.asyncio
    async def test_title_enrichment_exception_swallowed(self, mock_settings):
        leads = [make_lead(id="li_err", website="https://error.com")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"), \
             patch("src.enrichment.async_processor.fetch_company_employees", side_effect=Exception("Apollo down")):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 1
        assert results[0].enriched_at is not None

    @pytest.mark.asyncio
    async def test_skips_title_enrichment_without_website(self, mock_settings):
        leads = [make_lead(id="noweb", website="")]
        mock_fetch = MagicMock()

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"), \
             patch("src.enrichment.async_processor.fetch_company_employees", mock_fetch):
            results = await enrich_leads_async(leads, max_concurrent=2)

        mock_fetch.assert_not_called()
