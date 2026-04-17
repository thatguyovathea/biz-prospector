"""Reusable TUI widgets for the biz-prospector dashboard."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static, Input, Button

from src.models import Lead


class StatusBar(Static):
    """Bottom status bar showing pipeline run stats."""

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
        return (
            f"Last run: {self._last_run}"
            f" | {self._total_leads} leads"
            f" | {self._scored_leads} scored"
        )

    def render(self) -> str:
        return self.render_text()

    def update_stats(self, last_run: str, total_leads: int, scored_leads: int) -> None:
        self._last_run = last_run
        self._total_leads = total_leads
        self._scored_leads = scored_leads
        self.refresh()


class FilterBar(Static):
    """Top filter bar with metro/category/min-score inputs and an Apply button."""

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

        def __init__(
            self,
            metro: str | None,
            category: str | None,
            min_score: float | None,
        ) -> None:
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
        self.post_message(
            self.Applied(
                metro=metro_val or None,
                category=cat_val or None,
                min_score=float(score_val) if score_val else None,
            )
        )


def _bool_display(value: bool | None) -> str:
    """Return 'Yes', 'No', or '?' for a tri-state boolean."""
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "?"


class LeadDetail(Static):
    """Detail panel showing full enrichment data for a selected lead."""

    DEFAULT_CSS = """
    LeadDetail {
        padding: 1 2;
        overflow-y: auto;
    }
    """

    def __init__(self) -> None:
        self._lead: Lead | None = None
        super().__init__()

    def show_lead(self, lead: Lead) -> None:
        """Update the widget to display a new lead."""
        self._lead = lead
        self.refresh()

    def render_text(self) -> str:
        if self._lead is None:
            return "Select a lead from the table"
        return self._build_detail(self._lead)

    def render(self) -> str:
        return self.render_text()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_detail(self, lead: Lead) -> str:
        lines: list[str] = []

        # Header
        lines.append(f"=== {lead.business_name} ===")
        if lead.address:
            lines.append(f"Address:  {lead.address}")
        if lead.phone:
            lines.append(f"Phone:    {lead.phone}")
        if lead.website:
            lines.append(f"Website:  {lead.website}")

        # Score
        lines.append("")
        lines.append("--- Score ---")
        if lead.score is not None:
            lines.append(f"Overall:  {lead.score:.1f}")
        else:
            lines.append("Overall:  —")
        if lead.score_breakdown:
            sorted_breakdown = sorted(
                lead.score_breakdown.items(), key=lambda kv: kv[1], reverse=True
            )
            for factor, value in sorted_breakdown:
                lines.append(f"  {factor}: {value:.1f}")

        # Website Audit
        lines.append("")
        lines.append("--- Website Audit ---")
        lines.append(f"CRM:              {_bool_display(lead.has_crm)}")
        lines.append(f"Chat Widget:      {_bool_display(lead.has_chat_widget)}")
        lines.append(f"Scheduling:       {_bool_display(lead.has_scheduling)}")
        lines.append(f"SSL:              {_bool_display(lead.has_ssl)}")
        lines.append(f"Mobile Responsive:{_bool_display(lead.is_mobile_responsive)}")
        if lead.page_speed_score is not None:
            lines.append(f"Page Speed:       {lead.page_speed_score}")
        else:
            lines.append("Page Speed:       ?")
        if lead.tech_stack:
            lines.append(f"Tech Stack:       {', '.join(lead.tech_stack)}")
        else:
            lines.append("Tech Stack:       —")

        # Reviews
        lines.append("")
        lines.append("--- Reviews ---")
        if lead.rating is not None:
            lines.append(f"Rating:           {lead.rating:.1f}")
        else:
            lines.append("Rating:           —")
        if lead.review_count is not None:
            lines.append(f"Review Count:     {lead.review_count}")
        else:
            lines.append("Review Count:     —")
        lines.append(f"Ops Complaints:   {lead.ops_complaint_count}")
        if lead.owner_response_rate is not None:
            lines.append(f"Owner Response:   {lead.owner_response_rate:.0%}")
        else:
            lines.append("Owner Response:   —")
        if lead.ops_complaint_samples:
            lines.append("Complaint Samples:")
            for sample in lead.ops_complaint_samples[:3]:
                lines.append(f"  - {sample}")

        # Job Postings
        lines.append("")
        lines.append("--- Job Postings ---")
        lines.append(f"Active Postings:  {lead.active_job_postings}")
        lines.append(f"Manual Process:   {lead.manual_process_postings}")
        if lead.manual_process_titles:
            titles = lead.manual_process_titles[:5]
            lines.append(f"Titles:           {', '.join(titles)}")

        # Employees
        lines.append("")
        lines.append("--- Employees ---")
        if lead.employee_count is not None:
            lines.append(f"Employee Count:   {lead.employee_count}")
        else:
            lines.append("Employee Count:   —")
        if lead.founded_year is not None:
            lines.append(f"Founded:          {lead.founded_year}")
        else:
            lines.append("Founded:          —")
        lines.append(f"Manual Roles:     {lead.manual_role_count}")
        lines.append(f"Tech Roles:       {lead.tech_role_count}")

        # Contact
        lines.append("")
        lines.append("--- Contact ---")
        lines.append(f"Name:             {lead.contact_name or '—'}")
        lines.append(f"Email:            {lead.contact_email or '—'}")
        lines.append(f"Title:            {lead.contact_title or '—'}")
        lines.append(f"LinkedIn:         {lead.linkedin_url or '—'}")
        lines.append(f"Company LinkedIn: {lead.company_linkedin_url or '—'}")

        # Timestamps
        lines.append("")
        lines.append("--- Timestamps ---")
        lines.append(f"Scraped:   {lead.scraped_at or '—'}")
        lines.append(f"Enriched:  {lead.enriched_at or '—'}")
        lines.append(f"Scored:    {lead.scored_at or '—'}")
        lines.append(f"Contacted: {lead.contacted_at or '—'}")

        return "\n".join(lines)
