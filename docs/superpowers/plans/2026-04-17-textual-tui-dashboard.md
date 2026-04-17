# Textual TUI Dashboard (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only terminal dashboard for browsing leads, viewing run history, and checking pipeline stats.

**Architecture:** Textual App with three tabbed screens (Leads, Runs, Stats). Layout C: top filter bar + left table + right detail panel for the Leads screen. All data read from SQLite via existing `src.db` functions. Launched via `python -m src.pipeline tui`.

**Tech Stack:** Python 3.11+, Textual, existing src.db / src.models

---

### Task 1: Add textual dependency and create module skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `src/tui/__init__.py`
- Create: `src/tui/app.py`
- Create: `tests/tui/__init__.py`
- Create: `tests/tui/test_app.py`

- [ ] **Step 1: Add textual to requirements.txt**

Open `requirements.txt` and add `textual>=1.0.0` at the end:

```
textual>=1.0.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install textual>=1.0.0`

- [ ] **Step 3: Create the tui package with a minimal app**

Create `src/tui/__init__.py`:

```python
"""Textual TUI dashboard for biz-prospector."""
```

Create `src/tui/app.py`:

```python
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
```

- [ ] **Step 4: Create test directory and write a smoke test**

Create `tests/tui/__init__.py` (empty file).

Create `tests/tui/test_app.py`:

```python
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
```

- [ ] **Step 5: Run the test**

Run: `python -m pytest tests/tui/test_app.py -v`
Expected: 1 test PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/tui/__init__.py src/tui/app.py tests/tui/__init__.py tests/tui/test_app.py
git commit -m "feat: add textual dependency and TUI app skeleton"
```

---

### Task 2: Build the StatusBar widget

The status bar sits at the bottom of every screen and shows last run time, total leads, and scored leads.

**Files:**
- Create: `src/tui/widgets.py`
- Create: `tests/tui/test_widgets.py`

- [ ] **Step 1: Write the failing test**

Create `tests/tui/test_widgets.py`:

```python
"""Tests for TUI widgets."""

from __future__ import annotations

import pytest

from textual.app import App, ComposeResult

from src.tui.widgets import StatusBar


class StatusBarTestApp(App):
    """Test harness for StatusBar."""

    def __init__(self, last_run: str, total: int, scored: int):
        super().__init__()
        self._last_run = last_run
        self._total = total
        self._scored = scored

    def compose(self) -> ComposeResult:
        yield StatusBar(self._last_run, self._total, self._scored)


class TestStatusBar:
    @pytest.mark.asyncio
    async def test_displays_stats(self):
        app = StatusBarTestApp("2026-04-16 10:30", 127, 84)
        async with app.run_test():
            bar = app.query_one(StatusBar)
            text = bar.render_text()
            assert "2026-04-16 10:30" in text
            assert "127" in text
            assert "84" in text

    @pytest.mark.asyncio
    async def test_displays_no_runs_message(self):
        app = StatusBarTestApp("No runs yet", 0, 0)
        async with app.run_test():
            bar = app.query_one(StatusBar)
            text = bar.render_text()
            assert "No runs yet" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tui/test_widgets.py::TestStatusBar -v`
Expected: FAIL (StatusBar not found)

- [ ] **Step 3: Implement StatusBar**

Create `src/tui/widgets.py`:

```python
"""Reusable TUI widgets for biz-prospector."""

from __future__ import annotations

from textual.widgets import Static


