"""Tests for HTML report generator."""

from unittest.mock import patch

import pytest

from src.reporting.html_report import (
    _score_histogram_bins,
    _tech_stack_counts,
    _missing_tools_counts,
    _summary_stats,
    _esc,
    _tool_icon,
    _render_histogram,
    _render_top_leads_table,
    _render_tech_table,
    _render_tools_table,
    generate_report,
    save_report,
)
from tests.conftest import make_lead


# --- Helper data ---

def _scored_leads():
    """Create a list of leads with various scores and attributes."""
    return [
        make_lead(
            id="high", business_name="High Score HVAC",
            score=85.0, has_crm=False, has_chat_widget=False, has_scheduling=False,
            has_ssl=True, is_mobile_responsive=True,
            tech_stack=["wordpress", "google_analytics"],
            contact_name="Bob Owner", contact_email="bob@high.com",
            outreach_email="Subject: Hi\n\nHello Bob",
            manual_process_postings=3, ops_complaint_count=8,
            category="HVAC", metro="portland-or",
        ),
        make_lead(
            id="mid", business_name="Mid Score Dental",
            score=55.0, has_crm=True, has_chat_widget=False, has_scheduling=True,
            has_ssl=True, is_mobile_responsive=False,
            tech_stack=["wordpress", "bootstrap"],
            contact_name="Jane Manager", contact_email="jane@mid.com",
            outreach_email="",
            manual_process_postings=1, ops_complaint_count=2,
            category="Dental", metro="seattle-wa",
        ),
        make_lead(
            id="low", business_name="Low Score Auto",
            score=20.0, has_crm=True, has_chat_widget=True, has_scheduling=True,
            has_ssl=True, is_mobile_responsive=True,
            tech_stack=["react", "google_analytics"],
            contact_name="", contact_email="",
            outreach_email="",
            manual_process_postings=0, ops_complaint_count=0,
            category="Auto Repair", metro="portland-or",
        ),
    ]


class TestScoreHistogramBins:
    def test_creates_ten_bins(self):
        leads = _scored_leads()
        bins = _score_histogram_bins(leads)
        assert len(bins) == 10

    def test_correct_counts(self):
        leads = _scored_leads()
        bins = _score_histogram_bins(leads)
        # score=20 in 20-30 bin (index 2), score=55 in 50-60 bin (index 5), score=85 in 80-90 bin (index 8)
        assert bins[2]["count"] == 1
        assert bins[5]["count"] == 1
        assert bins[8]["count"] == 1
        # Others should be zero
        assert bins[0]["count"] == 0

    def test_empty_leads(self):
        assert _score_histogram_bins([]) == []

    def test_no_scored_leads(self):
        leads = [make_lead(score=None)]
        assert _score_histogram_bins(leads) == []

    def test_pct_calculation(self):
        leads = _scored_leads()
        bins = _score_histogram_bins(leads)
        # All non-zero bins have count=1, so pct should be 100
        non_zero = [b for b in bins if b["count"] > 0]
        for b in non_zero:
            assert b["pct"] == 100.0

    def test_custom_bin_count(self):
        leads = _scored_leads()
        bins = _score_histogram_bins(leads, num_bins=5)
        assert len(bins) == 5


class TestTechStackCounts:
    def test_counts_technologies(self):
        leads = _scored_leads()
        counts = _tech_stack_counts(leads)
        count_dict = dict(counts)
        assert count_dict["wordpress"] == 2
        assert count_dict["google_analytics"] == 2
        assert count_dict["bootstrap"] == 1
        assert count_dict["react"] == 1

    def test_sorted_descending(self):
        leads = _scored_leads()
        counts = _tech_stack_counts(leads)
        counts_only = [c for _, c in counts]
        assert counts_only == sorted(counts_only, reverse=True)

    def test_empty_leads(self):
        assert _tech_stack_counts([]) == []

    def test_no_tech_stack(self):
        leads = [make_lead(tech_stack=[])]
        assert _tech_stack_counts(leads) == []


class TestMissingToolsCounts:
    def test_counts_missing(self):
        leads = _scored_leads()
        tools = _missing_tools_counts(leads)
        assert tools["CRM"]["missing"] == 1
        assert tools["CRM"]["present"] == 2
        assert tools["Chat Widget"]["missing"] == 2
        assert tools["Scheduling"]["missing"] == 1

    def test_handles_none_values(self):
        leads = [make_lead(has_crm=None, has_chat_widget=None)]
        tools = _missing_tools_counts(leads)
        assert tools["CRM"]["unknown"] == 1
        assert tools["Chat Widget"]["unknown"] == 1

    def test_empty_leads(self):
        tools = _missing_tools_counts([])
        for label in tools:
            assert tools[label]["missing"] == 0
            assert tools[label]["present"] == 0


