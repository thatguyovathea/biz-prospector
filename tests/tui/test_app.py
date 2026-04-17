"""Tests for the TUI application."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.tui.app import BizProspectorApp
from src.tui.screens import LeadsScreen, RunsScreen, StatsScreen
from src.tui.widgets import StatusBar
from tests.conftest import make_lead


def _mock_get_db(path=None):
    return MagicMock()


def _mock_get_leads(conn, **kwargs):
    return [
        make_lead(id="1", business_name="Acme", score=78.5, metro="portland-or", category="HVAC"),
    ]


def _mock_get_run_history(conn, limit=20):
    return [{"id": 1, "vertical": "hvac", "metro": "portland-or", "started_at": "2026-04-16T10:30:00",
             "completed_at": "2026-04-16T10:35:00", "scraped_count": 50, "enriched_count": 45,
             "qualified_count": 12, "emailed_count": 10, "threshold": 55.0, "is_re_enrich": 0}]


def _mock_get_dedup_stats(conn):
    return {"enrich": 100}


@pytest.fixture
def patched_db():
    with patch("src.tui.app.get_db", side_effect=_mock_get_db), \
         patch("src.tui.app.get_leads", side_effect=_mock_get_leads), \
         patch("src.tui.app.get_run_history", side_effect=_mock_get_run_history), \
         patch("src.tui.screens.get_leads", side_effect=_mock_get_leads), \
         patch("src.tui.screens.get_run_history", side_effect=_mock_get_run_history), \
         patch("src.tui.screens.get_dedup_stats", side_effect=_mock_get_dedup_stats):
        yield


class TestAppSmoke:
    @pytest.mark.asyncio
    async def test_app_launches_and_quits(self, patched_db):
        app = BizProspectorApp()
        async with app.run_test() as pilot:
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_app_shows_leads_screen_by_default(self, patched_db):
        app = BizProspectorApp()
        async with app.run_test():
            leads_screens = app.query(LeadsScreen)
            assert len(leads_screens) >= 1

    @pytest.mark.asyncio
    async def test_app_has_status_bar(self, patched_db):
        app = BizProspectorApp()
        async with app.run_test():
            bars = app.query(StatusBar)
            assert len(bars) == 1


class TestTabSwitching:
    @pytest.mark.asyncio
    async def test_f1_shows_leads(self, patched_db):
        app = BizProspectorApp()
        async with app.run_test() as pilot:
            await pilot.press("f2")
            await pilot.press("f1")
            content = app.query_one("#tab-content")
            assert content.query(LeadsScreen)

    @pytest.mark.asyncio
    async def test_f2_shows_runs(self, patched_db):
        app = BizProspectorApp()
        async with app.run_test() as pilot:
            await pilot.press("f2")
            content = app.query_one("#tab-content")
            assert content.query(RunsScreen)

    @pytest.mark.asyncio
    async def test_f3_shows_stats(self, patched_db):
        app = BizProspectorApp()
        async with app.run_test() as pilot:
            await pilot.press("f3")
            content = app.query_one("#tab-content")
            assert content.query(StatsScreen)
