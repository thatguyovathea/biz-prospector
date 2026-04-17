"""Tests for Google Maps scraper."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.scrapers.google_maps import (
    parse_serpapi_result,
    parse_apify_result,
    scrape_serpapi,
    scrape_apify,
    scrape_google_maps,
    _make_id,
)
from src.models import Lead, LeadSource


class TestMakeId:
    def test_deterministic(self):
        id1 = _make_id("Acme HVAC", "123 Main St")
        id2 = _make_id("Acme HVAC", "123 Main St")
        assert id1 == id2

    def test_case_insensitive(self):
        id1 = _make_id("Acme HVAC", "123 Main St")
        id2 = _make_id("acme hvac", "123 main st")
        assert id1 == id2

    def test_different_inputs_differ(self):
        id1 = _make_id("Acme HVAC", "123 Main St")
        id2 = _make_id("Beta Plumbing", "456 Oak Ave")
        assert id1 != id2

    def test_twelve_chars(self):
        assert len(_make_id("Test", "Addr")) == 12


class TestParseSerpApiResult:
    def test_parses_full_result(self):
        item = {
            "title": "Portland HVAC Co",
            "address": "100 NW Broadway, Portland, OR",
            "phone": "(503) 555-1234",
            "website": "https://portlandhvac.com",
            "type": "HVAC contractor",
            "rating": 4.5,
            "reviews": 120,
            "place_id": "ChIJ_test123",
        }
        lead = parse_serpapi_result(item, "portland-or")
        assert lead.business_name == "Portland HVAC Co"
        assert lead.address == "100 NW Broadway, Portland, OR"
        assert lead.phone == "(503) 555-1234"
        assert lead.website == "https://portlandhvac.com"
        assert lead.category == "HVAC contractor"
        assert lead.metro == "portland-or"
        assert lead.source == LeadSource.GOOGLE_MAPS
        assert lead.rating == 4.5
        assert lead.review_count == 120
        assert lead.place_id == "ChIJ_test123"
        assert lead.id

    def test_handles_missing_fields(self):
        item = {"title": "Bare Minimum Biz"}
        lead = parse_serpapi_result(item, "test-metro")
        assert lead.business_name == "Bare Minimum Biz"
        assert lead.phone == ""
        assert lead.website == ""
        assert lead.rating is None


class TestParseApifyResult:
    def test_parses_full_result(self):
        item = {
            "title": "Seattle Dental",
            "address": "200 Pike St, Seattle, WA",
            "phone": "(206) 555-9876",
            "website": "https://seattledental.com",
            "categoryName": "Dentist",
            "totalScore": 4.8,
            "reviewsCount": 200,
            "placeId": "ChIJ_apify456",
        }
        lead = parse_apify_result(item, "seattle-wa")
        assert lead.business_name == "Seattle Dental"
        assert lead.rating == 4.8
        assert lead.review_count == 200
        assert lead.place_id == "ChIJ_apify456"

    def test_falls_back_to_url_for_website(self):
        item = {"title": "Test", "url": "https://fallback.com"}
        lead = parse_apify_result(item, "test")
        assert lead.website == "https://fallback.com"


class TestScrapeSerpapi:
    @respx.mock
    def test_fetches_results(self):
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={
                "local_results": [
                    {"title": f"Business {i}", "address": f"{i} Main St"}
                    for i in range(3)
                ]
            })
        )
        results = scrape_serpapi("hvac", "portland", "fake-key", num_results=3)
        assert len(results) == 3
        assert results[0]["title"] == "Business 0"

    @respx.mock
    def test_stops_on_empty_page(self):
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={
                    "local_results": [{"title": "Biz 1", "address": "Addr 1"}]
                })
            return httpx.Response(200, json={"local_results": []})

        respx.get("https://serpapi.com/search").mock(side_effect=side_effect)
        results = scrape_serpapi("hvac", "portland", "fake-key", num_results=100)
        assert len(results) == 1


class TestScrapeGoogleMaps:
    @respx.mock
    def test_deduplicates_results(self, sample_settings):
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={
                "local_results": [
                    {"title": "Same Biz", "address": "Same Addr"},
                    {"title": "Same Biz", "address": "Same Addr"},
                    {"title": "Different Biz", "address": "Other Addr"},
                ]
            })
        )
        with patch("src.scrapers.google_maps.load_settings", return_value=sample_settings):
            leads = scrape_google_maps("hvac", "portland-or", num_results=10, provider="serpapi")
        assert len(leads) == 2

    def test_invalid_provider_raises(self, sample_settings):
        with patch("src.scrapers.google_maps.load_settings", return_value=sample_settings):
            with pytest.raises(ValueError, match="Unknown provider"):
                scrape_google_maps("hvac", "portland-or", provider="unknown")

    @respx.mock
    def test_apify_provider(self, sample_settings):
        """Test scrape_google_maps dispatches to Apify when provider=apify."""
        # Mock the Apify actor run start
        respx.post("https://api.apify.com/v2/acts/nwua9Gu5YrADL7ZDj/runs").mock(
            return_value=httpx.Response(200, json={
                "data": {"id": "run_123", "defaultDatasetId": "ds_456"}
            })
        )
        # Mock the status check — immediately SUCCEEDED
        respx.get("https://api.apify.com/v2/actor-runs/run_123").mock(
            return_value=httpx.Response(200, json={
                "data": {"status": "SUCCEEDED"}
            })
        )
        # Mock the dataset items
        respx.get("https://api.apify.com/v2/datasets/ds_456/items").mock(
            return_value=httpx.Response(200, json=[
                {"title": "Apify Biz", "address": "789 Apify St"},
            ])
        )
        with patch("src.scrapers.google_maps.load_settings", return_value=sample_settings):
            leads = scrape_google_maps("hvac", "portland-or", num_results=5, provider="apify")
        assert len(leads) == 1
        assert leads[0].business_name == "Apify Biz"


class TestScrapeApify:
    @respx.mock
    def test_full_apify_run(self):
        respx.post("https://api.apify.com/v2/acts/nwua9Gu5YrADL7ZDj/runs").mock(
            return_value=httpx.Response(200, json={
                "data": {"id": "run_abc", "defaultDatasetId": "ds_xyz"}
            })
        )
        respx.get("https://api.apify.com/v2/actor-runs/run_abc").mock(
            return_value=httpx.Response(200, json={
                "data": {"status": "SUCCEEDED"}
            })
        )
        respx.get("https://api.apify.com/v2/datasets/ds_xyz/items").mock(
            return_value=httpx.Response(200, json=[
                {"title": "Biz A", "address": "1 Main St"},
                {"title": "Biz B", "address": "2 Oak Ave"},
            ])
        )
        results = scrape_apify("hvac portland", "portland", "fake-token", num_results=10)
        assert len(results) == 2
        assert results[0]["title"] == "Biz A"

    @respx.mock
    def test_apify_run_failed(self):
        respx.post("https://api.apify.com/v2/acts/nwua9Gu5YrADL7ZDj/runs").mock(
            return_value=httpx.Response(200, json={
                "data": {"id": "run_fail", "defaultDatasetId": "ds_fail"}
            })
        )
        respx.get("https://api.apify.com/v2/actor-runs/run_fail").mock(
            return_value=httpx.Response(200, json={
                "data": {"status": "FAILED"}
            })
        )
        with pytest.raises(RuntimeError, match="FAILED"):
            scrape_apify("hvac", "portland", "fake-token")


class TestScrapeApifyPolling:
    @respx.mock
    def test_polls_until_succeeded(self):
        """Test that scrape_apify polls status and waits via time.sleep."""
        respx.post("https://api.apify.com/v2/acts/nwua9Gu5YrADL7ZDj/runs").mock(
            return_value=httpx.Response(200, json={
                "data": {"id": "run_poll", "defaultDatasetId": "ds_poll"}
            })
        )
        call_count = 0

        def status_side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(200, json={"data": {"status": "RUNNING"}})
            return httpx.Response(200, json={"data": {"status": "SUCCEEDED"}})

        respx.get("https://api.apify.com/v2/actor-runs/run_poll").mock(
            side_effect=status_side_effect
        )
        respx.get("https://api.apify.com/v2/datasets/ds_poll/items").mock(
            return_value=httpx.Response(200, json=[
                {"title": "Polled Biz", "address": "1 Poll St"},
            ])
        )
        with patch("time.sleep"):
            results = scrape_apify("hvac portland", "portland", "fake-token", num_results=5)
        assert len(results) == 1
        assert call_count == 3


