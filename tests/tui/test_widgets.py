"""Tests for TUI widgets: StatusBar, FilterBar, LeadDetail."""

from __future__ import annotations

import pytest

from textual.app import App, ComposeResult

from src.tui.widgets import FilterBar, LeadDetail, StatusBar
from tests.conftest import make_lead


# ---------------------------------------------------------------------------
# Helper test apps
# ---------------------------------------------------------------------------


class StatusBarApp(App):
    """Minimal app that mounts a StatusBar for testing."""

    def __init__(self, last_run: str, total_leads: int, scored_leads: int) -> None:
        self._last_run = last_run
        self._total_leads = total_leads
        self._scored_leads = scored_leads
        super().__init__()

    def compose(self) -> ComposeResult:
        yield StatusBar(self._last_run, self._total_leads, self._scored_leads)


class FilterBarApp(App):
    """Minimal app that mounts a FilterBar for testing."""

    received_messages: list[FilterBar.Applied] = []

    def compose(self) -> ComposeResult:
        self.received_messages = []
        yield FilterBar()

    def on_filter_bar_applied(self, message: FilterBar.Applied) -> None:
        self.received_messages.append(message)


class LeadDetailApp(App):
    """Minimal app that mounts a LeadDetail for testing."""

    def compose(self) -> ComposeResult:
        yield LeadDetail()


# ---------------------------------------------------------------------------
# Task 2: StatusBar tests
# ---------------------------------------------------------------------------


class TestStatusBar:
    def test_render_text_contains_last_run(self):
        bar = StatusBar(last_run="2026-04-15 09:00", total_leads=50, scored_leads=30)
        text = bar.render_text()
        assert "Last run: 2026-04-15 09:00" in text

    def test_render_text_contains_lead_count(self):
        bar = StatusBar(last_run="never", total_leads=120, scored_leads=80)
        text = bar.render_text()
        assert "120 leads" in text

    def test_render_text_contains_scored_count(self):
        bar = StatusBar(last_run="never", total_leads=120, scored_leads=80)
        text = bar.render_text()
        assert "80 scored" in text

    def test_render_text_empty_state(self):
        bar = StatusBar(last_run="never", total_leads=0, scored_leads=0)
        text = bar.render_text()
        assert "0 leads" in text
        assert "0 scored" in text

    def test_update_stats_changes_render(self):
        bar = StatusBar(last_run="never", total_leads=0, scored_leads=0)
        bar.update_stats(last_run="2026-04-16 12:00", total_leads=42, scored_leads=17)
        text = bar.render_text()
        assert "2026-04-16 12:00" in text
        assert "42 leads" in text
        assert "17 scored" in text

    def test_render_text_format(self):
        """Full format check: all three segments joined by |."""
        bar = StatusBar(last_run="2026-01-01", total_leads=5, scored_leads=3)
        text = bar.render_text()
        assert text == "Last run: 2026-01-01 | 5 leads | 3 scored"

    @pytest.mark.asyncio
    async def test_status_bar_mounts_in_app(self):
        """StatusBar should mount and its render_text should work inside an app."""
        app = StatusBarApp(last_run="2026-04-15", total_leads=10, scored_leads=5)
        async with app.run_test() as pilot:
            bar = app.query_one(StatusBar)
            text = bar.render_text()
            assert "2026-04-15" in text
            assert "10 leads" in text
            assert "5 scored" in text


# ---------------------------------------------------------------------------
# Task 3: FilterBar tests
# ---------------------------------------------------------------------------


