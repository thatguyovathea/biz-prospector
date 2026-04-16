"""SQLite storage backend for biz-prospector.

Replaces JSON file I/O with a single SQLite database.
All list/dict Lead fields are stored as JSON text columns.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.models import Lead, LeadSource

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


def get_db(path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open or create the SQLite database, apply schema, return connection.

    Args:
        path: Filesystem path or \":memory:\" for in-memory database.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    # Ensure parent directory exists for file-based databases
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Lead <-> row serialization
# ---------------------------------------------------------------------------

# Stable column order for INSERT statements (must match leads table).
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
    "last_run_id",
]

_JSON_LIST_FIELDS = frozenset({
    "tech_stack", "ops_complaint_samples", "manual_process_titles",
    "employee_titles", "followups",
})
_JSON_DICT_FIELDS = frozenset({"score_breakdown"})
_BOOL_FIELDS = frozenset({
    "has_crm", "has_chat_widget", "has_scheduling",
    "has_ssl", "is_mobile_responsive",
})
_DATETIME_FIELDS = frozenset({
    "scraped_at", "enriched_at", "scored_at", "contacted_at",
})


def _bool_to_int(val: bool | None) -> int | None:
    if val is None:
        return None
    return 1 if val else 0


def _int_to_bool(val: int | None) -> bool | None:
    if val is None:
        return None
    return bool(val)


def _lead_to_row(lead: Lead) -> tuple:
    """Convert a Lead model to a tuple of SQLite-compatible values."""
    values = []
    for field in _LEAD_FIELDS:
        val = getattr(lead, field, None)
        if field in _JSON_LIST_FIELDS or field in _JSON_DICT_FIELDS:
            val = json.dumps(val)
        elif field in _BOOL_FIELDS:
            val = _bool_to_int(val)
        elif field == "source":
            val = val.value if val is not None else "google_maps"
        elif field in _DATETIME_FIELDS:
            val = val.isoformat() if val is not None else None
        values.append(val)
    return tuple(values)


def _row_to_lead(row: sqlite3.Row) -> Lead:
    """Convert a sqlite3.Row back to a Lead model."""
    data = {}
    for field in _LEAD_FIELDS:
        val = row[field]
        if field in _JSON_LIST_FIELDS or field in _JSON_DICT_FIELDS:
            val = json.loads(val) if val is not None else ([] if field in _JSON_LIST_FIELDS else {})
        elif field in _BOOL_FIELDS:
            val = _int_to_bool(val)
        elif field == "source":
            val = LeadSource(val) if val is not None else LeadSource.GOOGLE_MAPS
        elif field in _DATETIME_FIELDS:
            val = datetime.fromisoformat(val) if val is not None else None
        data[field] = val
    # last_run_id is not a Lead field, drop it
    data.pop("last_run_id", None)
    return Lead(**data)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

_PLACEHOLDERS = ", ".join(["?"] * len(_LEAD_FIELDS))
_COLUMNS = ", ".join(_LEAD_FIELDS)
_UPSERT_SQL = f"INSERT OR REPLACE INTO leads ({_COLUMNS}) VALUES ({_PLACEHOLDERS})"


def upsert_leads(conn: sqlite3.Connection, leads: list[Lead], run_id: int | None = None) -> int:
    """Insert or update leads in the database.

    Args:
        conn: Database connection.
        leads: List of Lead models to upsert.
        run_id: Optional pipeline run ID to tag on each lead.

    Returns:
        Number of leads upserted.
    """
    rows = []
    for lead in leads:
        row = list(_lead_to_row(lead))
        # last_run_id is the last field
        if run_id is not None:
            row[-1] = run_id
        rows.append(tuple(row))
    conn.executemany(_UPSERT_SQL, rows)
    conn.commit()
    return len(rows)


def get_lead(conn: sqlite3.Connection, lead_id: str) -> Lead | None:
    """Fetch a single lead by ID. Returns None if not found."""
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        return None
    return _row_to_lead(row)


def get_leads(
    conn: sqlite3.Connection,
    *,
    metro: str | None = None,
    category: str | None = None,
    min_score: float | None = None,
    scored_only: bool = False,
    limit: int | None = None,
) -> list[Lead]:
    """Flexible lead query with optional filters.

    Args:
        conn: Database connection.
        metro: Filter by metro area.
        category: Filter by business category.
        min_score: Minimum score threshold.
        scored_only: If True, exclude leads with NULL score.
        limit: Maximum number of results.

    Returns:
        List of Lead models matching the filters.
    """
    clauses: list[str] = []
    params: list = []

    if metro is not None:
        clauses.append("metro = ?")
        params.append(metro)
    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if min_score is not None:
        clauses.append("score >= ?")
        params.append(min_score)
    if scored_only:
        clauses.append("score IS NOT NULL")

    sql = "SELECT * FROM leads"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_lead(row) for row in rows]


# ---------------------------------------------------------------------------
# Dedup operations
# ---------------------------------------------------------------------------


def mark_processed(conn: sqlite3.Connection, leads: list[Lead], stage: str) -> None:
    """Record that leads have been processed for a given stage.

    Uses INSERT OR IGNORE so duplicates are silently skipped.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany(
        "INSERT OR IGNORE INTO dedup (lead_id, stage, processed_at) VALUES (?, ?, ?)",
        [(lead.id, stage, now) for lead in leads],
    )
    conn.commit()


