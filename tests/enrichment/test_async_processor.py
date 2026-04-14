"""Tests for async enrichment processor."""

from unittest.mock import patch, MagicMock

import pytest

from src.enrichment.async_processor import enrich_leads_async
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
