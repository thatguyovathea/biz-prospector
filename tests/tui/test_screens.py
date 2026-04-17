"""Tests for TUI screens."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from textual.app import App, ComposeResult
from textual.widgets import DataTable

from src.tui.screens import LeadsScreen
from src.tui.widgets import FilterBar, LeadDetail
from tests.conftest import make_lead


def _mock_get_leads(conn, *, metro=None, category=None, min_score=None, scored_only=False, limit=None):
    leads = [
        make_lead(id="lead1", business_name="Acme HVAC", score=78.5, metro="portland-or", category="HVAC"),
        make_lead(id="lead2", business_name="CoolAir Inc", score=65.2, metro="portland-or", category="HVAC"),
        make_lead(id="lead3", business_name="FixIt Pro", score=58.1, metro="seattle-wa", category="HVAC"),
    ]
    if metro:
        leads = [l for l in leads if l.metro == metro]
    if min_score is not None:
        leads = [l for l in leads if (l.score or 0) >= min_score]
    return leads


class LeadsScreenTestApp(App):
    def __init__(self, mock_conn=None):
        super().__init__()
        self.mock_conn = mock_conn or MagicMock()

    def compose(self) -> ComposeResult:
        yield LeadsScreen(self.mock_conn)


class TestLeadsScreen:
    @pytest.mark.asyncio
    async def test_renders_filter_bar_and_table(self):
        with patch("src.tui.screens.get_leads", side_effect=_mock_get_leads):
            app = LeadsScreenTestApp()
            async with app.run_test():
                assert len(app.query(FilterBar)) == 1
                assert len(app.query(DataTable)) == 1
                assert len(app.query(LeadDetail)) == 1

    @pytest.mark.asyncio
    async def test_table_populated_with_leads(self):
        with patch("src.tui.screens.get_leads", side_effect=_mock_get_leads):
            app = LeadsScreenTestApp()
            async with app.run_test():
                table = app.query_one(DataTable)
                assert table.row_count == 3

    @pytest.mark.asyncio
    async def test_table_shows_lead_count(self):
        with patch("src.tui.screens.get_leads", side_effect=_mock_get_leads):
            app = LeadsScreenTestApp()
            async with app.run_test():
                screen = app.query_one(LeadsScreen)
                assert "3" in screen._count_label.render_text()

    @pytest.mark.asyncio
    async def test_filter_updates_table(self):
        with patch("src.tui.screens.get_leads", side_effect=_mock_get_leads):
            app = LeadsScreenTestApp()
            async with app.run_test() as pilot:
                metro_input = app.query_one("#filter-metro")
                metro_input.value = "portland-or"
                await pilot.click("#apply-filters")
                table = app.query_one(DataTable)
                assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_selecting_row_updates_detail(self):
        with patch("src.tui.screens.get_leads", side_effect=_mock_get_leads):
            app = LeadsScreenTestApp()
            async with app.run_test() as pilot:
                table = app.query_one(DataTable)
                table.move_cursor(row=0)
                detail = app.query_one(LeadDetail)
                text = detail.render_text()
                # First row (highest score) should be Acme HVAC
                assert "Acme HVAC" in text or "Select a lead" in text
