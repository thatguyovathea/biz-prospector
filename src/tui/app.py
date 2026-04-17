"""Main Textual application for biz-prospector."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static


class BizProspectorApp(App):
    """Terminal dashboard for browsing leads and pipeline stats."""

    TITLE = "biz-prospector"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("biz-prospector TUI — loading...")
        yield Footer()