class TestSummaryStats:
    def test_basic_stats(self):
        leads = _scored_leads()
        stats = _summary_stats(leads)
        assert stats["total_leads"] == 3
        assert stats["scored_leads"] == 3
        assert stats["max_score"] == 85.0
        assert stats["min_score"] == 20.0
        assert 50 < stats["avg_score"] < 55  # (85+55+20)/3 = 53.3

    def test_with_email_count(self):
        leads = _scored_leads()
        stats = _summary_stats(leads)
        assert stats["with_email"] == 2  # bob and jane

    def test_with_outreach_count(self):
        leads = _scored_leads()
        stats = _summary_stats(leads)
        assert stats["with_outreach"] == 1  # only high has outreach

    def test_empty_leads(self):
        stats = _summary_stats([])
        assert stats["total_leads"] == 0
        assert stats["avg_score"] == 0

    def test_no_scores(self):
        leads = [make_lead(score=None)]
        stats = _summary_stats(leads)
        assert stats["scored_leads"] == 0
        assert stats["avg_score"] == 0


class TestEsc:
    def test_escapes_html(self):
        assert _esc("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"

    def test_plain_text(self):
        assert _esc("hello") == "hello"


class TestToolIcon:
    def test_true(self):
        assert "present" in _tool_icon(True)
        assert "Yes" in _tool_icon(True)

    def test_false(self):
        assert "missing" in _tool_icon(False)
        assert "No" in _tool_icon(False)

    def test_none(self):
        assert "unknown" in _tool_icon(None)
        assert "?" in _tool_icon(None)


class TestRenderHistogram:
    def test_renders_bars(self):
        leads = _scored_leads()
        bins = _score_histogram_bins(leads)
        html = _render_histogram(bins)
        assert "bar-row" in html
        assert "bar-fill" in html

    def test_empty_bins(self):
        html = _render_histogram([])
        assert "No scores" in html


class TestRenderTopLeadsTable:
    def test_renders_rows(self):
        leads = _scored_leads()
        html = _render_top_leads_table(leads)
        assert "High Score HVAC" in html
        assert "Mid Score Dental" in html
        assert "Low Score Auto" in html

    def test_sorted_by_score(self):
        leads = _scored_leads()
        html = _render_top_leads_table(leads)
        high_pos = html.index("High Score HVAC")
        low_pos = html.index("Low Score Auto")
        assert high_pos < low_pos

    def test_limits_to_n(self):
        leads = _scored_leads()
        html = _render_top_leads_table(leads, n=1)
        assert "High Score HVAC" in html
        assert "Low Score Auto" not in html

    def test_handles_none_score(self):
        leads = [make_lead(score=None, business_name="No Score Biz")]
        html = _render_top_leads_table(leads)
        assert "No Score Biz" in html


class TestRenderTechTable:
    def test_renders_table(self):
        counts = [("wordpress", 5), ("react", 3)]
        html = _render_tech_table(counts)
        assert "wordpress" in html
        assert "5" in html

    def test_empty(self):
        html = _render_tech_table([])
        assert "No tech stack" in html


class TestRenderToolsTable:
    def test_renders_rows(self):
        tools = {
            "CRM": {"missing": 5, "present": 10, "unknown": 2},
        }
        html = _render_tools_table(tools)
        assert "CRM" in html
        assert "5" in html

    def test_gap_percentage(self):
        tools = {
            "CRM": {"missing": 1, "present": 1, "unknown": 0},
        }
        html = _render_tools_table(tools)
        assert "50%" in html


class TestGenerateReport:
    def test_produces_valid_html(self):
        leads = _scored_leads()
        html = generate_report(leads, title="Test Report", vertical="HVAC", metro="portland-or")
        assert "<!DOCTYPE html>" in html
        assert "Test Report" in html
        assert "HVAC" in html
        assert "portland-or" in html

    def test_contains_all_sections(self):
        leads = _scored_leads()
        html = generate_report(leads)
        assert "Score Distribution" in html
        assert "Top Leads" in html
        assert "Tech Stack" in html
        assert "Tool Gaps" in html

    def test_contains_lead_data(self):
        leads = _scored_leads()
        html = generate_report(leads)
        assert "High Score HVAC" in html
        assert "bob@high.com" in html

    def test_empty_leads(self):
        html = generate_report([])
        assert "<!DOCTYPE html>" in html
        assert "No scores" in html

    def test_no_vertical_or_metro(self):
        html = generate_report(_scored_leads())
        assert "Vertical:" not in html

    def test_xss_prevention(self):
        leads = [make_lead(business_name="<script>alert('xss')</script>", score=50.0)]
        html = generate_report(leads)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html


class TestSaveReport:
    def test_saves_to_file(self, tmp_path):
        leads = _scored_leads()
        with patch("src.reporting.html_report.REPORT_DIR", tmp_path):
            path = save_report(leads, filename="test.html", title="Test")
        assert path.exists()
        content = path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "High Score HVAC" in content

    def test_auto_generates_filename(self, tmp_path):
        leads = _scored_leads()
        with patch("src.reporting.html_report.REPORT_DIR", tmp_path):
            path = save_report(leads, vertical="hvac", metro="portland")
        assert path.exists()
        assert "hvac" in path.name
        assert "portland" in path.name
        assert path.suffix == ".html"

    def test_creates_report_dir(self, tmp_path):
        report_dir = tmp_path / "reports"
        leads = _scored_leads()
        with patch("src.reporting.html_report.REPORT_DIR", report_dir):
            path = save_report(leads, filename="test.html")
        assert report_dir.exists()
        assert path.exists()
