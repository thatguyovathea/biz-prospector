# SQLite Backend Migration — Design Spec

**Date:** 2026-04-16
**Status:** Approved
**Replaces:** JSON file storage in `data/` subdirectories

## Summary

Replace all JSON file I/O and dedup tracking with a single SQLite database at `data/biz-prospector.db`. Add pipeline run tracking. Provide CLI commands for JSON import/export.

## Decisions

- **SQLite via stdlib `sqlite3`** — zero new dependencies
- **Full replacement** — no dual-mode JSON fallback
- **JSON import command** — migrate historical data from existing files
- **`Lead` model unchanged** — all changes are in the storage/pipeline layer

## Database Schema

### `leads` table

All columns map 1:1 to `Lead` model fields. List/dict fields stored as JSON text.

```sql
CREATE TABLE leads (
    id TEXT PRIMARY KEY,
    business_name TEXT NOT NULL,
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    website TEXT DEFAULT '',
    category TEXT DEFAULT '',
    metro TEXT DEFAULT '',
    source TEXT DEFAULT 'google_maps',

    -- Google Maps
    rating REAL,
    review_count INTEGER,
    place_id TEXT DEFAULT '',

    -- Enrichment
    tech_stack TEXT DEFAULT '[]',
    has_crm INTEGER,
    has_chat_widget INTEGER,
    has_scheduling INTEGER,
    has_ssl INTEGER,
    is_mobile_responsive INTEGER,
    page_speed_score INTEGER,

    -- Reviews
    reviews_analyzed INTEGER DEFAULT 0,
    ops_complaint_count INTEGER DEFAULT 0,
    ops_complaint_samples TEXT DEFAULT '[]',
    owner_response_rate REAL,

    -- Job postings
    active_job_postings INTEGER DEFAULT 0,
    manual_process_postings INTEGER DEFAULT 0,
    manual_process_titles TEXT DEFAULT '[]',

    -- Contact
    contact_name TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    contact_title TEXT DEFAULT '',

    -- LinkedIn
    linkedin_url TEXT DEFAULT '',
    company_linkedin_url TEXT DEFAULT '',
    employee_count INTEGER,
    founded_year INTEGER,
    employee_titles TEXT DEFAULT '[]',
    manual_role_count INTEGER DEFAULT 0,
    tech_role_count INTEGER DEFAULT 0,

    -- Scoring
    score REAL,
    score_breakdown TEXT DEFAULT '{}',

    -- Outreach
    outreach_email TEXT DEFAULT '',
    followups TEXT DEFAULT '[]',

    -- Timestamps
    scraped_at TEXT,
    enriched_at TEXT,
    scored_at TEXT,
    contacted_at TEXT,

    -- Run tracking
    last_run_id INTEGER REFERENCES pipeline_runs(id)
);

CREATE INDEX idx_leads_metro ON leads(metro);
CREATE INDEX idx_leads_score ON leads(score);
CREATE INDEX idx_leads_category ON leads(category);
CREATE INDEX idx_leads_place_id ON leads(place_id);
```

### `dedup` table

Replaces `data/.dedup/*_processed.json` files.

```sql
CREATE TABLE dedup (
    lead_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (lead_id, stage)
);
```

### `pipeline_runs` table

Tracks each pipeline execution for stats and history.

```sql
CREATE TABLE pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical TEXT NOT NULL,
    metro TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    scraped_count INTEGER DEFAULT 0,
    enriched_count INTEGER DEFAULT 0,
    qualified_count INTEGER DEFAULT 0,
    emailed_count INTEGER DEFAULT 0,
    threshold REAL,
    is_re_enrich INTEGER DEFAULT 0
);
```

## New Module: `src/db.py`

Thin wrapper around `sqlite3`. WAL mode enabled for concurrent read performance.

### Public API

