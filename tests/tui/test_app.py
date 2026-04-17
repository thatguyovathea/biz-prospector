"""Tests for the TUI application."""

from __future__ import annotations

import pytest

from src.tui.app import BizProspectorApp


class TestAppSmoke:
    @pytest.mark.asyncio
    async def test_app_launches_and_quits(self):
        """App should start and respond to quit key."""
        app = BizProspectorApp()
        async with app.run_test() as pilot:
            await pilot.press("q")
