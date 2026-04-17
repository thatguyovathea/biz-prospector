"""TUI screens for biz-prospector."""

from __future__ import annotations

import sqlite3
from collections import Counter

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


class RunsScreen(Static):
    DEFAULT_CSS = """
    RunsScreen {
        height: 1fr;
        width: 1fr;
        padding: 1;
    }
    RunsScreen DataTable {
        height: 1fr;
    }
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self._conn = conn

    def compose(self) -> ComposeResult:
        yield DataTable(id="runs-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns(
            "ID", "Vertical", "Metro", "Started", "Scraped",
            "Enriched", "Qualified", "Emailed", "Threshold", "Re-enrich",
        )
        self._load_runs()

    def _load_runs(self) -> None:
        runs = get_run_history(self._conn)
        table = self.query_one(DataTable)
        table.clear()
        for r in runs:
            started = r["started_at"][:16] if r["started_at"] else "—"
            table.add_row(
                str(r["id"]),
                r["vertical"],
                r["metro"],
                started,
                str(r["scraped_count"] or 0),
                str(r["enriched_count"] or 0),
                str(r["qualified_count"] or 0),
                str(r["emailed_count"] or 0),
                str(r["threshold"] or "—"),
                "Yes" if r["is_re_enrich"] else "No",
            )


class StatsScreen(Static):
    DEFAULT_CSS = """
    StatsScreen {
        height: 1fr;
        width: 1fr;
        padding: 1;
        overflow-y: auto;
    }
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        super().__init__()
        self._conn = conn

    def on_mount(self) -> None:
        self.update(self.render_text())

    def render_text(self) -> str:
        lines: list[str] = []

        # Dedup stats
        dedup = get_dedup_stats(self._conn)
        lines.append("Dedup Stats")
        lines.append("=" * 35)
        if dedup:
            for stage, count in sorted(dedup.items()):
                lines.append(f"  {stage}: {count} leads processed")
        else:
            lines.append("  No dedup records")
        lines.append("")

        # Aggregate counts
        all_leads = get_leads(self._conn)
        scored = [l for l in all_leads if l.score is not None]
        with_outreach = [l for l in all_leads if l.outreach_email]

        lines.append("Lead Counts")
        lines.append("=" * 35)
        lines.append(f"  Total leads: {len(all_leads)}")
        lines.append(f"  Scored:      {len(scored)}")
        lines.append(f"  With outreach: {len(with_outreach)}")
        lines.append("")

        # Per-metro breakdown
        metro_counts = Counter(l.metro for l in all_leads if l.metro)
        lines.append("Leads by Metro")
        lines.append("=" * 35)
        if metro_counts:
            for metro, count in metro_counts.most_common():
                lines.append(f"  {metro}: {count}")
        else:
            lines.append("  No metro data")
        lines.append("")

        # Per-category breakdown
        cat_counts = Counter(l.category for l in all_leads if l.category)
        lines.append("Leads by Category")
        lines.append("=" * 35)
        if cat_counts:
            for cat, count in cat_counts.most_common():
                lines.append(f"  {cat}: {count}")
        else:
            lines.append("  No category data")

        return "\n".join(lines)
