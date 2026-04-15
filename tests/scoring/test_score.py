"""Tests for the scoring engine — parametrized across all factors and weight combos."""

from unittest.mock import patch

import pytest

from src.scoring.score import score_lead, score_leads, _normalize, DEFAULT_WEIGHTS
from tests.conftest import make_lead


class TestNormalize:
    def test_mid_range(self):
        assert _normalize(5, 0, 10) == 0.5

    def test_at_min(self):
        assert _normalize(0, 0, 10) == 0.0

    def test_at_max(self):
        assert _normalize(10, 0, 10) == 1.0

    def test_below_min_clamps(self):
        assert _normalize(-5, 0, 10) == 0.0

    def test_above_max_clamps(self):
        assert _normalize(15, 0, 10) == 1.0

    def test_equal_min_max(self):
        assert _normalize(5, 5, 5) == 0.0


class TestWebsiteOutdatedFactor:
    def test_no_ssl(self):
        lead = make_lead(has_ssl=False, is_mobile_responsive=True, tech_stack=["react"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == pytest.approx(0.3, abs=0.01)

    def test_not_mobile_responsive(self):
        lead = make_lead(has_ssl=True, is_mobile_responsive=False, tech_stack=["react"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == pytest.approx(0.4, abs=0.01)

    def test_no_modern_tech(self):
        lead = make_lead(has_ssl=True, is_mobile_responsive=True, tech_stack=["wordpress"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == pytest.approx(0.3, abs=0.01)

    def test_all_outdated_signals(self):
        lead = make_lead(has_ssl=False, is_mobile_responsive=False, tech_stack=["wordpress"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == 1.0

    def test_modern_website(self):
        lead = make_lead(has_ssl=True, is_mobile_responsive=True, tech_stack=["react"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == 0.0

    def test_empty_tech_stack(self):
        lead = make_lead(has_ssl=True, is_mobile_responsive=True, tech_stack=[])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == 0.0


class TestBooleanFactors:
    @pytest.mark.parametrize("field,factor_name", [
        ("has_crm", "no_crm_detected"),
        ("has_scheduling", "no_scheduling_tool"),
        ("has_chat_widget", "no_chat_widget"),
    ])
    def test_missing_tool_scores_one(self, field, factor_name):
        lead = make_lead(**{field: False})
        score_lead(lead)
        assert lead.score_breakdown[factor_name] == 1.0

    @pytest.mark.parametrize("field,factor_name", [
        ("has_crm", "no_crm_detected"),
        ("has_scheduling", "no_scheduling_tool"),
        ("has_chat_widget", "no_chat_widget"),
    ])
    def test_present_tool_scores_zero(self, field, factor_name):
        lead = make_lead(**{field: True})
        score_lead(lead)
        assert lead.score_breakdown[factor_name] == 0.0

    @pytest.mark.parametrize("field,factor_name", [
        ("has_crm", "no_crm_detected"),
        ("has_scheduling", "no_scheduling_tool"),
        ("has_chat_widget", "no_chat_widget"),
    ])
    def test_none_scores_zero(self, field, factor_name):
        lead = make_lead(**{field: None})
        score_lead(lead)
        assert lead.score_breakdown[factor_name] == 0.0


class TestManualJobPostingsFactor:
    def test_zero_postings(self):
        lead = make_lead(active_job_postings=0, manual_process_postings=0)
        score_lead(lead)
        assert lead.score_breakdown["manual_job_postings"] == 0.0

    def test_some_manual_postings(self):
        lead = make_lead(active_job_postings=5, manual_process_postings=1)
        score_lead(lead)
        score = lead.score_breakdown["manual_job_postings"]
        assert 0 < score < 1

    def test_many_manual_postings(self):
        lead = make_lead(active_job_postings=10, manual_process_postings=5)
        score_lead(lead)
        assert lead.score_breakdown["manual_job_postings"] == 1.0

    def test_no_active_postings_no_score(self):
        lead = make_lead(active_job_postings=0, manual_process_postings=3)
        score_lead(lead)
        assert lead.score_breakdown["manual_job_postings"] == 0.0


class TestNegativeReviewsFactor:
    def test_high_complaint_ratio(self):
        lead = make_lead(reviews_analyzed=100, ops_complaint_count=15)
        score_lead(lead)
        assert lead.score_breakdown["negative_reviews_ops"] == 1.0

    def test_low_complaint_ratio(self):
        lead = make_lead(reviews_analyzed=100, ops_complaint_count=2)
        score_lead(lead)
        score = lead.score_breakdown["negative_reviews_ops"]
        assert 0 < score < 1

    def test_no_reviews(self):
        lead = make_lead(reviews_analyzed=0, ops_complaint_count=0)
        score_lead(lead)
        assert lead.score_breakdown["negative_reviews_ops"] == 0.0

    def test_low_owner_response_bonus(self):
        lead = make_lead(reviews_analyzed=100, ops_complaint_count=5, owner_response_rate=0.1)
        score_lead(lead)
        score_with_bonus = lead.score_breakdown["negative_reviews_ops"]

        lead2 = make_lead(reviews_analyzed=100, ops_complaint_count=5, owner_response_rate=0.5)
        score_lead(lead2)
        score_without_bonus = lead2.score_breakdown["negative_reviews_ops"]

        assert score_with_bonus > score_without_bonus


class TestCompositeScoring:
    def test_perfect_lead_near_zero(self):
        lead = make_lead(
            has_ssl=True, is_mobile_responsive=True, tech_stack=["react"],
            has_crm=True, has_scheduling=True, has_chat_widget=True,
            active_job_postings=5, manual_process_postings=0,
            reviews_analyzed=50, ops_complaint_count=0,
        )
        score_lead(lead)
        assert lead.score <= 5.0

    def test_worst_lead_near_hundred(self):
        lead = make_lead(
            has_ssl=False, is_mobile_responsive=False, tech_stack=["wordpress"],
            has_crm=False, has_scheduling=False, has_chat_widget=False,
            active_job_postings=10, manual_process_postings=5,
            reviews_analyzed=100, ops_complaint_count=20,
            owner_response_rate=0.05,
        )
        score_lead(lead)
        assert lead.score >= 80.0

    def test_score_always_0_to_100(self):
        for has_crm in [True, False, None]:
            for has_ssl in [True, False, None]:
                lead = make_lead(has_crm=has_crm, has_ssl=has_ssl)
                score_lead(lead)
                assert 0 <= lead.score <= 100

    def test_default_weights_sum(self):
        assert sum(DEFAULT_WEIGHTS.values()) == 100

    def test_breakdown_has_all_factors(self):
        lead = make_lead()
        score_lead(lead)
        expected_keys = {
            "website_outdated", "no_crm_detected", "no_scheduling_tool",
            "no_chat_widget", "manual_job_postings", "negative_reviews_ops",
            "business_age", "employee_count",
        }
        assert set(lead.score_breakdown.keys()) == expected_keys

    def test_breakdown_values_0_to_1(self):
        lead = make_lead(
            has_ssl=False, has_crm=False,
            reviews_analyzed=50, ops_complaint_count=10,
        )
        score_lead(lead)
        for value in lead.score_breakdown.values():
            assert 0 <= value <= 1

    def test_scored_at_set(self):
        lead = make_lead()
        score_lead(lead)
        assert lead.scored_at is not None


class TestZeroWeights:
    def test_zero_total_weight_gives_zero_score(self):
        lead = make_lead(has_crm=False)
        zero_weights = {k: 0 for k in DEFAULT_WEIGHTS}
        score_lead(lead, weights=zero_weights)
        assert lead.score == 0.0


class TestCustomWeights:
    def test_custom_weights_applied(self):
        lead = make_lead(has_crm=False, has_scheduling=False)
        zero_weights = {k: 0 for k in DEFAULT_WEIGHTS}

        score_lead(lead, weights={**zero_weights, "no_crm_detected": 100})
        score_crm_heavy = lead.score

        score_lead(lead, weights={**zero_weights, "no_scheduling_tool": 100})
        score_sched_heavy = lead.score

        assert score_crm_heavy == pytest.approx(100.0, abs=1)
        assert score_sched_heavy == pytest.approx(100.0, abs=1)


class TestVerticalOverrides:
    def test_hvac_weights(self, sample_settings, sample_vertical_config):
        leads = [make_lead(has_scheduling=False)]
        with patch("src.scoring.score.load_settings", return_value=sample_settings), \
             patch("src.scoring.score.load_vertical", return_value=sample_vertical_config):
            scored = score_leads(leads, vertical="hvac")
        assert len(scored) == 1
        assert scored[0].score is not None

    def test_no_vertical_uses_defaults(self, sample_settings):
        leads = [make_lead()]
        with patch("src.scoring.score.load_settings", return_value=sample_settings):
            scored = score_leads(leads, vertical=None)
        assert len(scored) == 1

    def test_sorted_descending(self, sample_settings):
        leads = [
            make_lead(id="low", has_crm=True, has_scheduling=True, has_chat_widget=True),
            make_lead(id="high", has_crm=False, has_scheduling=False, has_chat_widget=False),
        ]
        with patch("src.scoring.score.load_settings", return_value=sample_settings):
            scored = score_leads(leads)
        assert scored[0].score >= scored[1].score
