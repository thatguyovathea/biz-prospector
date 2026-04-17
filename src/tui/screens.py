"""TUI screens for biz-prospector."""

from __future__ import annotations

import sqlite3

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Static

from src.db import get_leads, get_lead, get_run_history, get_dedup_stats
from src.models import Lead
from src.tui.widgets import FilterBar, LeadDetail


class LeadCountLabel(Static):
    DEFAULT_CSS = """
    LeadCountLabel {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._count = 0
        self._total = 0

    def set_counts(self, shown: int, total: int) -> None:
        self._count = shown
        self._total = total
        self.update(self.render_text())

    def render_text(self) -> str:
        if self._count == self._total:
            return f"{self._count} leads"
        return f"{self._count} of {self._total} leads"


class LeadsScreen(Static):
    DEFAULT_CSS = """
    LeadsScreen {
        height: 1fr;
        width: 1fr;
    }
    LeadsScreen Horizontal {
        height: 1fr;
    }
    LeadsScreen #table-pane {
        width: 1fr;
    }
    LeadsScreen DataTable {
        height: 1fr;
    }
    LeadsScreen LeadDetail {
        width: 2fr;
    }
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self._conn = conn
        self._leads: list[Lead] = []
        self._all_leads_count = 0
        self._count_label = LeadCountLabel()

    def compose(self) -> ComposeResult:
        yield FilterBar()
        with Horizontal():
            with Static(id="table-pane"):
                yield DataTable(id="leads-table", cursor_type="row")
                yield self._count_label
            yield LeadDetail()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Business Name", "Score", "Metro", "Category")
        self._load_leads()

    def _load_leads(self, metro=None, category=None, min_score=None) -> None:
        all_leads = get_leads(self._conn)
        self._all_leads_count = len(all_leads)
        self._leads = get_leads(self._conn, metro=metro, category=category, min_score=min_score)
        self._leads.sort(key=lambda l: l.score or 0, reverse=True)
        table = self.query_one(DataTable)
        table.clear()
        for lead in self._leads:
            table.add_row(
                lead.business_name[:30],
                f"{lead.score:.1f}" if lead.score is not None else "—",
                lead.metro,
                lead.category,
                key=lead.id,
            )
        self._count_label.set_counts(len(self._leads), self._all_leads_count)

    def on_filter_bar_applied(self, event: FilterBar.Applied) -> None:
        self._load_leads(metro=event.metro, category=event.category, min_score=event.min_score)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value is not None:
            row_idx = event.cursor_row
            if 0 <= row_idx < len(self._leads):
                lead = self._leads[row_idx]
                self.query_one(LeadDetail).show_lead(lead)