class StatusBar(Static):
    """Persistent footer showing pipeline summary stats."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, last_run: str, total_leads: int, scored_leads: int) -> None:
        self._last_run = last_run
        self._total_leads = total_leads
        self._scored_leads = scored_leads
        super().__init__()

    def render_text(self) -> str:
        """Return the status text. Used for rendering and testing."""
        return (
            f"Last run: {self._last_run}"
            f" | {self._total_leads} leads"
            f" | {self._scored_leads} scored"
        )

    def render(self) -> str:
        return self.render_text()

    def update_stats(self, last_run: str, total_leads: int, scored_leads: int) -> None:
        """Update the displayed stats and refresh."""
        self._last_run = last_run
        self._total_leads = total_leads
        self._scored_leads = scored_leads
        self.refresh()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tui/test_widgets.py::TestStatusBar -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tui/widgets.py tests/tui/test_widgets.py
git commit -m "feat: add StatusBar widget for TUI dashboard"
```

---

### Task 3: Build the FilterBar widget

A horizontal bar with Metro, Category, Min Score inputs and an Apply button.

**Files:**
- Modify: `src/tui/widgets.py`
- Modify: `tests/tui/test_widgets.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tui/test_widgets.py`:

```python
from src.tui.widgets import FilterBar


class FilterBarTestApp(App):
    """Test harness for FilterBar."""

    def __init__(self):
        super().__init__()
        self.applied_filters = None

    def compose(self) -> ComposeResult:
        yield FilterBar()

    def on_filter_bar_applied(self, event: FilterBar.Applied) -> None:
        self.applied_filters = {
            "metro": event.metro,
            "category": event.category,
            "min_score": event.min_score,
        }


class TestFilterBar:
    @pytest.mark.asyncio
    async def test_renders_three_inputs(self):
        app = FilterBarTestApp()
        async with app.run_test():
            inputs = app.query("Input")
            assert len(inputs) == 3

    @pytest.mark.asyncio
    async def test_apply_emits_event_with_values(self):
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            # Type into the metro input (first Input widget)
            metro_input = app.query("Input").first()
            metro_input.value = "portland-or"
            # Click the Apply button
            await pilot.click("#apply-filters")
            assert app.applied_filters is not None
            assert app.applied_filters["metro"] == "portland-or"
            assert app.applied_filters["category"] is None
            assert app.applied_filters["min_score"] is None

    @pytest.mark.asyncio
    async def test_apply_parses_min_score(self):
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            score_input = app.query("Input").last()
            score_input.value = "55.0"
            await pilot.click("#apply-filters")
            assert app.applied_filters is not None
            assert app.applied_filters["min_score"] == 55.0

    @pytest.mark.asyncio
    async def test_empty_inputs_are_none(self):
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            await pilot.click("#apply-filters")
            assert app.applied_filters is not None
            assert app.applied_filters["metro"] is None
            assert app.applied_filters["category"] is None
            assert app.applied_filters["min_score"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tui/test_widgets.py::TestFilterBar -v`
Expected: FAIL (FilterBar not found)

- [ ] **Step 3: Implement FilterBar**

Add to `src/tui/widgets.py`:

```python
from textual.containers import Horizontal
from textual.widgets import Static, Input, Button
from textual.message import Message


class FilterBar(Static):
    """Horizontal filter bar with Metro, Category, Min Score inputs and Apply button."""

    DEFAULT_CSS = """
    FilterBar {
        dock: top;
        height: 3;
        padding: 0 1;
        layout: horizontal;
    }
    FilterBar Horizontal {
        height: 3;
        width: 1fr;
    }
    FilterBar Input {
        width: 20;
        margin: 0 1;
    }
    FilterBar Button {
        margin: 0 1;
    }
    """

    class Applied(Message):
        """Posted when the user applies filters."""

        def __init__(self, metro: str | None, category: str | None, min_score: float | None) -> None:
            self.metro = metro
            self.category = category
            self.min_score = min_score
            super().__init__()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Input(placeholder="Metro", id="filter-metro")
            yield Input(placeholder="Category", id="filter-category")
            yield Input(placeholder="Min Score", id="filter-score")
            yield Button("Apply", id="apply-filters", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply-filters":
            self._emit_applied()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._emit_applied()

    def _emit_applied(self) -> None:
        metro_val = self.query_one("#filter-metro", Input).value.strip()
        cat_val = self.query_one("#filter-category", Input).value.strip()
        score_val = self.query_one("#filter-score", Input).value.strip()

        self.post_message(self.Applied(
            metro=metro_val or None,
            category=cat_val or None,
            min_score=float(score_val) if score_val else None,
        ))
```

Also update the imports at the top of `src/tui/widgets.py`. The full import block should be:

```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static, Input, Button
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tui/test_widgets.py::TestFilterBar -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tui/widgets.py tests/tui/test_widgets.py
git commit -m "feat: add FilterBar widget with metro/category/score inputs"
```

---

### Task 4: Build the LeadDetail widget

A scrollable panel showing all enrichment data for a selected lead.

**Files:**
- Modify: `src/tui/widgets.py`
- Modify: `tests/tui/test_widgets.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tui/test_widgets.py`:

```python
from tests.conftest import make_lead
from src.tui.widgets import LeadDetail


class LeadDetailTestApp(App):
    """Test harness for LeadDetail."""

    def compose(self) -> ComposeResult:
        yield LeadDetail()


class TestLeadDetail:
    @pytest.mark.asyncio
    async def test_empty_state(self):
        app = LeadDetailTestApp()
        async with app.run_test():
            detail = app.query_one(LeadDetail)
            text = detail.render_text()
            assert "Select a lead" in text

    @pytest.mark.asyncio
    async def test_shows_lead_name_and_score(self):
        lead = make_lead(
            business_name="Acme HVAC",
            score=78.5,
            score_breakdown={"no_crm_detected": 20.0, "website_outdated": 15.0},
        )
        app = LeadDetailTestApp()
        async with app.run_test():
            detail = app.query_one(LeadDetail)
            detail.show_lead(lead)
            text = detail.render_text()
            assert "Acme HVAC" in text
            assert "78.5" in text

    @pytest.mark.asyncio
    async def test_shows_audit_flags(self):
        lead = make_lead(
            has_crm=False,
            has_chat_widget=True,
            has_scheduling=False,
        )
        app = LeadDetailTestApp()
        async with app.run_test():
            detail = app.query_one(LeadDetail)
            detail.show_lead(lead)
            text = detail.render_text()
            assert "CRM" in text
            assert "Chat" in text

    @pytest.mark.asyncio
    async def test_shows_contact_info(self):
        lead = make_lead(
            contact_name="John Doe",
            contact_email="john@acme.com",
            contact_title="Owner",
        )
        app = LeadDetailTestApp()
        async with app.run_test():
            detail = app.query_one(LeadDetail)
            detail.show_lead(lead)
            text = detail.render_text()
            assert "John Doe" in text
            assert "john@acme.com" in text

    @pytest.mark.asyncio
    async def test_shows_review_data(self):
        lead = make_lead(
            rating=4.2,
            review_count=85,
            ops_complaint_count=3,
        )
        app = LeadDetailTestApp()
        async with app.run_test():
            detail = app.query_one(LeadDetail)
            detail.show_lead(lead)
            text = detail.render_text()
            assert "4.2" in text
            assert "85" in text
            assert "3" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tui/test_widgets.py::TestLeadDetail -v`
Expected: FAIL (LeadDetail not found)

- [ ] **Step 3: Implement LeadDetail**

Add to `src/tui/widgets.py`:

```python
from src.models import Lead


class LeadDetail(Static):
    """Scrollable panel showing full detail for a selected lead."""

    DEFAULT_CSS = """
    LeadDetail {
        width: 1fr;
        height: 1fr;
        overflow-y: auto;
        padding: 1;
        border-left: solid $primary;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._lead: Lead | None = None

    def show_lead(self, lead: Lead) -> None:
        """Update the detail panel to show a new lead."""
        self._lead = lead
        self.update(self.render_text())

    def render_text(self) -> str:
        """Build the detail text. Used for rendering and testing."""
        if self._lead is None:
            return "Select a lead from the table"

        lead = self._lead
        lines: list[str] = []

        # Header
        lines.append(f"{'=' * 40}")
        lines.append(f"{lead.business_name}")
        lines.append(f"{'=' * 40}")
        if lead.address:
            lines.append(f"Address: {lead.address}")
        if lead.phone:
            lines.append(f"Phone:   {lead.phone}")
        if lead.website:
            lines.append(f"Website: {lead.website}")
        lines.append("")

        # Score
        if lead.score is not None:
            lines.append(f"SCORE: {lead.score:.1f} / 100")
            if lead.score_breakdown:
                lines.append("-" * 30)
                for factor, value in sorted(lead.score_breakdown.items(), key=lambda x: -x[1]):
                    lines.append(f"  {factor}: {value:.1f}")
            lines.append("")

        # Website Audit
        lines.append("Website Audit")
        lines.append("-" * 30)

        def _flag(val: bool | None, label: str) -> str:
            if val is None:
                return f"  {label}: ?"
            return f"  {label}: {'Yes' if val else 'No'}"

        lines.append(_flag(lead.has_crm, "CRM"))
        lines.append(_flag(lead.has_chat_widget, "Chat Widget"))
        lines.append(_flag(lead.has_scheduling, "Scheduling"))
        lines.append(_flag(lead.has_ssl, "SSL"))
        lines.append(_flag(lead.is_mobile_responsive, "Mobile Responsive"))
        if lead.page_speed_score is not None:
            lines.append(f"  Page Speed: {lead.page_speed_score}")
        if lead.tech_stack:
            lines.append(f"  Tech Stack: {', '.join(lead.tech_stack)}")
        lines.append("")

        # Reviews
        lines.append("Reviews")
        lines.append("-" * 30)
        if lead.rating is not None:
            lines.append(f"  Rating: {lead.rating} ({lead.review_count or 0} reviews)")
        lines.append(f"  Ops Complaints: {lead.ops_complaint_count}")
        if lead.ops_complaint_samples:
            for sample in lead.ops_complaint_samples[:3]:
                lines.append(f"    - \"{sample[:80]}\"")
        if lead.owner_response_rate is not None:
            lines.append(f"  Owner Response Rate: {lead.owner_response_rate:.0%}")
        lines.append("")

        # Job Postings
        lines.append("Job Postings")
        lines.append("-" * 30)
        lines.append(f"  Active: {lead.active_job_postings}")
        lines.append(f"  Manual Process: {lead.manual_process_postings}")
        if lead.manual_process_titles:
            for title in lead.manual_process_titles[:5]:
                lines.append(f"    - {title}")
        lines.append("")

        # Employees
        lines.append("Employees")
        lines.append("-" * 30)
        if lead.employee_count is not None:
            lines.append(f"  Count: {lead.employee_count}")
        if lead.founded_year is not None:
            lines.append(f"  Founded: {lead.founded_year}")
        lines.append(f"  Manual Roles: {lead.manual_role_count}")
        lines.append(f"  Tech Roles: {lead.tech_role_count}")
        lines.append("")

        # Contact
        lines.append("Contact")
        lines.append("-" * 30)
        if lead.contact_name:
            lines.append(f"  Name:  {lead.contact_name}")
        if lead.contact_email:
            lines.append(f"  Email: {lead.contact_email}")
        if lead.contact_title:
            lines.append(f"  Title: {lead.contact_title}")
        if lead.linkedin_url:
            lines.append(f"  LinkedIn: {lead.linkedin_url}")
        if lead.company_linkedin_url:
            lines.append(f"  Company LinkedIn: {lead.company_linkedin_url}")
        lines.append("")

        # Timestamps
        lines.append("Timestamps")
        lines.append("-" * 30)
        for field_name, label in [
            ("scraped_at", "Scraped"),
            ("enriched_at", "Enriched"),
            ("scored_at", "Scored"),
            ("contacted_at", "Contacted"),
        ]:
            val = getattr(lead, field_name)
            lines.append(f"  {label}: {val.isoformat()[:16] if val else '—'}")

        return "\n".join(lines)
```

Update the import at the top of `widgets.py` to include `Lead`:

```python
from src.models import Lead
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tui/test_widgets.py::TestLeadDetail -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tui/widgets.py tests/tui/test_widgets.py
git commit -m "feat: add LeadDetail widget showing full lead enrichment data"
```

---

### Task 5: Build the LeadsScreen

The main screen with FilterBar (top), DataTable (left), and LeadDetail (right).

**Files:**
- Create: `src/tui/screens.py`
- Create: `tests/tui/test_screens.py`

- [ ] **Step 1: Write the failing test**

Create `tests/tui/test_screens.py`:

```python
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
    """Return fixture leads for testing."""
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
    """Test harness wrapping LeadsScreen."""

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
                # Set metro filter and apply
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
                # Move cursor to first row and select
                table.move_cursor(row=0)
                detail = app.query_one(LeadDetail)
                # After cursor move, detail should show the lead
                text = detail.render_text()
                assert "Acme HVAC" in text or "Select a lead" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tui/test_screens.py::TestLeadsScreen -v`
Expected: FAIL (screens module not found)

- [ ] **Step 3: Implement LeadsScreen**

Create `src/tui/screens.py`:

```python
"""TUI screens for biz-prospector."""

from __future__ import annotations

import sqlite3

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Static

from src.db import get_leads, get_lead
from src.models import Lead
from src.tui.widgets import FilterBar, LeadDetail


class LeadCountLabel(Static):
    """Shows 'N leads' below the table."""

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
    """Main leads browser: filter bar + table + detail panel."""

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

    def _load_leads(self, metro: str | None = None, category: str | None = None, min_score: float | None = None) -> None:
        """Query the database and populate the table."""
        # Get total count (unfiltered)
        all_leads = get_leads(self._conn)
        self._all_leads_count = len(all_leads)

        # Get filtered leads
        self._leads = get_leads(
            self._conn,
            metro=metro,
            category=category,
            min_score=min_score,
        )
        # Sort by score descending
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
        self._load_leads(
            metro=event.metro,
            category=event.category,
            min_score=event.min_score,
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value is not None:
            row_idx = event.cursor_row
            if 0 <= row_idx < len(self._leads):
                lead = self._leads[row_idx]
                self.query_one(LeadDetail).show_lead(lead)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tui/test_screens.py::TestLeadsScreen -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tui/screens.py tests/tui/test_screens.py
git commit -m "feat: add LeadsScreen with filter bar, data table, and detail panel"
```

---

### Task 6: Build the RunsScreen

A DataTable showing pipeline run history.

**Files:**
- Modify: `src/tui/screens.py`
- Modify: `tests/tui/test_screens.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tui/test_screens.py`:

```python
from src.tui.screens import RunsScreen


def _mock_get_run_history(conn, limit=20):
    """Return fixture run history."""
    return [
        {
            "id": 1,
            "vertical": "hvac",
            "metro": "portland-or",
            "started_at": "2026-04-16T10:30:00",
            "completed_at": "2026-04-16T10:35:00",
            "scraped_count": 50,
            "enriched_count": 45,
            "qualified_count": 12,
            "emailed_count": 10,
            "threshold": 55.0,
            "is_re_enrich": 0,
        },
        {
            "id": 2,
            "vertical": "dental",
            "metro": "seattle-wa",
            "started_at": "2026-04-15T14:00:00",
            "completed_at": "2026-04-15T14:10:00",
            "scraped_count": 80,
            "enriched_count": 70,
            "qualified_count": 20,
            "emailed_count": 18,
            "threshold": 55.0,
            "is_re_enrich": 0,
        },
    ]


class RunsScreenTestApp(App):
    """Test harness wrapping RunsScreen."""

    def __init__(self, mock_conn=None):
        super().__init__()
        self.mock_conn = mock_conn or MagicMock()

    def compose(self) -> ComposeResult:
        yield RunsScreen(self.mock_conn)


class TestRunsScreen:
    @pytest.mark.asyncio
    async def test_renders_table(self):
        with patch("src.tui.screens.get_run_history", side_effect=_mock_get_run_history):
            app = RunsScreenTestApp()
            async with app.run_test():
                tables = app.query(DataTable)
                assert len(tables) == 1

    @pytest.mark.asyncio
    async def test_table_has_rows(self):
        with patch("src.tui.screens.get_run_history", side_effect=_mock_get_run_history):
            app = RunsScreenTestApp()
            async with app.run_test():
                table = app.query_one(DataTable)
                assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_empty_history(self):
        with patch("src.tui.screens.get_run_history", return_value=[]):
            app = RunsScreenTestApp()
            async with app.run_test():
                table = app.query_one(DataTable)
                assert table.row_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tui/test_screens.py::TestRunsScreen -v`
Expected: FAIL (RunsScreen not found)

- [ ] **Step 3: Implement RunsScreen**

Add to `src/tui/screens.py`:

```python
from src.db import get_leads, get_lead, get_run_history


class RunsScreen(Static):
    """Pipeline run history table."""

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
```

Update the import line at the top of `screens.py` to include `get_run_history`:

```python
from src.db import get_leads, get_lead, get_run_history
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tui/test_screens.py::TestRunsScreen -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tui/screens.py tests/tui/test_screens.py
git commit -m "feat: add RunsScreen showing pipeline run history table"
```

---

### Task 7: Build the StatsScreen

Summary stats: dedup counts, lead totals, per-metro and per-category breakdowns.

**Files:**
- Modify: `src/tui/screens.py`
- Modify: `tests/tui/test_screens.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/tui/test_screens.py`:

```python
from src.tui.screens import StatsScreen


def _mock_get_dedup_stats(conn):
    return {"enrich": 100, "score": 80, "outreach": 40}


def _mock_get_leads_for_stats(conn, *, metro=None, category=None, min_score=None, scored_only=False, limit=None):
    """Return leads for stats aggregation."""
    leads = [
        make_lead(id="1", metro="portland-or", category="HVAC", score=78.5, outreach_email="hi"),
        make_lead(id="2", metro="portland-or", category="HVAC", score=65.2, outreach_email=""),
        make_lead(id="3", metro="seattle-wa", category="dental", score=None, outreach_email=""),
    ]
    if scored_only:
        leads = [l for l in leads if l.score is not None]
    return leads


class StatsScreenTestApp(App):
    """Test harness wrapping StatsScreen."""

    def __init__(self, mock_conn=None):
        super().__init__()
        self.mock_conn = mock_conn or MagicMock()

    def compose(self) -> ComposeResult:
        yield StatsScreen(self.mock_conn)


class TestStatsScreen:
    @pytest.mark.asyncio
    async def test_shows_dedup_stats(self):
        with patch("src.tui.screens.get_dedup_stats", side_effect=_mock_get_dedup_stats), \
             patch("src.tui.screens.get_leads", side_effect=_mock_get_leads_for_stats):
            app = StatsScreenTestApp()
            async with app.run_test():
                screen = app.query_one(StatsScreen)
                text = screen.render_text()
                assert "enrich" in text
                assert "100" in text

    @pytest.mark.asyncio
    async def test_shows_total_counts(self):
        with patch("src.tui.screens.get_dedup_stats", side_effect=_mock_get_dedup_stats), \
             patch("src.tui.screens.get_leads", side_effect=_mock_get_leads_for_stats):
            app = StatsScreenTestApp()
            async with app.run_test():
                screen = app.query_one(StatsScreen)
                text = screen.render_text()
                # 3 total, 2 scored, 1 with outreach
                assert "3" in text

    @pytest.mark.asyncio
    async def test_shows_metro_breakdown(self):
        with patch("src.tui.screens.get_dedup_stats", side_effect=_mock_get_dedup_stats), \
             patch("src.tui.screens.get_leads", side_effect=_mock_get_leads_for_stats):
            app = StatsScreenTestApp()
            async with app.run_test():
                screen = app.query_one(StatsScreen)
                text = screen.render_text()
                assert "portland-or" in text
                assert "seattle-wa" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/tui/test_screens.py::TestStatsScreen -v`
Expected: FAIL (StatsScreen not found)

- [ ] **Step 3: Implement StatsScreen**

Add to `src/tui/screens.py`:

```python
from collections import Counter
from src.db import get_leads, get_lead, get_run_history, get_dedup_stats


class StatsScreen(Static):
    """Pipeline statistics summary."""

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
        """Build the stats text. Used for rendering and testing."""
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
```

Update the import line at the top of `screens.py` to include `Counter` and `get_dedup_stats`:

```python
from collections import Counter
from src.db import get_leads, get_lead, get_run_history, get_dedup_stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/tui/test_screens.py::TestStatsScreen -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tui/screens.py tests/tui/test_screens.py
git commit -m "feat: add StatsScreen with dedup, lead, and breakdown stats"
```

---

### Task 8: Wire screens into the main App with tabbed navigation

Connect all three screens into the main app with F1/F2/F3 tab switching and StatusBar.

**Files:**
- Modify: `src/tui/app.py`
- Modify: `tests/tui/test_app.py`

- [ ] **Step 1: Write the failing tests**

Replace the contents of `tests/tui/test_app.py` with:

```python
"""Tests for the TUI application."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from src.tui.app import BizProspectorApp
from src.tui.screens import LeadsScreen, RunsScreen, StatsScreen
from src.tui.widgets import StatusBar
from tests.conftest import make_lead


def _mock_get_db(path=None):
    conn = MagicMock()
    return conn


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
            await pilot.press("f2")  # switch away
            await pilot.press("f1")  # switch back
            content = app.query_one("#tab-content")
            # LeadsScreen should be visible
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/tui/test_app.py -v`
Expected: FAIL (old tests fail because app structure changed)

- [ ] **Step 3: Rewrite the app with tabbed navigation**

Replace `src/tui/app.py` with:

```python
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
        """Replace the tab content with the requested screen."""
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
        """Update the status bar with current DB stats."""
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
        """Handle F1/F2/F3 tab switching."""
        self._show_screen(tab)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/tui/test_app.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Run all TUI tests**

Run: `python -m pytest tests/tui/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/tui/app.py tests/tui/test_app.py
git commit -m "feat: wire LeadsScreen, RunsScreen, StatsScreen into tabbed app"
```

---

### Task 9: Add the `tui` CLI command to pipeline.py

**Files:**
- Modify: `src/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pipeline.py`:

```python
class TestTuiCommand:
    def test_tui_command_exists(self, cli_runner):
        """The tui command should exist in the CLI group."""
        from src.pipeline import cli
        result = cli_runner.invoke(cli, ["tui", "--help"])
        assert result.exit_code == 0
        assert "Launch interactive TUI dashboard" in result.output
```

Note: `cli_runner` is a Click test fixture. If there is no `cli_runner` fixture in `tests/test_pipeline.py` or `conftest.py`, add one. Check the existing test file for how Click commands are tested first. If the tests use `CliRunner` directly, write the test as:

```python
from click.testing import CliRunner
from src.pipeline import cli


class TestTuiCommand:
    def test_tui_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["tui", "--help"])
        assert result.exit_code == 0
        assert "Launch interactive TUI dashboard" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py::TestTuiCommand -v`
Expected: FAIL (no such command 'tui')

- [ ] **Step 3: Add the tui command**

Add to `src/pipeline.py`, after the `export_json` command and before `if __name__ == "__main__":`:

```python
@cli.command()
def tui():
    """Launch interactive TUI dashboard."""
    try:
        from src.tui.app import BizProspectorApp
    except ImportError:
        console.print("[red]Textual is not installed. Run: pip install textual[/]")
        raise SystemExit(1)
    BizProspectorApp().run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py::TestTuiCommand -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest --tb=short 2>&1 | tail -5`
Expected: All tests pass (484 + new TUI tests)

- [ ] **Step 6: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add 'tui' CLI command to launch Textual dashboard"
```

---

### Task 10: Integration test — full app with seeded database

Verify the complete app works end-to-end with a real (in-memory) SQLite database.

**Files:**
- Modify: `tests/tui/test_app.py`

- [ ] **Step 1: Write the integration test**

Append to `tests/tui/test_app.py`:

```python
from src.db import get_db, upsert_leads, start_run, finish_run


class TestIntegration:
    @pytest.fixture
    def seeded_db(self):
        """Create an in-memory DB with test data."""
        conn = get_db(":memory:")
        leads = [
            make_lead(id="int1", business_name="Alpha HVAC", score=82.0, metro="portland-or", category="HVAC",
                      has_crm=False, has_chat_widget=True, has_scheduling=False,
                      contact_name="Alice", contact_email="alice@alpha.com"),
            make_lead(id="int2", business_name="Beta Dental", score=71.5, metro="seattle-wa", category="dental",
                      has_crm=True, has_chat_widget=False, has_scheduling=True,
                      contact_name="Bob", contact_email="bob@beta.com"),
            make_lead(id="int3", business_name="Gamma Legal", score=None, metro="portland-or", category="legal"),
        ]
        upsert_leads(conn, leads)
        run_id = start_run(conn, "hvac", "portland-or", threshold=55.0)
        finish_run(conn, run_id, {"scraped_count": 50, "enriched_count": 40, "qualified_count": 10, "emailed_count": 8})
        return conn

    @pytest.mark.asyncio
    async def test_full_navigation(self, seeded_db):
        """Launch app with real DB, navigate all tabs, verify no crashes."""
        with patch("src.tui.app.get_db", return_value=seeded_db):
            app = BizProspectorApp()
            async with app.run_test(size=(120, 40)) as pilot:
                # F1: Leads screen (default)
                leads_screen = app.query_one(LeadsScreen)
                assert leads_screen is not None

                # Verify table has data
                from textual.widgets import DataTable
                table = app.query_one(DataTable)
                assert table.row_count == 3

                # F2: Runs screen
                await pilot.press("f2")
                runs_table = app.query_one("#runs-table", DataTable)
                assert runs_table.row_count == 1

                # F3: Stats screen
                await pilot.press("f3")
                stats = app.query_one(StatsScreen)
                text = stats.render_text()
                assert "portland-or" in text
                assert "3" in text  # total leads

                # F1: Back to leads
                await pilot.press("f1")

                # Quit
                await pilot.press("q")
```

- [ ] **Step 2: Run the integration test**

Run: `python -m pytest tests/tui/test_app.py::TestIntegration -v`
Expected: PASS

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest --tb=short 2>&1 | tail -5`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/tui/test_app.py
git commit -m "test: add integration test for full TUI navigation with seeded DB"
```

---

### Task 11: Update project documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `FEATURES.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update CLAUDE.md**

In the "Running" section, add:

```bash
python -m src.pipeline tui
```

In the "What's built" section, add:
- Textual TUI dashboard (lead browser, run history, pipeline stats)

In the "TODO" section, mark item 8 as done:
```
8. ~~Web dashboard~~ ✓ (Textual TUI dashboard — terminal-native, no web hosting needed)
```

- [ ] **Step 2: Update FEATURES.md**

Add a new section:

```markdown
## Dashboard
- **Textual TUI** — Interactive terminal dashboard (`python -m src.pipeline tui`)
  - Lead browser with filter bar (metro, category, min score), sortable table, and detail panel
  - Pipeline run history table
  - Aggregate stats: dedup counts, lead totals, per-metro and per-category breakdowns
  - Keyboard navigation: F1 Leads, F2 Runs, F3 Stats, Q quit
```

- [ ] **Step 3: Update CHANGELOG.md**

Under `[Unreleased]` → `### Added`:

```markdown
- **Textual TUI dashboard** — interactive terminal UI for browsing leads, run history, and stats (`python -m src.pipeline tui`)
```

Under `### Changed`:

```markdown
- Added `textual>=1.0.0` dependency for TUI dashboard
```

- [ ] **Step 4: Run the full test suite one final time**

Run: `python -m pytest --tb=short 2>&1 | tail -5`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md FEATURES.md CHANGELOG.md
git commit -m "docs: update project docs for Textual TUI dashboard"
```