class TestFilterBar:
    @pytest.mark.asyncio
    async def test_three_inputs_render(self):
        """FilterBar should contain exactly 3 Input widgets."""
        app = FilterBarApp()
        async with app.run_test() as pilot:
            from textual.widgets import Input
            inputs = app.query(Input)
            assert len(inputs) == 3

    @pytest.mark.asyncio
    async def test_apply_button_exists(self):
        """FilterBar should contain an Apply button."""
        app = FilterBarApp()
        async with app.run_test() as pilot:
            from textual.widgets import Button
            buttons = app.query(Button)
            assert len(buttons) == 1
            assert buttons.first(Button).id == "apply-filters"

    @pytest.mark.asyncio
    async def test_empty_inputs_map_to_none(self):
        """Applied message should have all None when inputs are empty."""
        app = FilterBarApp()
        async with app.run_test() as pilot:
            await pilot.click("#apply-filters")
            await pilot.pause()
            assert len(app.received_messages) == 1
            msg = app.received_messages[0]
            assert msg.metro is None
            assert msg.category is None
            assert msg.min_score is None

    @pytest.mark.asyncio
    async def test_filled_inputs_map_to_values(self):
        """Applied message should carry entered values."""
        from textual.widgets import Input
        app = FilterBarApp()
        async with app.run_test() as pilot:
            # Set values directly on the Input widgets (pilot.type not available in this version)
            app.query_one("#filter-metro", Input).value = "portland-or"
            app.query_one("#filter-category", Input).value = "HVAC"
            app.query_one("#filter-score", Input).value = "60"
            await pilot.click("#apply-filters")
            await pilot.pause()
            assert len(app.received_messages) == 1
            msg = app.received_messages[0]
            assert msg.metro == "portland-or"
            assert msg.category == "HVAC"
            assert msg.min_score == 60.0

    @pytest.mark.asyncio
    async def test_min_score_parses_to_float(self):
        """min_score should be a float, not a string."""
        from textual.widgets import Input
        app = FilterBarApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-score", Input).value = "75.5"
            await pilot.click("#apply-filters")
            await pilot.pause()
            assert len(app.received_messages) == 1
            msg = app.received_messages[0]
            assert isinstance(msg.min_score, float)
            assert msg.min_score == 75.5

    @pytest.mark.asyncio
    async def test_enter_in_metro_input_emits_applied(self):
        """Pressing Enter in any Input should emit Applied via on_input_submitted."""
        from textual.widgets import Input
        app = FilterBarApp()
        async with app.run_test() as pilot:
            metro_input = app.query_one("#filter-metro", Input)
            metro_input.value = "seattle-wa"
            # Call the synchronous handler directly, then flush the message queue
            filter_bar = app.query_one(FilterBar)
            filter_bar.on_input_submitted(Input.Submitted(metro_input, metro_input.value))
            await pilot.pause()
            assert len(app.received_messages) >= 1
            msg = app.received_messages[0]
            assert msg.metro == "seattle-wa"

    @pytest.mark.asyncio
    async def test_partial_inputs_map_correctly(self):
        """Only filled inputs should have values; empty ones map to None."""
        from textual.widgets import Input
        app = FilterBarApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-metro", Input).value = "denver-co"
            await pilot.click("#apply-filters")
            await pilot.pause()
            assert len(app.received_messages) == 1
            msg = app.received_messages[0]
            assert msg.metro == "denver-co"
            assert msg.category is None
            assert msg.min_score is None


# ---------------------------------------------------------------------------
# Task 4: LeadDetail tests
# ---------------------------------------------------------------------------


