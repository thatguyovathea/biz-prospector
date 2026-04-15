"""Tests for review scraper and analyzer."""

import httpx
import respx

from src.scrapers.reviews import (
    analyze_reviews,
    enrich_lead_with_reviews,
    fetch_reviews_outscraper,
)
from tests.conftest import make_lead


class TestAnalyzeReviews:
    def test_counts_ops_complaints(self):
        reviews = [
            {"review_text": "They never called back after I left a message", "review_rating": 2},
            {"review_text": "Great service, highly recommend!", "review_rating": 5},
            {"review_text": "Very disorganized office, lost my records", "review_rating": 1},
        ]
        keywords = ["never called back", "disorganized", "hard to reach"]
        result = analyze_reviews(reviews, keywords)
        assert result["total_analyzed"] == 3
        assert result["ops_complaint_count"] == 2
        assert len(result["ops_complaint_samples"]) == 2

    def test_ignores_positive_reviews(self):
        reviews = [
            {"review_text": "They never called back but great overall!", "review_rating": 5},
            {"review_text": "Never called back, terrible", "review_rating": 4},
        ]
        keywords = ["never called back"]
        result = analyze_reviews(reviews, keywords)
        assert result["ops_complaint_count"] == 0

    def test_owner_response_rate(self):
        reviews = [
            {"review_text": "Bad", "review_rating": 1, "owner_answer": "Sorry about that"},
            {"review_text": "Good", "review_rating": 5, "owner_answer": "Thanks!"},
            {"review_text": "OK", "review_rating": 3, "owner_answer": ""},
            {"review_text": "Meh", "review_rating": 3},
        ]
        result = analyze_reviews(reviews, [])
        assert result["owner_response_rate"] == 0.5

    def test_limits_samples_to_five(self):
        reviews = [
            {"review_text": f"They were disorganized, visit {i}", "review_rating": 1}
            for i in range(10)
        ]
        keywords = ["disorganized"]
        result = analyze_reviews(reviews, keywords)
        assert result["ops_complaint_count"] == 10
        assert len(result["ops_complaint_samples"]) == 5

    def test_empty_reviews(self):
        result = analyze_reviews([], ["keyword"])
        assert result["total_analyzed"] == 0
        assert result["ops_complaint_count"] == 0
        assert result["owner_response_rate"] == 0.0

    def test_no_matching_keywords(self):
        reviews = [{"review_text": "Terrible experience", "review_rating": 1}]
        result = analyze_reviews(reviews, ["never called back"])
        assert result["ops_complaint_count"] == 0

    def test_alternate_field_names(self):
        reviews = [{"text": "disorganized mess", "rating": 2}]
        result = analyze_reviews(reviews, ["disorganized"])
        assert result["ops_complaint_count"] == 1

    def test_response_field_name(self):
        reviews = [{"review_text": "Bad", "review_rating": 1, "response": "We'll fix it"}]
        result = analyze_reviews(reviews, [])
        assert result["owner_response_rate"] == 1.0


class TestFetchReviewsOutscraper:
    @respx.mock
    def test_fetches_reviews(self):
        respx.get("https://api.app.outscraper.com/maps/reviews-v3").mock(
            return_value=httpx.Response(200, json={
                "data": [{"reviews_data": [
                    {"review_text": "Great!", "review_rating": 5},
                    {"review_text": "Bad!", "review_rating": 1},
                ]}]
            })
        )
        reviews = fetch_reviews_outscraper("ChIJ_test", "fake-key")
        assert len(reviews) == 2

    @respx.mock
    def test_empty_response(self):
        respx.get("https://api.app.outscraper.com/maps/reviews-v3").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        reviews = fetch_reviews_outscraper("ChIJ_test", "fake-key")
        assert reviews == []


class TestEnrichLeadWithReviews:
    def test_applies_analysis_to_lead(self):
        lead = make_lead()
        analysis = {
            "total_analyzed": 50,
            "ops_complaint_count": 5,
            "ops_complaint_samples": ["sample 1", "sample 2"],
            "owner_response_rate": 0.3,
        }
        enrich_lead_with_reviews(lead, analysis)
        assert lead.reviews_analyzed == 50
        assert lead.ops_complaint_count == 5
        assert lead.ops_complaint_samples == ["sample 1", "sample 2"]
        assert lead.owner_response_rate == 0.3
