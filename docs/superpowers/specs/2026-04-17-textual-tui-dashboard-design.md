# Textual TUI Dashboard — Design Spec

## Goal

Add a terminal-based interactive dashboard for browsing leads, viewing run history, and checking pipeline stats — all without leaving the terminal. Phase 1 is read-only; Phase 2 (future) adds pipeline control.

## Launch

```bash
python -m src.pipeline tui
```

New Click command in `src/pipeline.py` that imports and runs the Textual app.

## Dependencies

- `textual` — added to `requirements.txt`

## Module Structure

```
src/tui/
  __init__.py
  app.py        — BizProspectorApp (Textual App subclass), keybindings, screen routing
  screens.py    — LeadsScreen, RunsScreen, StatsScreen (one class per tab)
  widgets.py    — FilterBar, LeadDetail, StatusBar (reusable components)
```

All data access goes through existing `src.db` functions. No new data layer.

## Screens

### Leads Screen (F1 — default)

Layout: top filter bar, left lead table, right detail panel.

**Filter bar (top):**
- Three `Input` widgets: Metro, Category, Min Score
- Apply button (or Enter in any input triggers apply)
- Queries `get_leads(conn, metro=, category=, min_score=)` on apply
- Empty filters are treated as "no filter" (passed as `None`)

**Lead table (left):**
- `DataTable` with columns: Business Name, Score, Metro, Category
- Sorted by score descending
- Scrollable with Up/Down keys
- Footer shows count: "N of M leads"
- Selecting a row updates the detail panel

**Detail panel (right):**
- Displays all enrichment data for the currently selected lead
- Sections:
  - **Header:** Business name, address, phone, website
  - **Score:** Overall score (0–100) + breakdown table showing each factor name and its contribution
  - **Website Audit:** has_crm, has_chat_widget, has_scheduling, has_ssl, is_mobile_responsive, page_speed_score, tech_stack list
  - **Reviews:** rating, review_count, ops_complaint_count, ops_complaint_samples, owner_response_rate
  - **Job Postings:** active_job_postings, manual_process_postings, manual_process_titles
  - **Employees:** employee_count, founded_year, manual_role_count, tech_role_count, employee_titles
  - **Contact:** contact_name, contact_email, contact_title, linkedin_url, company_linkedin_url
  - **Timestamps:** scraped_at, enriched_at, scored_at, contacted_at
- Read-only, no action buttons
- Scrollable if content overflows

### Runs Screen (F2)

Single `DataTable` showing `get_run_history(conn)` results.

Columns: Date, Vertical, Metro, Threshold, Scraped, Enriched, Qualified, Emailed, Duration, Re-enrich flag.

Sorted by most recent first. No interactivity beyond scrolling.

### Stats Screen (F3)

Vertical layout of labeled key-value pairs:

- **Dedup stats** from `get_dedup_stats(conn)`: processed count per stage (scrape, enrich, score, outreach)
- **Aggregate counts** from `get_leads(conn)`:
  - Total leads (all leads, no filter)
  - Scored leads (`scored_only=True`)
  - Leads with outreach email (fetch all leads, count where `outreach_email != ""` in Python — `get_leads` has no outreach filter)
- **Per-metro breakdown:** count of leads grouped by metro (query all leads, group in Python)
- **Per-category breakdown:** count of leads grouped by category (same approach)

## Navigation & Keybindings

| Key | Action |
|-----|--------|
| F1 | Switch to Leads screen |
| F2 | Switch to Runs screen |
| F3 | Switch to Stats screen |
| Up/Down | Navigate table rows |
| Tab | Move focus between filter inputs and table |
| Enter | Apply filters (when focus is on a filter input) |
| Q | Quit the app |

## Status Bar

Persistent footer across all screens. Shows:
- Last run timestamp (from most recent `get_run_history` entry)
- Total lead count
- Scored lead count

Refreshed on screen switch.

## Data Access

All reads go through `src.db`:
- `get_db()` — open connection (called once at app startup, stored on app instance)
- `get_leads(conn, ...)` — lead queries with filters
- `get_lead(conn, lead_id)` — single lead detail (used when table row selected)
- `get_run_history(conn)` — run table data
- `get_dedup_stats(conn)` — stage processing counts

No writes in Phase 1. The DB connection is opened read-only style (no WAL writes needed).

## CLI Integration

In `src/pipeline.py`, add:

```python
@cli.command()
def tui():
    """Launch interactive TUI dashboard."""
    from src.tui.app import BizProspectorApp
    BizProspectorApp().run()
```

Lazy import keeps `textual` optional — the rest of the CLI works without it installed. If `textual` is not installed, the import fails with a clear error message.

## Testing Strategy

- **Widget tests:** Use Textual's `app.run_test()` to simulate keypresses and assert widget content. Mock `src.db` functions to return fixture data.
- **Screen tests:** Verify that filter inputs produce correct `get_leads()` call args. Verify table populates from mock data. Verify detail panel updates on row selection.
- **Integration test:** Launch the full app with an in-memory SQLite DB seeded with test leads, verify basic navigation (F1/F2/F3 switching).

Tests go in `tests/tui/test_app.py`, `tests/tui/test_screens.py`, `tests/tui/test_widgets.py`.

## Phase 2 (Future — Not in This Spec)

- Trigger pipeline stages from within the TUI (scrape, enrich, score, outreach)
- Real-time output capture from running stages
- Progress indicators for long-running operations
- Possibly: lead selection + batch export

## Out of Scope

- Color theming / custom CSS beyond Textual defaults
- Mouse-only interactions (keyboard-first, mouse is a bonus from Textual)
- Web access or remote connections
- Editing lead data from the TUI
