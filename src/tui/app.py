"""Main Textual application for biz-prospector."""

from __future__ import annotations

import sqlite3

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer

from src.db import get_db, get_leads, get_run_history
from src.tui.screens import LeadsScreen, RunsScreen, StatsScreen
from src.tui.widgets import StatusBar


class BizProspectorApp(App):
    """Terminal dashboard for browsing leads and pipeline stats."""

    TITLE = "biz-prospector"

    CSS = """
    #tab-content {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("f1", "show_tab('leads')", "Leads"),
        ("f2", "show_tab('runs')", "Runs"),
        ("f3", "show_tab('stats')", "Stats"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._conn: sqlite3.Connection | None = None
        self._current_tab = "leads"

    def on_mount(self) -> None:
        self._conn = get_db()
        self._refresh_status_bar()
        self._show_screen("leads")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(id="tab-content")
        yield StatusBar("Loading...", 0, 0)
        yield Footer()

    def _show_screen(self, tab: str) -> None:
        self._current_tab = tab
        container = self.query_one("#tab-content")
        container.remove_children()

        if tab == "leads":
            container.mount(LeadsScreen(self._conn))
        elif tab == "runs":
            container.mount(RunsScreen(self._conn))
        elif tab == "stats":
            container.mount(StatsScreen(self._conn))

        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        if self._conn is None:
            return
        try:
            all_leads = get_leads(self._conn)
            total = len(all_leads)
            scored = sum(1 for l in all_leads if l.score is not None)

            runs = get_run_history(self._conn, limit=1)
            if runs:
                last_run = runs[0]["started_at"][:16] if runs[0]["started_at"] else "Unknown"
            else:
                last_run = "No runs yet"

            self.query_one(StatusBar).update_stats(last_run, total, scored)
        except Exception:
            pass

    def action_show_tab(self, tab: str) -> None:
        self._show_screen(tab)