def filter_new_leads(
    conn: sqlite3.Connection, leads: list[Lead], stage: str
) -> tuple[list[Lead], int]:
    """Filter out leads that have already been processed for a stage.

    Returns:
        Tuple of (new_leads, skipped_count).
    """
    if not leads:
        return [], 0

    lead_ids = [lead.id for lead in leads]
    placeholders = ", ".join(["?"] * len(lead_ids))
    rows = conn.execute(
        f"SELECT lead_id FROM dedup WHERE stage = ? AND lead_id IN ({placeholders})",
        [stage] + lead_ids,
    ).fetchall()
    seen = {row["lead_id"] for row in rows}

    new_leads = [lead for lead in leads if lead.id not in seen]
    skipped = len(leads) - len(new_leads)
    return new_leads, skipped


def get_dedup_stats(conn: sqlite3.Connection) -> dict[str, int]:
    """Return count of processed leads per stage."""
    rows = conn.execute(
        "SELECT stage, COUNT(*) as cnt FROM dedup GROUP BY stage"
    ).fetchall()
    return {row["stage"]: row["cnt"] for row in rows}


# ---------------------------------------------------------------------------
# Pipeline run tracking
# ---------------------------------------------------------------------------


def start_run(
    conn: sqlite3.Connection,
    vertical: str,
    metro: str,
    threshold: float | None = None,
    is_re_enrich: bool = False,
) -> int:
    """Create a new pipeline run record and return its ID."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """INSERT INTO pipeline_runs (vertical, metro, started_at, threshold, is_re_enrich)
           VALUES (?, ?, ?, ?, ?)""",
        (vertical, metro, now, threshold, 1 if is_re_enrich else 0),
    )
    conn.commit()
    return cursor.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, counts: dict[str, int]) -> None:
    """Mark a pipeline run as completed and update count columns."""
    now = datetime.now(timezone.utc).isoformat()
    set_clauses = ["completed_at = ?"]
    params: list = [now]

    for col in ("scraped_count", "enriched_count", "qualified_count", "emailed_count"):
        if col in counts:
            set_clauses.append(f"{col} = ?")
            params.append(counts[col])

    params.append(run_id)
    conn.execute(
        f"UPDATE pipeline_runs SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )
    conn.commit()


def get_run_history(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Return recent pipeline runs, most recent first."""
    rows = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_stale_leads(conn: sqlite3.Connection, cutoff: datetime) -> list[Lead]:
    """Return scored leads whose enriched_at is older than the cutoff.

    Useful for identifying leads that need re-enrichment.
    """
    rows = conn.execute(
        "SELECT * FROM leads WHERE score IS NOT NULL AND enriched_at < ?",
        (cutoff.isoformat(),),
    ).fetchall()
    return [_row_to_lead(row) for row in rows]
