# SQLite Backend Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all JSON file I/O with a SQLite database, add pipeline run tracking, and provide import/export CLI commands.

**Architecture:** A new `src/db.py` module wraps Python's stdlib `sqlite3`. All pipeline stages read/write through `db.py` instead of JSON files. The `Lead` Pydantic model is unchanged — `db.py` handles serialization of list/dict fields to JSON text columns. Dedup tracking moves from JSON files to a `dedup` table.

**Tech Stack:** Python stdlib `sqlite3`, existing Pydantic models, Click CLI

**Spec:** `docs/superpowers/specs/2026-04-16-sqlite-backend-design.md`

---

### Task 1: Core database module — schema and connection

**Files:**
- Create: `src/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for `get_db` and schema creation**

```python
# tests/test_db.py
"""Tests for SQLite database module."""

import sqlite3
from pathlib import Path

import pytest

from src.db import get_db


class TestGetDb:
    def test_creates_database_file(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = get_db(str(db_path))
        assert db_path.exists()
        conn.close()

    def test_creates_leads_table(self, tmp_path):
        conn = get_db(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_dedup_table(self, tmp_path):
        conn = get_db(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dedup'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_pipeline_runs_table(self, tmp_path):
        conn = get_db(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_enables_wal_mode(self, tmp_path):
        conn = get_db(str(tmp_path / "test.db"))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_idempotent_on_existing_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn1 = get_db(db_path)
        conn1.execute("INSERT INTO leads (id, business_name) VALUES ('x', 'Test')")
        conn1.commit()
        conn1.close()

        conn2 = get_db(db_path)
        row = conn2.execute("SELECT business_name FROM leads WHERE id='x'").fetchone()
        assert row[0] == "Test"
        conn2.close()

    def test_in_memory_db(self):
        conn = get_db(":memory:")
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
        )
        assert cursor.fetchone() is not None
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_db.py -v`
Expected: `ModuleNotFoundError: No module named 'src.db'`

- [ ] **Step 3: Implement `get_db` with full schema**

```python
# src/db.py
"""SQLite storage backend for biz-prospector.

Replaces JSON file I/O with a single SQLite database.
All list/dict Lead fields are stored as JSON text columns.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
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

CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    business_name TEXT NOT NULL,
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    website TEXT DEFAULT '',
    category TEXT DEFAULT '',
    metro TEXT DEFAULT '',
    source TEXT DEFAULT 'google_maps',

    rating REAL,
    review_count INTEGER,
    place_id TEXT DEFAULT '',

    tech_stack TEXT DEFAULT '[]',
    has_crm INTEGER,
    has_chat_widget INTEGER,
    has_scheduling INTEGER,
    has_ssl INTEGER,
    is_mobile_responsive INTEGER,
    page_speed_score INTEGER,

    reviews_analyzed INTEGER DEFAULT 0,
    ops_complaint_count INTEGER DEFAULT 0,
    ops_complaint_samples TEXT DEFAULT '[]',
    owner_response_rate REAL,

    active_job_postings INTEGER DEFAULT 0,
    manual_process_postings INTEGER DEFAULT 0,
    manual_process_titles TEXT DEFAULT '[]',

    contact_name TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    contact_title TEXT DEFAULT '',

    linkedin_url TEXT DEFAULT '',
    company_linkedin_url TEXT DEFAULT '',
    employee_count INTEGER,
    founded_year INTEGER,
    employee_titles TEXT DEFAULT '[]',
    manual_role_count INTEGER DEFAULT 0,
    tech_role_count INTEGER DEFAULT 0,

    score REAL,
    score_breakdown TEXT DEFAULT '{}',

    outreach_email TEXT DEFAULT '',
    followups TEXT DEFAULT '[]',

    scraped_at TEXT,
    enriched_at TEXT,
    scored_at TEXT,
    contacted_at TEXT,

    last_run_id INTEGER REFERENCES pipeline_runs(id)
);

CREATE TABLE IF NOT EXISTS dedup (
    lead_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (lead_id, stage)
);

CREATE INDEX IF NOT EXISTS idx_leads_metro ON leads(metro);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score);
CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category);
CREATE INDEX IF NOT EXISTS idx_leads_place_id ON leads(place_id);
"""

DEFAULT_DB_PATH = "data/biz-prospector.db"


def get_db(path: str | None = None) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure schema exists.

    Args:
        path: Database file path. Defaults to data/biz-prospector.db.
              Use ":memory:" for in-memory databases (testing).

    Returns:
        sqlite3.Connection with WAL mode and foreign keys enabled.
    """
    if path is None:
        path = DEFAULT_DB_PATH
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    return conn
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_db.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add src/db.py tests/test_db.py
git commit -m "feat: add SQLite database module with schema creation"
```

---

### Task 2: Lead ↔ row serialization and upsert

**Files:**
- Modify: `src/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for `_lead_to_row`, `_row_to_lead`, and `upsert_leads`**

Add to `tests/test_db.py`:

```python
import json
from datetime import datetime, timezone

from src.db import get_db, upsert_leads, get_lead
from src.models import Lead, LeadSource
from tests.conftest import make_lead


class TestLeadRoundTrip:
    def test_basic_round_trip(self):
        conn = get_db(":memory:")
        lead = make_lead(id="rt1", business_name="Round Trip Biz")
        upsert_leads(conn, [lead])
        result = get_lead(conn, "rt1")
        assert result is not None
        assert result.business_name == "Round Trip Biz"
        assert result.id == "rt1"
        conn.close()

    def test_list_fields_round_trip(self):
        conn = get_db(":memory:")
        lead = make_lead(
            id="rt2",
            tech_stack=["wordpress", "google_analytics"],
            ops_complaint_samples=["slow response", "never called back"],
            manual_process_titles=["data entry clerk"],
            employee_titles=["Office Manager", "Dispatcher"],
            followups=["Follow up 1", "Follow up 2"],
        )
        upsert_leads(conn, [lead])
        result = get_lead(conn, "rt2")
        assert result.tech_stack == ["wordpress", "google_analytics"]
        assert result.ops_complaint_samples == ["slow response", "never called back"]
        assert result.manual_process_titles == ["data entry clerk"]
        assert result.employee_titles == ["Office Manager", "Dispatcher"]
        assert result.followups == ["Follow up 1", "Follow up 2"]
        conn.close()

    def test_dict_field_round_trip(self):
        conn = get_db(":memory:")
        lead = make_lead(
            id="rt3",
            score_breakdown={"website_outdated": 15.0, "no_crm_detected": 10.0},
        )
        upsert_leads(conn, [lead])
        result = get_lead(conn, "rt3")
        assert result.score_breakdown == {"website_outdated": 15.0, "no_crm_detected": 10.0}
        conn.close()

    def test_boolean_fields_round_trip(self):
        conn = get_db(":memory:")
        lead = make_lead(id="rt4", has_crm=True, has_chat_widget=False, has_scheduling=None)
        upsert_leads(conn, [lead])
        result = get_lead(conn, "rt4")
        assert result.has_crm is True
        assert result.has_chat_widget is False
        assert result.has_scheduling is None
        conn.close()

    def test_datetime_fields_round_trip(self):
        conn = get_db(":memory:")
        now = datetime.now(timezone.utc)
        lead = make_lead(id="rt5", scraped_at=now, enriched_at=now)
        upsert_leads(conn, [lead])
        result = get_lead(conn, "rt5")
        assert result.scraped_at is not None
        assert result.enriched_at is not None
        conn.close()

    def test_enum_field_round_trip(self):
        conn = get_db(":memory:")
        lead = make_lead(id="rt6", source=LeadSource.LINKEDIN)
        upsert_leads(conn, [lead])
        result = get_lead(conn, "rt6")
        assert result.source == LeadSource.LINKEDIN
        conn.close()

    def test_none_lead_returns_none(self):
        conn = get_db(":memory:")
        result = get_lead(conn, "nonexistent")
        assert result is None
        conn.close()


class TestUpsertLeads:
    def test_upsert_count(self):
        conn = get_db(":memory:")
        leads = [make_lead(id="u1"), make_lead(id="u2"), make_lead(id="u3")]
        count = upsert_leads(conn, leads)
        assert count == 3
        conn.close()

    def test_upsert_is_idempotent(self):
        conn = get_db(":memory:")
        lead = make_lead(id="u4", business_name="Original")
        upsert_leads(conn, [lead])
        lead.business_name = "Updated"
        upsert_leads(conn, [lead])
        result = get_lead(conn, "u4")
        assert result.business_name == "Updated"
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        assert total == 1
        conn.close()

    def test_upsert_sets_run_id(self):
        conn = get_db(":memory:")
        conn.execute(
            "INSERT INTO pipeline_runs (vertical, metro, started_at) VALUES ('hvac', 'portland-or', '2026-01-01')"
        )
        run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        upsert_leads(conn, [make_lead(id="u5")], run_id=run_id)
        row = conn.execute("SELECT last_run_id FROM leads WHERE id='u5'").fetchone()
        assert row[0] == run_id
        conn.close()

    def test_upsert_empty_list(self):
        conn = get_db(":memory:")
        count = upsert_leads(conn, [])
        assert count == 0
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_db.py::TestLeadRoundTrip tests/test_db.py::TestUpsertLeads -v`
Expected: `ImportError: cannot import name 'upsert_leads' from 'src.db'`

- [ ] **Step 3: Implement `_lead_to_row`, `_row_to_lead`, `upsert_leads`, and `get_lead`**

Add to `src/db.py`:

```python
import json
from src.models import Lead, LeadSource

# Fields stored as JSON text in SQLite
_JSON_LIST_FIELDS = {
    "tech_stack", "ops_complaint_samples", "manual_process_titles",
    "employee_titles", "followups",
}
_JSON_DICT_FIELDS = {"score_breakdown"}
_BOOL_FIELDS = {
    "has_crm", "has_chat_widget", "has_scheduling",
    "has_ssl", "is_mobile_responsive",
}
_DATETIME_FIELDS = {"scraped_at", "enriched_at", "scored_at", "contacted_at"}

# All Lead field names in a stable order for SQL generation
_LEAD_FIELDS = [
    "id", "business_name", "address", "phone", "website", "category",
    "metro", "source", "rating", "review_count", "place_id",
    "tech_stack", "has_crm", "has_chat_widget", "has_scheduling",
    "has_ssl", "is_mobile_responsive", "page_speed_score",
    "reviews_analyzed", "ops_complaint_count", "ops_complaint_samples",
    "owner_response_rate", "active_job_postings", "manual_process_postings",
    "manual_process_titles", "contact_name", "contact_email", "contact_title",
    "linkedin_url", "company_linkedin_url", "employee_count", "founded_year",
    "employee_titles", "manual_role_count", "tech_role_count",
    "score", "score_breakdown", "outreach_email", "followups",
    "scraped_at", "enriched_at", "scored_at", "contacted_at",
]

_INSERT_SQL = (
    f"INSERT OR REPLACE INTO leads ({', '.join(_LEAD_FIELDS)}, last_run_id) "
    f"VALUES ({', '.join('?' for _ in _LEAD_FIELDS)}, ?)"
)


def _lead_to_row(lead: Lead, run_id: int | None = None) -> tuple:
    """Convert a Lead to a tuple of SQLite-compatible values."""
    values = []
    for field in _LEAD_FIELDS:
        val = getattr(lead, field)
        if field in _JSON_LIST_FIELDS or field in _JSON_DICT_FIELDS:
            val = json.dumps(val)
        elif field in _BOOL_FIELDS:
            val = None if val is None else int(val)
        elif field == "source":
            val = val.value if isinstance(val, LeadSource) else val
        elif field in _DATETIME_FIELDS:
            val = val.isoformat() if val is not None else None
        values.append(val)
    values.append(run_id)
    return tuple(values)


def _row_to_lead(row: sqlite3.Row) -> Lead:
    """Convert a SQLite Row to a Lead object."""
    data = {}
    for field in _LEAD_FIELDS:
        val = row[field]
        if field in _JSON_LIST_FIELDS or field in _JSON_DICT_FIELDS:
            data[field] = json.loads(val) if val else ([] if field in _JSON_LIST_FIELDS else {})
        elif field in _BOOL_FIELDS:
            data[field] = None if val is None else bool(val)
        else:
            data[field] = val
    return Lead(**data)


def upsert_leads(
    conn: sqlite3.Connection,
    leads: list[Lead],
    run_id: int | None = None,
) -> int:
    """Insert or replace leads in the database.

    Returns the number of rows affected.
    """
    if not leads:
        return 0
    rows = [_lead_to_row(lead, run_id) for lead in leads]
    conn.executemany(_INSERT_SQL, rows)
    conn.commit()
    return len(rows)


def get_lead(conn: sqlite3.Connection, lead_id: str) -> Lead | None:
    """Fetch a single lead by ID. Returns None if not found."""
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return None
    return _row_to_lead(row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_db.py -v`
Expected: All tests PASS (7 from Task 1 + 11 new = 18 total)

- [ ] **Step 5: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add src/db.py tests/test_db.py
git commit -m "feat: add Lead upsert and round-trip serialization"
```

---

### Task 3: Query, dedup, and pipeline run functions

**Files:**
- Modify: `src/db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for `get_leads`, dedup functions, and pipeline run functions**

Add to `tests/test_db.py`:

```python
from src.db import (
    get_db, upsert_leads, get_lead, get_leads,
    mark_processed, filter_new_leads, get_dedup_stats,
    start_run, finish_run, get_run_history,
)


class TestGetLeads:
    def test_get_all(self):
        conn = get_db(":memory:")
        upsert_leads(conn, [
            make_lead(id="g1", metro="portland-or", score=70.0, category="HVAC"),
            make_lead(id="g2", metro="seattle-wa", score=40.0, category="dental"),
            make_lead(id="g3", metro="portland-or", score=80.0, category="HVAC"),
        ])
        leads = get_leads(conn)
        assert len(leads) == 3
        conn.close()

    def test_filter_by_metro(self):
        conn = get_db(":memory:")
        upsert_leads(conn, [
            make_lead(id="g1", metro="portland-or"),
            make_lead(id="g2", metro="seattle-wa"),
        ])
        leads = get_leads(conn, metro="portland-or")
        assert len(leads) == 1
        assert leads[0].id == "g1"
        conn.close()

    def test_filter_by_category(self):
        conn = get_db(":memory:")
        upsert_leads(conn, [
            make_lead(id="g1", category="HVAC"),
            make_lead(id="g2", category="dental"),
        ])
        leads = get_leads(conn, category="HVAC")
        assert len(leads) == 1
        assert leads[0].id == "g1"
        conn.close()

    def test_filter_by_min_score(self):
        conn = get_db(":memory:")
        upsert_leads(conn, [
            make_lead(id="g1", score=70.0),
            make_lead(id="g2", score=40.0),
            make_lead(id="g3", score=None),
        ])
        leads = get_leads(conn, min_score=55.0)
        assert len(leads) == 1
        assert leads[0].id == "g1"
        conn.close()

    def test_filter_scored_only(self):
        conn = get_db(":memory:")
        upsert_leads(conn, [
            make_lead(id="g1", score=70.0),
            make_lead(id="g2", score=None),
        ])
        leads = get_leads(conn, scored_only=True)
        assert len(leads) == 1
        assert leads[0].id == "g1"
        conn.close()

    def test_limit(self):
        conn = get_db(":memory:")
        upsert_leads(conn, [make_lead(id=f"g{i}") for i in range(10)])
        leads = get_leads(conn, limit=3)
        assert len(leads) == 3
        conn.close()

    def test_combined_filters(self):
        conn = get_db(":memory:")
        upsert_leads(conn, [
            make_lead(id="g1", metro="portland-or", category="HVAC", score=70.0),
            make_lead(id="g2", metro="portland-or", category="HVAC", score=40.0),
            make_lead(id="g3", metro="portland-or", category="dental", score=80.0),
            make_lead(id="g4", metro="seattle-wa", category="HVAC", score=90.0),
        ])
        leads = get_leads(conn, metro="portland-or", category="HVAC", min_score=55.0)
        assert len(leads) == 1
        assert leads[0].id == "g1"
        conn.close()

    def test_empty_result(self):
        conn = get_db(":memory:")
        leads = get_leads(conn, metro="nonexistent")
        assert leads == []
        conn.close()


class TestDedup:
    def test_mark_and_filter(self):
        conn = get_db(":memory:")
        leads = [make_lead(id="d1"), make_lead(id="d2")]
        mark_processed(conn, leads, "enrich")
        new, skipped = filter_new_leads(
            conn, [make_lead(id="d1"), make_lead(id="d3")], "enrich"
        )
        assert len(new) == 1
        assert new[0].id == "d3"
        assert skipped == 1
        conn.close()

    def test_all_new_on_empty_db(self):
        conn = get_db(":memory:")
        leads = [make_lead(id="d1"), make_lead(id="d2")]
        new, skipped = filter_new_leads(conn, leads, "enrich")
        assert len(new) == 2
        assert skipped == 0
        conn.close()

    def test_separate_stages(self):
        conn = get_db(":memory:")
        mark_processed(conn, [make_lead(id="d1")], "enrich")
        new, skipped = filter_new_leads(conn, [make_lead(id="d1")], "score")
        assert len(new) == 1
        assert skipped == 0
        conn.close()

    def test_empty_list(self):
        conn = get_db(":memory:")
        new, skipped = filter_new_leads(conn, [], "enrich")
        assert new == []
        assert skipped == 0
        conn.close()

    def test_dedup_stats(self):
        conn = get_db(":memory:")
        mark_processed(conn, [make_lead(id="d1"), make_lead(id="d2")], "enrich")
        mark_processed(conn, [make_lead(id="d1")], "score")
        stats = get_dedup_stats(conn)
        assert stats["enrich"] == 2
        assert stats["score"] == 1
        conn.close()

    def test_dedup_stats_empty(self):
        conn = get_db(":memory:")
        stats = get_dedup_stats(conn)
        assert stats == {}
        conn.close()


class TestPipelineRuns:
    def test_start_and_finish_run(self):
        conn = get_db(":memory:")
        run_id = start_run(conn, "hvac", "portland-or", 55.0)
        assert run_id >= 1
        finish_run(conn, run_id, {
            "scraped_count": 100,
            "enriched_count": 80,
            "qualified_count": 30,
            "emailed_count": 25,
        })
        row = conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        assert row["scraped_count"] == 100
        assert row["qualified_count"] == 30
        assert row["completed_at"] is not None
        conn.close()

    def test_run_history_order(self):
        conn = get_db(":memory:")
        start_run(conn, "hvac", "portland-or", 55.0)
        start_run(conn, "dental", "seattle-wa", 60.0)
        history = get_run_history(conn)
        assert len(history) == 2
        assert history[0]["vertical"] == "dental"  # most recent first
        conn.close()

    def test_run_history_limit(self):
        conn = get_db(":memory:")
        for i in range(5):
            start_run(conn, f"v{i}", "metro", 55.0)
        history = get_run_history(conn, limit=3)
        assert len(history) == 3
        conn.close()

    def test_run_history_empty(self):
        conn = get_db(":memory:")
        history = get_run_history(conn)
        assert history == []
        conn.close()

    def test_re_enrich_flag(self):
        conn = get_db(":memory:")
        run_id = start_run(conn, "all", "all", 55.0, is_re_enrich=True)
        row = conn.execute("SELECT is_re_enrich FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        assert row[0] == 1
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_db.py::TestGetLeads tests/test_db.py::TestDedup tests/test_db.py::TestPipelineRuns -v`
Expected: `ImportError: cannot import name 'get_leads' from 'src.db'`

- [ ] **Step 3: Implement `get_leads`, dedup, and pipeline run functions**

Add to `src/db.py`:

```python
from datetime import datetime, timezone


def get_leads(
    conn: sqlite3.Connection,
    metro: str | None = None,
    category: str | None = None,
    min_score: float | None = None,
    scored_only: bool = False,
    limit: int | None = None,
) -> list[Lead]:
    """Query leads with optional filters.

    Args:
        metro: Filter by metro area.
        category: Filter by business category.
        min_score: Minimum score threshold.
        scored_only: Only return leads with a non-null score.
        limit: Maximum number of leads to return.
    """
    query = "SELECT * FROM leads WHERE 1=1"
    params: list = []

    if metro is not None:
        query += " AND metro = ?"
        params.append(metro)
    if category is not None:
        query += " AND category = ?"
        params.append(category)
    if min_score is not None:
        query += " AND score >= ?"
        params.append(min_score)
    if scored_only:
        query += " AND score IS NOT NULL"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [_row_to_lead(row) for row in rows]


def mark_processed(
    conn: sqlite3.Connection,
    leads: list[Lead],
    stage: str,
) -> None:
    """Mark leads as processed for a pipeline stage."""
    if not leads:
        return
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR IGNORE INTO dedup (lead_id, stage, processed_at) VALUES (?, ?, ?)",
        [(lead.id, stage, now) for lead in leads],
    )
    conn.commit()


def filter_new_leads(
    conn: sqlite3.Connection,
    leads: list[Lead],
    stage: str,
) -> tuple[list[Lead], int]:
    """Filter out leads already processed in a given stage.

    Returns:
        Tuple of (new_leads, skipped_count).
    """
    if not leads:
        return [], 0
    ids = [lead.id for lead in leads]
    placeholders = ", ".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT lead_id FROM dedup WHERE stage = ? AND lead_id IN ({placeholders})",
        [stage] + ids,
    ).fetchall()
    processed_ids = {row[0] for row in rows}
    new = [lead for lead in leads if lead.id not in processed_ids]
    skipped = len(leads) - len(new)
    return new, skipped


def get_dedup_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Get count of processed leads per stage."""
    rows = conn.execute(
        "SELECT stage, COUNT(*) as cnt FROM dedup GROUP BY stage"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def start_run(
    conn: sqlite3.Connection,
    vertical: str,
    metro: str,
    threshold: float,
    is_re_enrich: bool = False,
) -> int:
    """Create a new pipeline run record. Returns the run ID."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO pipeline_runs (vertical, metro, started_at, threshold, is_re_enrich) "
        "VALUES (?, ?, ?, ?, ?)",
        (vertical, metro, now, threshold, int(is_re_enrich)),
    )
    conn.commit()
    return cursor.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, counts: dict) -> None:
    """Update a pipeline run with completion data."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE pipeline_runs SET completed_at = ?, scraped_count = ?, "
        "enriched_count = ?, qualified_count = ?, emailed_count = ? "
        "WHERE id = ?",
        (
            now,
            counts.get("scraped_count", 0),
            counts.get("enriched_count", 0),
            counts.get("qualified_count", 0),
            counts.get("emailed_count", 0),
            run_id,
        ),
    )
    conn.commit()


def get_run_history(
    conn: sqlite3.Connection,
    limit: int = 20,
) -> list[dict]:
    """Get recent pipeline runs, newest first."""
    rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_stale_leads(
    conn: sqlite3.Connection,
    cutoff: datetime,
) -> list[Lead]:
    """Get scored leads with enriched_at before cutoff (or NULL)."""
    cutoff_iso = cutoff.isoformat()
    rows = conn.execute(
        "SELECT * FROM leads WHERE score IS NOT NULL "
        "AND (enriched_at IS NULL OR enriched_at < ?)",
        (cutoff_iso,),
    ).fetchall()
    return [_row_to_lead(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_db.py -v`
Expected: All tests PASS (18 from Tasks 1-2 + 19 new = 37 total)

- [ ] **Step 5: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add src/db.py tests/test_db.py
git commit -m "feat: add lead queries, dedup, and pipeline run tracking"
```

---

### Task 4: Update `dedup.py` to use SQLite backend

**Files:**
- Modify: `src/dedup.py`
- Modify: `tests/test_dedup.py`

- [ ] **Step 1: Rewrite `tests/test_dedup.py` to use SQLite**

Replace the contents of `tests/test_dedup.py` with:

```python
"""Tests for deduplication logic (SQLite-backed)."""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.dedup import filter_new_leads, mark_processed, reset_stage, get_stats
from src.db import get_db
from tests.conftest import make_lead


@pytest.fixture
def db_conn():
    """In-memory SQLite connection for tests."""
    conn = get_db(":memory:")
    yield conn
    conn.close()


class TestFilterNewLeads:
    def test_all_new_on_first_run(self, db_conn):
        leads = [make_lead(id="lead1"), make_lead(id="lead2"), make_lead(id="lead3")]
        with patch("src.dedup._get_conn", return_value=db_conn):
            new, skipped = filter_new_leads(leads, "enrich")
        assert len(new) == 3
        assert skipped == 0

    def test_filters_processed_leads(self, db_conn):
        from src.db import mark_processed as db_mark
        db_mark(db_conn, [make_lead(id="lead1"), make_lead(id="lead2")], "enrich")
        leads = [make_lead(id="lead1"), make_lead(id="lead2"), make_lead(id="lead3")]
        with patch("src.dedup._get_conn", return_value=db_conn):
            new, skipped = filter_new_leads(leads, "enrich")
        assert len(new) == 1
        assert new[0].id == "lead3"
        assert skipped == 2

    def test_empty_leads_list(self, db_conn):
        with patch("src.dedup._get_conn", return_value=db_conn):
            new, skipped = filter_new_leads([], "enrich")
        assert new == []
        assert skipped == 0


class TestMarkProcessed:
    def test_writes_lead_ids(self, db_conn):
        leads = [make_lead(id="lead1"), make_lead(id="lead2")]
        with patch("src.dedup._get_conn", return_value=db_conn):
            mark_processed(leads, "enrich")
        rows = db_conn.execute("SELECT * FROM dedup WHERE stage='enrich'").fetchall()
        ids = {row["lead_id"] for row in rows}
        assert ids == {"lead1", "lead2"}
        # Timestamps must be valid ISO format
        for row in rows:
            datetime.fromisoformat(row["processed_at"])

    def test_appends_to_existing(self, db_conn):
        from src.db import mark_processed as db_mark
        db_mark(db_conn, [make_lead(id="existing_lead")], "enrich")
        with patch("src.dedup._get_conn", return_value=db_conn):
            mark_processed([make_lead(id="new_lead")], "enrich")
        rows = db_conn.execute("SELECT * FROM dedup WHERE stage='enrich'").fetchall()
        ids = {row["lead_id"] for row in rows}
        assert ids == {"existing_lead", "new_lead"}


class TestResetStage:
    def test_deletes_dedup_records(self, db_conn):
        from src.db import mark_processed as db_mark
        db_mark(db_conn, [make_lead(id="lead1")], "enrich")
        with patch("src.dedup._get_conn", return_value=db_conn):
            reset_stage("enrich")
        rows = db_conn.execute("SELECT * FROM dedup WHERE stage='enrich'").fetchall()
        assert len(rows) == 0

    def test_no_error_if_empty(self, db_conn):
        with patch("src.dedup._get_conn", return_value=db_conn):
            reset_stage("enrich")


class TestGetStats:
    def test_counts_per_stage(self, db_conn):
        from src.db import mark_processed as db_mark
        db_mark(db_conn, [make_lead(id="l1"), make_lead(id="l2")], "enrich")
        db_mark(db_conn, [make_lead(id="l1")], "score")
        with patch("src.dedup._get_conn", return_value=db_conn):
            stats = get_stats()
        assert stats["enrich"] == 2
        assert stats["score"] == 1

    def test_empty_when_no_data(self, db_conn):
        with patch("src.dedup._get_conn", return_value=db_conn):
            stats = get_stats()
        assert stats == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_dedup.py -v`
Expected: Failures because `src.dedup` still uses JSON files and has no `_get_conn`

- [ ] **Step 3: Rewrite `src/dedup.py` to use SQLite**

Replace `src/dedup.py` with:

```python
"""Deduplication across pipeline runs.

Tracks which leads have been processed to avoid duplicate
enrichment, scoring, and outreach across multiple runs.
Backed by the SQLite database.
"""

from __future__ import annotations

from rich.console import Console

from src.db import get_db, filter_new_leads as db_filter, mark_processed as db_mark, get_dedup_stats
from src.models import Lead

console = Console()


def _get_conn():
    """Get the shared database connection."""
    return get_db()


def filter_new_leads(
    leads: list[Lead],
    stage: str,
) -> tuple[list[Lead], int]:
    """Filter out leads already processed in a given stage.

    Returns:
        Tuple of (new_leads, skipped_count)
    """
    conn = _get_conn()
    new, skipped = db_filter(conn, leads, stage)

    if skipped > 0:
        console.print(
            f"  [dim]Dedup: {skipped} already processed for {stage}, "
            f"{len(new)} new[/]"
        )

    return new, skipped


def mark_processed(
    leads: list[Lead],
    stage: str,
):
    """Mark leads as processed for a stage."""
    conn = _get_conn()
    db_mark(conn, leads, stage)


def reset_stage(stage: str):
    """Clear all dedup tracking for a stage."""
    conn = _get_conn()
    conn.execute("DELETE FROM dedup WHERE stage = ?", (stage,))
    conn.commit()
    console.print(f"[yellow]Reset dedup tracking for {stage}[/]")


def get_stats() -> dict[str, int]:
    """Get count of processed leads per stage."""
    conn = _get_conn()
    return get_dedup_stats(conn)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_dedup.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add src/dedup.py tests/test_dedup.py
git commit -m "refactor: switch dedup module from JSON files to SQLite"
```

---

### Task 5: Update `pipeline.py` — replace JSON I/O with database calls

**Files:**
- Modify: `src/pipeline.py`
- Modify: `tests/test_pipeline.py`

This is the largest task. It replaces `_load_leads` / `_save_json` with `db.upsert_leads` / `db.get_leads`, adds run tracking, and changes individual stage commands to use DB filters instead of `--input` file paths.

- [ ] **Step 1: Rewrite `tests/test_pipeline.py`**

Replace `tests/test_pipeline.py` with tests that use the SQLite backend. The key changes:
- Replace `leads_json_file` fixture with `db_conn` fixture that pre-populates leads in an in-memory DB
- Replace `patch("src.pipeline.DATA_DIR", ...)` with `patch("src.pipeline._get_conn", ...)`
- `scrape` command tests verify leads are in DB after scrape
- `enrich` / `score` / `outreach` commands use `--metro` filter instead of `--input`
- `run` command tests verify a `pipeline_runs` record is created
- `stats` command tests check `pipeline_runs` and dedup tables

```python
"""Tests for the pipeline CLI orchestrator."""

import json
from io import StringIO
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner
from rich.console import Console

from src.pipeline import cli, _print_top_leads
from src.models import Lead
from src.db import get_db, upsert_leads, get_lead
from tests.conftest import make_lead


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def db_conn():
    """In-memory SQLite DB for tests."""
    conn = get_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def db_with_leads(db_conn):
    """DB pre-populated with two sample leads."""
    leads = [
        make_lead(id="l1", business_name="Lead One", score=70.0, has_crm=False,
                  metro="portland-or", category="HVAC"),
        make_lead(id="l2", business_name="Lead Two", score=40.0, has_crm=True,
                  metro="portland-or", category="HVAC"),
    ]
    upsert_leads(db_conn, leads)
    return db_conn


@pytest.fixture
def sample_settings():
    return {
        "apis": {
            "serpapi_key": "fake-serpapi",
            "apify_token": "fake-apify",
            "outscraper_key": "fake-outscraper",
            "apollo_key": "fake-apollo",
            "hunter_key": "fake-hunter",
            "anthropic_key": "fake-anthropic",
            "instantly_key": "fake-instantly",
            "builtwith_key": "fake-builtwith",
        },
        "pipeline": {
            "batch_size": 100,
            "score_threshold": 55,
            "daily_send_limit": 50,
        },
        "scoring": {
            "weights": {},
            "manual_process_keywords": ["data entry"],
            "ops_complaint_keywords": ["never called back"],
        },
        "outreach": {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "followup_count": 2,
            "followup_interval_days": 3,
        },
    }


class TestPrintTopLeads:
    def test_prints_without_error(self):
        leads = [
            make_lead(score=80.0, has_crm=False, has_chat_widget=True, has_scheduling=None),
            make_lead(score=None, has_crm=None),
        ]
        buf = StringIO()
        c = Console(file=buf, highlight=False)
        import src.pipeline as _pl
        original_console = _pl.console
        _pl.console = c
        try:
            result = _print_top_leads(leads, n=5)
        finally:
            _pl.console = original_console
        output = buf.getvalue()
        assert "80.0" in output
        assert result is None


class TestScrapeCommand:
    def test_scrape_cli(self, runner, db_conn, sample_settings):
        mock_leads = [make_lead(id="s1")]
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["scrape", "--vertical", "hvac", "--metro", "portland-or"])
        assert result.exit_code == 0
        assert get_lead(db_conn, "s1") is not None


class TestEnrichCommand:
    def test_enrich_cli(self, runner, db_with_leads, sample_settings):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.audit_website") as mock_audit, \
             patch("src.pipeline.enrich_lead_with_audit"), \
             patch("src.pipeline.fetch_reviews_outscraper", return_value=[]), \
             patch("src.pipeline.search_jobs_serpapi", return_value=[]), \
             patch("src.pipeline._get_conn", return_value=db_with_leads):
            mock_audit.return_value = MagicMock()
            result = runner.invoke(cli, ["enrich", "--metro", "portland-or"])
        assert result.exit_code == 0
        assert "Enriching" in result.output

    def test_enrich_handles_review_exception(self, runner, sample_settings):
        conn = get_db(":memory:")
        upsert_leads(conn, [make_lead(id="l1", place_id="place_abc", website="")])
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.fetch_reviews_outscraper", side_effect=Exception("API down")), \
             patch("src.pipeline.search_jobs_serpapi", return_value=[]), \
             patch("src.pipeline._get_conn", return_value=conn):
            result = runner.invoke(cli, ["enrich", "--metro", "portland-or"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()
        conn.close()

    def test_enrich_handles_job_search_exception(self, runner, sample_settings):
        conn = get_db(":memory:")
        upsert_leads(conn, [make_lead(id="l1", place_id="", website="")])
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.search_jobs_serpapi", side_effect=Exception("SerpAPI down")), \
             patch("src.pipeline._get_conn", return_value=conn):
            result = runner.invoke(cli, ["enrich", "--metro", "portland-or"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()
        conn.close()


class TestScoreCommand:
    def test_score_cli(self, runner, db_with_leads, sample_settings):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline._get_conn", return_value=db_with_leads):
            result = runner.invoke(cli, ["score", "--metro", "portland-or"])
        assert result.exit_code == 0
        assert "above threshold" in result.output

    def test_score_with_threshold(self, runner, db_with_leads, sample_settings):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline._get_conn", return_value=db_with_leads):
            result = runner.invoke(cli, ["score", "--metro", "portland-or", "--threshold", "80"])
        assert result.exit_code == 0
        assert "above threshold" in result.output


class TestOutreachCommand:
    def test_outreach_cli(self, runner, db_with_leads, sample_settings):
        with patch("src.pipeline.generate_batch_outreach", side_effect=lambda leads, **kw: leads), \
             patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline._get_conn", return_value=db_with_leads):
            result = runner.invoke(cli, ["outreach", "--min-score", "55"])
        assert result.exit_code == 0


class TestReportCommand:
    def test_report_cli(self, runner, db_with_leads, tmp_path):
        with patch("src.pipeline.save_report", return_value=tmp_path / "report.html"), \
             patch("src.pipeline._get_conn", return_value=db_with_leads):
            result = runner.invoke(cli, [
                "report", "--metro", "portland-or",
                "--vertical", "hvac",
            ])
        assert result.exit_code == 0
        assert "Report saved" in result.output

    def test_report_no_vertical(self, runner, db_with_leads, tmp_path):
        with patch("src.pipeline.save_report", return_value=tmp_path / "report.html"), \
             patch("src.pipeline._get_conn", return_value=db_with_leads):
            result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0
        assert "Report saved" in result.output


class TestStatsCommand:
    def test_stats_with_data(self, runner, db_conn):
        from src.db import mark_processed as db_mark, start_run
        db_mark(db_conn, [make_lead(id="l1")], "enrich")
        start_run(db_conn, "hvac", "portland-or", 55.0)
        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "enrich" in result.output or "hvac" in result.output

    def test_stats_empty(self, runner, db_conn):
        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "No" in result.output


class TestRunCommand:
    def test_full_run(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="r1", score=70.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.filter_new_leads", return_value=(mock_leads, 0)), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline.generate_batch_outreach", return_value=mock_leads), \
             patch("src.pipeline.save_report", return_value="/tmp/report.html"), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--count", "5", "--skip-dedup",
            ])
        assert result.exit_code == 0
        assert "Pipeline Complete" in result.output

    def test_run_no_leads_after_dedup(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="r1")]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.filter_new_leads", return_value=([], 1)), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
            ])
        assert result.exit_code == 0
        assert "No new leads" in result.output

    def test_run_no_qualified_after_scoring(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="r1", score=10.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or", "--skip-dedup",
            ])
        assert result.exit_code == 0
        assert "No leads above threshold" in result.output

    def test_run_with_push_instantly(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="r1", score=70.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline.generate_batch_outreach", return_value=mock_leads), \
             patch("src.pipeline.push_to_instantly", return_value={
                 "campaign_id": "camp_123", "leads_added": 1, "status": "launched"
             }), \
             patch("src.pipeline.save_report", return_value="/tmp/report.html"), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--skip-dedup", "--push-instantly",
            ])
        assert result.exit_code == 0
        assert "camp_123" in result.output

    def test_run_with_dedup_skipping(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="r1", score=70.0), make_lead(id="r2", score=60.0)]
        filtered = [mock_leads[0]]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.filter_new_leads", return_value=(filtered, 1)), \
             patch("src.pipeline.run_async_enrichment", return_value=filtered), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=filtered), \
             patch("src.pipeline.generate_batch_outreach", return_value=filtered), \
             patch("src.pipeline.save_report", return_value="/tmp/report.html"), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
            ])
        assert result.exit_code == 0
        assert "Skipped 1" in result.output


class TestRunNotify:
    def test_run_with_notify_sends_email(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="n1", score=70.0)]
        sample_settings["schedule"] = {
            "summary_email": {
                "enabled": True, "to": "test@test.com",
                "smtp_host": "smtp.test.com", "smtp_port": 587,
                "smtp_user": "u", "smtp_password": "p",
            }
        }

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline.generate_batch_outreach", return_value=mock_leads), \
             patch("src.pipeline.save_report", return_value="/tmp/report.html"), \
             patch("src.pipeline.send_run_summary") as mock_send, \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--skip-dedup", "--notify",
            ])
        assert result.exit_code == 0
        mock_send.assert_called_once()

    def test_run_without_notify_skips_email(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="n1", score=70.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline.generate_batch_outreach", return_value=mock_leads), \
             patch("src.pipeline.save_report", return_value="/tmp/report.html"), \
             patch("src.pipeline.send_run_summary") as mock_send, \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--skip-dedup",
            ])
        assert result.exit_code == 0
        mock_send.assert_not_called()


class TestReEnrichCommand:
    def test_re_enriches_stale_leads(self, runner, sample_settings):
        from datetime import datetime, timezone, timedelta
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        conn = get_db(":memory:")
        upsert_leads(conn, [make_lead(id="stale1", score=60.0, enriched_at=old_date)])

        sample_settings["schedule"] = {"re_enrich": {"max_age_days": 30}}
        mock_enriched = [make_lead(id="stale1", score=65.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_enriched), \
             patch("src.pipeline.score_leads", return_value=mock_enriched), \
             patch("src.pipeline.send_run_summary"), \
             patch("src.pipeline._get_conn", return_value=conn):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "Re-enriching" in result.output
        conn.close()

    def test_skips_fresh_leads(self, runner, sample_settings):
        from datetime import datetime, timezone
        fresh_date = datetime.now(timezone.utc).isoformat()
        conn = get_db(":memory:")
        upsert_leads(conn, [make_lead(id="fresh1", score=60.0, enriched_at=fresh_date)])

        sample_settings["schedule"] = {"re_enrich": {"max_age_days": 30}}

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline._get_conn", return_value=conn):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "No stale leads" in result.output
        conn.close()

    def test_re_enrich_with_notify(self, runner, sample_settings):
        from datetime import datetime, timezone, timedelta
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        conn = get_db(":memory:")
        upsert_leads(conn, [make_lead(id="s1", score=60.0, enriched_at=old_date)])

        sample_settings["schedule"] = {
            "re_enrich": {"max_age_days": 30},
            "summary_email": {"enabled": True, "to": "test@test.com",
                              "smtp_user": "u", "smtp_password": "p"},
        }
        mock_enriched = [make_lead(id="s1", score=65.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_enriched), \
             patch("src.pipeline.score_leads", return_value=mock_enriched), \
             patch("src.pipeline.send_run_summary") as mock_send, \
             patch("src.pipeline._get_conn", return_value=conn):
            result = runner.invoke(cli, ["re-enrich", "--notify"])
        assert result.exit_code == 0
        mock_send.assert_called_once()
        conn.close()

    def test_re_enrich_empty_db(self, runner, sample_settings, db_conn):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "No stale leads" in result.output


class TestScheduleCommands:
    def test_schedule_install(self, runner, sample_settings):
        sample_settings["schedule"] = {
            "jobs": [{"name": "test", "vertical": "hvac",
                      "metro": "portland-or", "cron": "0 6 * * 1"}],
            "re_enrich": {"enabled": False},
        }
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.install_jobs", return_value=["test"]):
            result = runner.invoke(cli, ["schedule", "install"])
        assert result.exit_code == 0
        assert "test" in result.output

    def test_schedule_list(self, runner):
        jobs = [
            {"name": "hvac-portland", "schedule": "0 6 * * 1", "command": "..."},
            {"name": "dental-seattle", "schedule": "0 6 * * 3", "command": "..."},
        ]
        with patch("src.pipeline.list_jobs", return_value=jobs):
            result = runner.invoke(cli, ["schedule", "list"])
        assert result.exit_code == 0
        assert "hvac-portland" in result.output

    def test_schedule_list_empty(self, runner):
        with patch("src.pipeline.list_jobs", return_value=[]):
            result = runner.invoke(cli, ["schedule", "list"])
        assert result.exit_code == 0
        assert "No scheduled jobs" in result.output

    def test_schedule_remove(self, runner):
        with patch("src.pipeline.remove_jobs", return_value=2):
            result = runner.invoke(cli, ["schedule", "remove"], input="y\n")
        assert result.exit_code == 0
        assert "Removed 2" in result.output

    def test_schedule_remove_none(self, runner):
        with patch("src.pipeline.remove_jobs", return_value=0):
            result = runner.invoke(cli, ["schedule", "remove"], input="y\n")
        assert result.exit_code == 0
        assert "No scheduled jobs" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_pipeline.py -v 2>&1 | head -30`
Expected: Failures because `pipeline.py` still uses JSON I/O

- [ ] **Step 3: Rewrite `src/pipeline.py` to use SQLite**

Replace `src/pipeline.py` with the SQLite-backed version. Key changes:
- Remove `_load_leads`, `_save_json`, and all `json`/`Path` file I/O
- Add `_get_conn()` that returns `db.get_db()`
- `scrape` → upserts leads to DB
- `enrich` → reads leads from DB by `--metro`/`--category`, writes back
- `score` → reads from DB, scores, writes back
- `outreach` → reads scored leads from DB, generates emails, writes back
- `run` → creates `pipeline_runs` record, upserts at each stage
- `re-enrich` → queries DB for stale `enriched_at`
- `stats` → queries `pipeline_runs` and dedup tables
- `report` → reads from DB with filters

```python
"""Main pipeline orchestrator.

Chains: scrape → enrich → score → generate outreach → save results.
Can run full pipeline or individual stages.
All data is stored in SQLite via src.db.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import click
from rich.console import Console
from rich.table import Table

from src.config import load_settings, get_scoring_keywords
from src.models import Lead
from src.db import (
    get_db, upsert_leads, get_leads, get_lead, get_stale_leads,
    start_run, finish_run, get_run_history, get_dedup_stats,
)
from src.scrapers.google_maps import scrape_google_maps
from src.enrichment.website_audit import audit_website, enrich_lead_with_audit
from src.scrapers.reviews import (
    fetch_reviews_outscraper,
    analyze_reviews,
    enrich_lead_with_reviews,
)
from src.scrapers.job_posts import (
    search_jobs_serpapi,
    analyze_job_postings,
    enrich_lead_with_jobs,
)
from src.scoring.score import score_leads
from src.outreach.generate import generate_batch_outreach
from src.outreach.delivery import push_to_instantly
from src.enrichment.async_processor import run_async_enrichment
from src.dedup import filter_new_leads, mark_processed
from src.reporting.html_report import save_report
from src.notifications.email_summary import send_run_summary
from src.scheduler import install_jobs, list_jobs, remove_jobs

console = Console()


def _get_conn():
    """Get the shared database connection."""
    return get_db()


def _print_top_leads(leads: list[Lead], n: int = 10):
    """Print a summary table of top scored leads."""
    table = Table(title=f"Top {n} Leads by Score")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Business", style="cyan")
    table.add_column("Category")
    table.add_column("CRM", justify="center")
    table.add_column("Chat", justify="center")
    table.add_column("Sched", justify="center")
    table.add_column("Job Flags", justify="right")
    table.add_column("Rev Complaints", justify="right")

    for lead in leads[:n]:
        table.add_row(
            f"{lead.score:.1f}" if lead.score else "—",
            lead.business_name[:30],
            lead.category[:20],
            "✗" if lead.has_crm is False else ("✓" if lead.has_crm else "?"),
            "✗" if lead.has_chat_widget is False else ("✓" if lead.has_chat_widget else "?"),
            "✗" if lead.has_scheduling is False else ("✓" if lead.has_scheduling else "?"),
            str(lead.manual_process_postings),
            str(lead.ops_complaint_count),
        )

    console.print(table)


@click.group()
def cli():
    """biz-prospector: find and reach businesses needing modernization."""
    pass


@cli.command()
@click.option("--vertical", required=True)
@click.option("--metro", required=True)
@click.option("--count", default=100)
@click.option("--provider", default="serpapi", type=click.Choice(["serpapi", "apify"]))
def scrape(vertical: str, metro: str, count: int, provider: str):
    """Stage 1: Scrape business listings from Google Maps."""
    leads = scrape_google_maps(vertical, metro, count, provider)
    conn = _get_conn()
    upsert_leads(conn, leads)
    console.print(f"[green]Saved {len(leads)} leads to database[/]")


@cli.command()
@click.option("--metro", default=None)
@click.option("--category", default=None)
def enrich(metro: str | None, category: str | None):
    """Stage 2: Enrich leads with website audit, reviews, and job postings."""
    settings = load_settings()
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category)
    console.print(f"[bold]Enriching {len(leads)} leads[/]")

    kw = get_scoring_keywords(settings)
    complaint_kw = kw["ops_complaint_keywords"]
    manual_kw = kw["manual_process_keywords"]

    for i, lead in enumerate(leads):
        console.print(f"  [{i + 1}/{len(leads)}] {lead.business_name}")

        if lead.website:
            audit = audit_website(lead.website)
            enrich_lead_with_audit(lead, audit)

        if lead.place_id:
            try:
                outscraper_key = settings.get("apis", {}).get("outscraper_key", "")
                if outscraper_key:
                    reviews = fetch_reviews_outscraper(lead.place_id, outscraper_key)
                    analysis = analyze_reviews(reviews, complaint_kw)
                    enrich_lead_with_reviews(lead, analysis)
            except Exception as e:
                console.print(f"    [yellow]Review fetch failed: {e}[/]")

        try:
            serpapi_key = settings.get("apis", {}).get("serpapi_key", "")
            if serpapi_key:
                postings = search_jobs_serpapi(lead.business_name, lead.metro, serpapi_key)
                job_analysis = analyze_job_postings(postings, manual_kw)
                enrich_lead_with_jobs(lead, job_analysis)
        except Exception as e:
            console.print(f"    [yellow]Job search failed: {e}[/]")

    upsert_leads(conn, leads)
    console.print(f"[green]Updated {len(leads)} leads in database[/]")


@cli.command()
@click.option("--metro", default=None)
@click.option("--category", default=None)
@click.option("--vertical", default=None)
@click.option("--threshold", default=None, type=float)
def score(metro: str | None, category: str | None, vertical: str | None, threshold: float | None):
    """Stage 3: Score enriched leads."""
    settings = load_settings()
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category)
    scored = score_leads(leads, vertical)

    if threshold is None:
        threshold = settings.get("pipeline", {}).get("score_threshold", 55)
    qualified = [l for l in scored if (l.score or 0) >= threshold]

    console.print(
        f"[bold]{len(qualified)}/{len(scored)} leads above threshold ({threshold})[/]"
    )
    _print_top_leads(qualified)
    upsert_leads(conn, scored)
    console.print(f"[green]Updated {len(scored)} lead scores in database[/]")


@cli.command()
@click.option("--min-score", default=55.0, type=float)
@click.option("--metro", default=None)
@click.option("--category", default=None)
def outreach(min_score: float, metro: str | None, category: str | None):
    """Stage 4: Generate personalized outreach emails."""
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category, min_score=min_score)
    results = generate_batch_outreach(leads)
    upsert_leads(conn, results)
    console.print(f"[green]Generated outreach for {len(results)} leads[/]")


@cli.command()
@click.option("--vertical", required=True)
@click.option("--metro", required=True)
@click.option("--count", default=100)
@click.option("--provider", default="serpapi", type=click.Choice(["serpapi", "apify"]))
@click.option("--concurrent", default=10, help="Max concurrent enrichment tasks")
@click.option("--skip-dedup", is_flag=True, help="Process all leads even if seen before")
@click.option("--push-instantly", is_flag=True, help="Push results to Instantly.ai")
@click.option("--notify", is_flag=True, help="Send summary email after completion")
def run(
    vertical: str,
    metro: str,
    count: int,
    provider: str,
    concurrent: int,
    skip_dedup: bool,
    push_instantly: bool,
    notify: bool,
):
    """Run the full pipeline: scrape → enrich → score → outreach → [deliver]."""
    settings = load_settings()
    conn = _get_conn()
    threshold = settings.get("pipeline", {}).get("score_threshold", 55)
    run_id = start_run(conn, vertical, metro, threshold)

    # Stage 1: Scrape
    console.rule("[bold blue]Stage 1: Scraping")
    leads = scrape_google_maps(vertical, metro, count, provider)
    scraped_count = len(leads)
    upsert_leads(conn, leads, run_id=run_id)

    # Dedup against previous runs
    if not skip_dedup:
        leads, skipped = filter_new_leads(leads, "enrich")
        if skipped:
            console.print(f"  Skipped {skipped} previously enriched leads")

    if not leads:
        console.print("[yellow]No new leads to process.[/]")
        return

    # Stage 2: Enrich (async)
    console.rule("[bold blue]Stage 2: Enriching")
    leads = run_async_enrichment(leads, max_concurrent=concurrent)
    mark_processed(leads, "enrich")
    upsert_leads(conn, leads, run_id=run_id)

    # Stage 3: Score
    console.rule("[bold blue]Stage 3: Scoring")
    scored = score_leads(leads, vertical)
    qualified = [l for l in scored if (l.score or 0) >= threshold]
    _print_top_leads(qualified)
    upsert_leads(conn, scored, run_id=run_id)

    if not qualified:
        console.print("[yellow]No leads above threshold.[/]")
        return

    # Stage 4: Outreach
    console.rule("[bold blue]Stage 4: Generating Outreach")
    results = generate_batch_outreach(qualified)
    upsert_leads(conn, results, run_id=run_id)

    # Stage 5: Delivery (optional)
    if push_instantly:
        console.rule("[bold blue]Stage 5: Pushing to Instantly")
        followup_days = settings.get("outreach", {}).get("followup_interval_days", 3)
        delivery = push_to_instantly(
            results,
            campaign_name=f"{vertical} {metro} {datetime.now().strftime('%Y%m%d')}",
            followup_interval_days=followup_days,
        )
        console.print(f"  Campaign: {delivery.get('campaign_id')}")
        console.print(f"  Leads added: {delivery.get('leads_added')}")

    # Generate HTML report
    report_path = save_report(
        results,
        title=f"{vertical} {metro} Pipeline Report",
        vertical=vertical,
        metro=metro,
    )
    console.print(f"  Report: {report_path}")

    # Finish run tracking
    finish_run(conn, run_id, {
        "scraped_count": scraped_count,
        "enriched_count": len(leads),
        "qualified_count": len(qualified),
        "emailed_count": sum(1 for l in results if l.outreach_email),
    })

    # Email notification (for scheduled runs)
    if notify:
        run_info = {
            "vertical": vertical,
            "metro": metro,
            "timestamp": datetime.now().strftime("%Y%m%d"),
            "scraped_count": scraped_count,
            "qualified_count": len(qualified),
            "threshold": threshold,
            "is_re_enrich": False,
        }
        send_run_summary(results, run_info, settings, report_path=report_path)

    console.rule("[bold green]Pipeline Complete")
    console.print(
        f"Scraped {scraped_count} → Qualified {len(qualified)} → "
        f"Emails generated for {sum(1 for l in results if l.outreach_email)}"
    )


@cli.command()
@click.option("--metro", default=None)
@click.option("--category", default=None)
@click.option("--vertical", default="")
@click.option("--output", "output_path", default="", help="Output HTML filename")
def report(metro: str | None, category: str | None, vertical: str, output_path: str):
    """Generate an HTML report from leads in the database."""
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category, scored_only=True)
    title = f"{vertical} {metro or ''} Report".strip() if vertical or metro else "Pipeline Run Report"
    path = save_report(
        leads,
        filename=output_path,
        title=title,
        vertical=vertical,
        metro=metro or "",
    )
    console.print(f"[green]Report saved to {path}[/]")


@cli.command()
def stats():
    """Show pipeline run history and dedup stats."""
    conn = _get_conn()
    history = get_run_history(conn, limit=10)
    dedup = get_dedup_stats(conn)

    if not history and not dedup:
        console.print("No leads processed yet.")
        return

    if history:
        table = Table(title="Recent Pipeline Runs")
        table.add_column("ID", justify="right")
        table.add_column("Vertical")
        table.add_column("Metro")
        table.add_column("Scraped", justify="right")
        table.add_column("Qualified", justify="right")
        table.add_column("Emailed", justify="right")
        table.add_column("Started")
        for run in history:
            table.add_row(
                str(run["id"]),
                run["vertical"],
                run["metro"],
                str(run["scraped_count"]),
                str(run["qualified_count"]),
                str(run["emailed_count"]),
                run["started_at"][:16] if run["started_at"] else "—",
            )
        console.print(table)

    if dedup:
        console.print("\n[bold]Dedup Stats:[/]")
        for stage, count in dedup.items():
            console.print(f"  {stage}: {count} leads processed")


@cli.command(name="re-enrich")
@click.option("--max-age", default=None, type=int, help="Override max_age_days from config")
@click.option("--notify", is_flag=True, help="Send summary email after completion")
def re_enrich(max_age: int | None, notify: bool):
    """Re-enrich and re-score stale leads."""
    settings = load_settings()
    conn = _get_conn()
    max_age_days = max_age or settings.get("schedule", {}).get(
        "re_enrich", {}
    ).get("max_age_days", 30)

    # Find stale leads directly from DB
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale_leads = get_stale_leads(conn, cutoff)

    if not stale_leads:
        console.print("[yellow]No stale leads to re-enrich.[/]")
        return

    console.print(f"[bold]Re-enriching {len(stale_leads)} stale leads[/]")

    enriched = run_async_enrichment(stale_leads)
    scored = score_leads(enriched)
    upsert_leads(conn, scored)

    console.rule("[bold green]Re-enrichment Complete")
    console.print(f"Refreshed {len(scored)} leads")

    if notify:
        run_info = {
            "vertical": "all",
            "metro": "all",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "scraped_count": 0,
            "qualified_count": len(scored),
            "threshold": settings.get("pipeline", {}).get("score_threshold", 55),
            "is_re_enrich": True,
        }
        send_run_summary(scored, run_info, settings)


@cli.group()
def schedule():
    """Manage scheduled pipeline runs (cron jobs)."""
    pass


@schedule.command(name="install")
def schedule_install():
    """Install cron jobs from settings.yaml schedule config."""
    settings = load_settings()
    try:
        names = install_jobs(settings)
        if names:
            console.print(f"[green]Installed {len(names)} scheduled jobs:[/]")
            for name in names:
                console.print(f"  • {name}")
        else:
            console.print("[yellow]No jobs configured in settings.yaml[/]")
    except ValueError as e:
        console.print(f"[red]{e}[/]")


@schedule.command(name="list")
def schedule_list():
    """List installed biz-prospector cron jobs."""
    jobs = list_jobs()
    if not jobs:
        console.print("No scheduled jobs found.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("Job", style="cyan")
    table.add_column("Schedule")
    for job in jobs:
        table.add_row(job["name"], job["schedule"])
    console.print(table)


@schedule.command(name="remove")
def schedule_remove():
    """Remove all biz-prospector cron jobs."""
    if not click.confirm("Remove all scheduled biz-prospector jobs?"):
        return
    count = remove_jobs()
    if count > 0:
        console.print(f"[green]Removed {count} scheduled job(s)[/]")
    else:
        console.print("No scheduled jobs to remove.")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run the full test suite to catch regressions**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest --tb=short 2>&1 | tail -10`
Expected: All tests pass (some test counts may change due to removed/rewritten tests)

- [ ] **Step 6: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add src/pipeline.py tests/test_pipeline.py
git commit -m "refactor: replace JSON file I/O with SQLite in pipeline"
```

---

### Task 6: Add `import-json` and `export-json` CLI commands

**Files:**
- Modify: `src/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for import-json and export-json**

Add to `tests/test_pipeline.py`:

```python
class TestImportJsonCommand:
    def test_imports_leads(self, runner, tmp_path, db_conn):
        leads_data = [
            make_lead(id="imp1", business_name="Import One", score=70.0).model_dump(mode="json"),
            make_lead(id="imp2", business_name="Import Two").model_dump(mode="json"),
        ]
        json_file = tmp_path / "leads.json"
        json_file.write_text(json.dumps(leads_data))

        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["import-json", "--input", str(json_file)])
        assert result.exit_code == 0
        assert "Imported 2" in result.output
        assert get_lead(db_conn, "imp1") is not None
        assert get_lead(db_conn, "imp2") is not None

    def test_import_empty_file(self, runner, tmp_path, db_conn):
        json_file = tmp_path / "empty.json"
        json_file.write_text("[]")

        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["import-json", "--input", str(json_file)])
        assert result.exit_code == 0
        assert "0" in result.output


class TestExportJsonCommand:
    def test_exports_leads(self, runner, db_with_leads, tmp_path):
        output_file = tmp_path / "export.json"
        with patch("src.pipeline._get_conn", return_value=db_with_leads):
            result = runner.invoke(cli, ["export-json", "--output", str(output_file)])
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert len(data) == 2

    def test_exports_with_filters(self, runner, tmp_path):
        conn = get_db(":memory:")
        upsert_leads(conn, [
            make_lead(id="e1", metro="portland-or", score=70.0),
            make_lead(id="e2", metro="seattle-wa", score=80.0),
            make_lead(id="e3", metro="portland-or", score=40.0),
        ])
        output_file = tmp_path / "filtered.json"
        with patch("src.pipeline._get_conn", return_value=conn):
            result = runner.invoke(cli, [
                "export-json", "--output", str(output_file),
                "--metro", "portland-or", "--min-score", "55",
            ])
        assert result.exit_code == 0
        data = json.loads(output_file.read_text())
        assert len(data) == 1
        assert data[0]["id"] == "e1"
        conn.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_pipeline.py::TestImportJsonCommand tests/test_pipeline.py::TestExportJsonCommand -v`
Expected: `Error: No such command 'import-json'`

- [ ] **Step 3: Implement import-json and export-json commands**

Add to `src/pipeline.py` (before `if __name__ == "__main__":`):

```python
import json


@cli.command(name="import-json")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True))
def import_json(input_path: str):
    """Import leads from a JSON file into the database."""
    with open(input_path) as f:
        data = json.load(f)
    leads = [Lead(**item) for item in data]
    conn = _get_conn()
    count = upsert_leads(conn, leads)
    console.print(f"[green]Imported {count} leads from {input_path}[/]")


@cli.command(name="export-json")
@click.option("--output", "output_path", required=True, type=click.Path())
@click.option("--metro", default=None)
@click.option("--category", default=None)
@click.option("--min-score", default=None, type=float)
def export_json(output_path: str, metro: str | None, category: str | None, min_score: float | None):
    """Export leads from the database to a JSON file."""
    conn = _get_conn()
    leads = get_leads(conn, metro=metro, category=category, min_score=min_score)
    with open(output_path, "w") as f:
        json.dump([l.model_dump(mode="json") for l in leads], f, indent=2)
    console.print(f"[green]Exported {len(leads)} leads to {output_path}[/]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest tests/test_pipeline.py::TestImportJsonCommand tests/test_pipeline.py::TestExportJsonCommand -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add import-json and export-json CLI commands"
```

---

### Task 7: Remove dead `save_leads` from google_maps scraper and clean up

**Files:**
- Modify: `src/scrapers/google_maps.py`
- Modify: `tests/conftest.py` (remove `tmp_data_dir` fixture if no longer used)

- [ ] **Step 1: Remove `save_leads` from google_maps.py**

Remove the `save_leads` function and its `json` import (if `json` is no longer used elsewhere in the file). Also remove the `DATA_DIR` constant if it's only used by `save_leads`.

Check first:
Run: `cd /Users/rando/Downloads/biz-prospector && grep -n 'save_leads\|DATA_DIR\|import json' src/scrapers/google_maps.py`

Then remove the dead code.

- [ ] **Step 2: Check if `tmp_data_dir` fixture is still used anywhere**

Run: `cd /Users/rando/Downloads/biz-prospector && grep -r 'tmp_data_dir' tests/`

If only used in `test_dedup.py` (which was rewritten in Task 4 to not use it), remove it from `conftest.py`.

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest --tb=short 2>&1 | tail -10`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add -A
git commit -m "chore: remove dead JSON I/O code (save_leads, tmp_data_dir)"
```

---

### Task 8: Update CLAUDE.md, FEATURES.md, CHANGELOG.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `FEATURES.md` (if it exists)
- Modify: `CHANGELOG.md` (if it exists)

- [ ] **Step 1: Update CLAUDE.md**

Update the TODO list — mark "SQLite or Postgres backend instead of JSON files" as done. Update the "Data flow" section to mention SQLite instead of JSON files. Update the "Running" section with the new command syntax (e.g., `enrich --metro portland-or` instead of `enrich --input data/raw/leads.json`). Add new commands `import-json` and `export-json` to the running examples.

- [ ] **Step 2: Update FEATURES.md if it exists**

Run: `ls /Users/rando/Downloads/biz-prospector/FEATURES.md`

If it exists, add the SQLite backend feature.

- [ ] **Step 3: Update CHANGELOG.md if it exists**

Run: `ls /Users/rando/Downloads/biz-prospector/CHANGELOG.md`

If it exists, add an entry for the SQLite migration.

- [ ] **Step 4: Commit**

```bash
cd /Users/rando/Downloads/biz-prospector
git add CLAUDE.md FEATURES.md CHANGELOG.md
git commit -m "docs: update project docs for SQLite backend migration"
```

---

### Task 9: Final verification — full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `cd /Users/rando/Downloads/biz-prospector && python -m pytest -v 2>&1 | tail -20`

Expected: All tests pass. The total count will differ from the pre-migration 447 because some tests were rewritten and new `test_db.py` tests were added.

- [ ] **Step 2: Verify no JSON file references remain in production code**

Run: `cd /Users/rando/Downloads/biz-prospector && grep -rn 'json\.load\|json\.dump\|\.json' src/ --include='*.py' | grep -v 'json\.loads\|json\.dumps\|__pycache__'`

The only hits should be:
- `src/db.py` — `json.dumps`/`json.loads` for serializing list/dict fields (expected)
- `src/pipeline.py` — `json.load`/`json.dump` in `import-json`/`export-json` commands (expected)
- `src/outreach/generate.py` — `json.loads` for LLM response parsing (not file I/O, expected)

There should be NO `json.load(f)` or `json.dump(..., f)` calls remaining in `src/dedup.py` or in the main pipeline flow of `src/pipeline.py`.

- [ ] **Step 3: Verify DB file can be created**

Run: `cd /Users/rando/Downloads/biz-prospector && python -c "from src.db import get_db; conn = get_db('/tmp/test-biz.db'); print('OK'); conn.close()"`

Expected: `OK` and `/tmp/test-biz.db` exists.

- [ ] **Step 4: Push to remote**

```bash
cd /Users/rando/Downloads/biz-prospector
git push origin master
```
