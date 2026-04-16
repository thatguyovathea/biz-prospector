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