class TestLeadDetail:
    def test_empty_state_message(self):
        """No lead selected: should show placeholder text."""
        widget = LeadDetail()
        assert widget.render_text() == "Select a lead from the table"

    def test_show_lead_displays_business_name(self):
        lead = make_lead(business_name="Portland HVAC Co.")
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "Portland HVAC Co." in text

    def test_show_lead_displays_score(self):
        lead = make_lead(score=72.5)
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "72.5" in text

    def test_show_lead_no_score(self):
        lead = make_lead(score=None)
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "Overall:" in text
        assert "—" in text

    def test_show_lead_score_breakdown_sorted_descending(self):
        """Score breakdown should appear sorted from highest to lowest."""
        lead = make_lead(
            score=80.0,
            score_breakdown={"no_crm_detected": 15.0, "manual_job_postings": 25.0, "no_chat_widget": 5.0},
        )
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        pos_manual = text.index("manual_job_postings")
        pos_crm = text.index("no_crm_detected")
        pos_chat = text.index("no_chat_widget")
        assert pos_manual < pos_crm < pos_chat

    def test_audit_flags_yes_no_unknown(self):
        lead = make_lead(
            has_crm=True,
            has_chat_widget=False,
            has_scheduling=None,
        )
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        # CRM present = Yes, Chat = No, Scheduling = ?
        lines = {line.split(":")[0].strip(): line for line in text.splitlines() if ":" in line}
        assert "Yes" in lines.get("CRM", "")
        assert "No" in lines.get("Chat Widget", "")
        assert "?" in lines.get("Scheduling", "")

    def test_audit_ssl_and_mobile(self):
        lead = make_lead(has_ssl=True, is_mobile_responsive=False)
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "SSL" in text
        assert "Yes" in text  # SSL = True
        assert "Mobile Responsive" in text

    def test_audit_page_speed_score(self):
        lead = make_lead(page_speed_score=88)
        widget = LeadDetail()
        widget.show_lead(lead)
        assert "88" in widget.render_text()

    def test_audit_tech_stack(self):
        lead = make_lead(tech_stack=["WordPress", "Google Analytics"])
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "WordPress" in text
        assert "Google Analytics" in text

    def test_reviews_rating_and_count(self):
        lead = make_lead(rating=4.3, review_count=102)
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "4.3" in text
        assert "102" in text

    def test_reviews_ops_complaint_count(self):
        lead = make_lead(ops_complaint_count=7)
        widget = LeadDetail()
        widget.show_lead(lead)
        assert "7" in widget.render_text()

    def test_reviews_complaint_samples_first_three(self):
        """Only the first 3 complaint samples should be shown."""
        samples = ["never called back", "very disorganized", "hard to reach", "no show", "missed visit"]
        lead = make_lead(ops_complaint_samples=samples)
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "never called back" in text
        assert "very disorganized" in text
        assert "hard to reach" in text
        # 4th and 5th should NOT appear
        assert "no show" not in text
        assert "missed visit" not in text

    def test_reviews_owner_response_rate(self):
        lead = make_lead(owner_response_rate=0.75)
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "75%" in text

    def test_contact_info_displayed(self):
        lead = make_lead(
            contact_name="Jane Smith",
            contact_email="jane@example.com",
            contact_title="Operations Manager",
            linkedin_url="https://linkedin.com/in/janesmith",
        )
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "Jane Smith" in text
        assert "jane@example.com" in text
        assert "Operations Manager" in text
        assert "https://linkedin.com/in/janesmith" in text

    def test_contact_empty_fields_show_dash(self):
        lead = make_lead(contact_name="", contact_email="", contact_title="")
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        # Should show dashes for empty contact fields
        assert "—" in text

    def test_job_postings_section(self):
        lead = make_lead(
            active_job_postings=3,
            manual_process_postings=2,
            manual_process_titles=["Receptionist", "Data Entry Clerk", "Filing Clerk", "Admin Asst", "Scheduler", "Extra"],
        )
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "3" in text
        assert "2" in text
        assert "Receptionist" in text
        # Only first 5 titles shown; "Extra" should not appear
        assert "Extra" not in text

    def test_employees_section(self):
        lead = make_lead(
            employee_count=25,
            founded_year=1998,
            manual_role_count=8,
            tech_role_count=2,
        )
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "25" in text
        assert "1998" in text
        assert "8" in text
        assert "2" in text

    def test_timestamps_section(self):
        from datetime import datetime
        scraped = datetime(2026, 4, 10, 8, 0, 0)
        lead = make_lead(scraped_at=scraped)
        widget = LeadDetail()
        widget.show_lead(lead)
        text = widget.render_text()
        assert "Scraped" in text
        assert "2026-04-10" in text

    def test_show_lead_replaces_previous_lead(self):
        lead1 = make_lead(business_name="First Business")
        lead2 = make_lead(business_name="Second Business")
        widget = LeadDetail()
        widget.show_lead(lead1)
        assert "First Business" in widget.render_text()
        widget.show_lead(lead2)
        text = widget.render_text()
        assert "Second Business" in text
        assert "First Business" not in text

    @pytest.mark.asyncio
    async def test_lead_detail_mounts_in_app(self):
        """LeadDetail should mount cleanly and show empty state."""
        app = LeadDetailApp()
        async with app.run_test() as pilot:
            detail = app.query_one(LeadDetail)
            assert detail.render_text() == "Select a lead from the table"

    @pytest.mark.asyncio
    async def test_lead_detail_show_lead_in_app(self):
        """After show_lead(), render_text() reflects the new lead."""
        app = LeadDetailApp()
        async with app.run_test() as pilot:
            lead = make_lead(business_name="Austin Plumbing LLC", score=68.0)
            detail = app.query_one(LeadDetail)
            detail.show_lead(lead)
            text = detail.render_text()
            assert "Austin Plumbing LLC" in text
            assert "68.0" in text