```python
get_db(path: str | None = None) -> sqlite3.Connection
    # Returns connection. Creates DB + tables on first call.
    # Default path: data/biz-prospector.db
    # Enables WAL mode and foreign keys.

upsert_leads(conn, leads: list[Lead], run_id: int | None = None) -> int
    # INSERT OR REPLACE into leads table. Sets last_run_id if provided.
    # Handles JSON serialization of list/dict fields.
    # Returns number of rows affected.

get_leads(conn, metro=None, category=None, min_score=None, scored_only=False, limit=None) -> list[Lead]
    # Flexible query builder with optional filters.
    # Handles JSON deserialization back to Lead objects.

get_lead(conn, lead_id: str) -> Lead | None
    # Single lead lookup by ID.

mark_processed(conn, leads: list[Lead], stage: str) -> None
    # Bulk INSERT OR IGNORE into dedup table.

filter_new_leads(conn, leads: list[Lead], stage: str) -> tuple[list[Lead], int]
    # Same interface as current dedup.filter_new_leads.
    # Returns (new_leads, skipped_count).

start_run(conn, vertical: str, metro: str, threshold: float) -> int
    # Insert pipeline_runs row. Returns run ID.

finish_run(conn, run_id: int, counts: dict) -> None
    # Update completed_at and count columns.

get_run_history(conn, limit: int = 20) -> list[dict]
    # Recent pipeline runs ordered by started_at desc.

get_dedup_stats(conn) -> dict[str, int]
    # Count of processed leads per stage.
```

### Lead ↔ Row Conversion

Internal helpers `_lead_to_row(lead)` and `_row_to_lead(row)` handle:
- `list[str]` fields → `json.dumps()` / `json.loads()`
- `dict` fields → `json.dumps()` / `json.loads()`
- `Optional[bool]` fields → `None`/`0`/`1` integers
- `LeadSource` enum → string value
- `datetime` fields → ISO format strings

## Pipeline Changes

### `pipeline.py` modifications

**Removed:**
- `_load_leads(path)` — replaced by `db.get_leads()`
- `_save_json(leads, subdir, filename)` — replaced by `db.upsert_leads()`

**Changed commands:**

`scrape` — writes leads to DB via `upsert_leads()` instead of JSON file.

`enrich` — accepts `--metro` and `--category` filters instead of `--input` file path. Reads from DB, writes enriched data back.

`score` — reads enriched leads from DB, writes scores back. Accepts same filters.

`outreach` — reads scored leads from DB (above threshold), writes outreach back.

`run` — creates a `pipeline_runs` record via `start_run()`. Updates counts at each stage via `finish_run()`. All intermediate data stays in DB.

`stats` — queries `pipeline_runs` table and `dedup` table instead of counting JSON files. Shows run history table.

`re-enrich` — queries DB for leads with stale `enriched_at` instead of scanning JSON files.

### Individual stage commands

For `scrape`, `enrich`, `score`, `outreach` run individually:
- Each reads/writes from the shared DB
- `enrich --metro portland-or` enriches all un-enriched leads in that metro
- `score --metro portland-or --vertical hvac` scores all enriched leads matching those filters
- `outreach --min-score 55` generates emails for all scored leads above threshold without existing outreach

### New commands

`import-json --input <path>` — parse a JSON file of leads, upsert into DB. Detects which stage the leads are from (raw/enriched/scored/outreach) based on which fields are populated.

`export-json --output <path> [--metro X] [--min-score N] [--category Y]` — dump matching leads as JSON array for portability or external tooling.

## `dedup.py` changes

The module becomes a thin wrapper around `db.mark_processed()` and `db.filter_new_leads()`. Same public API, backed by SQLite instead of JSON files. Existing callers don't change.

## What stays the same

- `src/models.py` — `Lead`, `PipelineConfig`, `VerticalConfig` unchanged
- `src/scrapers/*` — all scrapers return `list[Lead]`, no storage awareness
- `src/enrichment/*` — all enrichment functions take/return `Lead` objects
- `src/scoring/score.py` — takes `list[Lead]`, returns `list[Lead]`
- `src/outreach/generate.py` — takes `list[Lead]`, returns `list[Lead]`
- `src/outreach/delivery.py` — takes `list[Lead]`, no change
- `src/reporting/html_report.py` — takes `list[Lead]`, no change
- `src/notifications/email_summary.py` — takes `list[Lead]`, no change
- `config/settings.yaml` — no schema changes needed

## Testing Strategy

- Unit tests for `src/db.py` using in-memory SQLite (`:memory:`)
- Test Lead ↔ row round-trip for all field types
- Test upsert idempotency (same lead twice = one row)
- Test filter/query combinations
- Test pipeline_runs lifecycle
- Integration tests for import-json with sample data files
- Existing pipeline tests updated to use DB instead of JSON fixtures

## Migration Path

1. Build `src/db.py` with full test coverage
2. Update `dedup.py` to use DB backend
3. Update `pipeline.py` commands one at a time
4. Add `import-json` and `export-json` commands
5. Remove JSON file I/O code from pipeline
6. Update CLAUDE.md and README
