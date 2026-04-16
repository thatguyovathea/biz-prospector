"""Tests for the SQLite storage backend."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models import Lead, LeadSource
from tests.conftest import make_lead


class TestGetDb:
    """Tests for get_db() connection and schema creation."""

    def test_creates_database_file(self, tmp_path):
        from src.db import get_db

        db_path = tmp_path / "test.db"
        conn = get_db(str(db_path))
        conn.close()
        assert db_path.exists()

    def test_creates_leads_table(self, tmp_path):
        from src.db import get_db

        conn = get_db(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_dedup_table(self, tmp_path):
        from src.db import get_db

        conn = get_db(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dedup'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_pipeline_runs_table(self, tmp_path):
        from src.db import get_db

        conn = get_db(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_enables_wal_mode(self, tmp_path):
        from src.db import get_db

        conn = get_db(str(tmp_path / "test.db"))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_idempotent_on_existing_db(self, tmp_path):
        from src.db import get_db

        db_path = str(tmp_path / "test.db")
        conn1 = get_db(db_path)
        conn1.execute(
            "INSERT INTO pipeline_runs (vertical, metro, started_at) VALUES (?, ?, ?)",
            ("hvac", "portland-or", "2026-01-01T00:00:00"),
        )
        conn1.commit()
        conn1.close()

        # Opening again should not destroy data
        conn2 = get_db(db_path)
        row = conn2.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()
        assert row[0] == 1
        conn2.close()

    def test_in_memory_db(self):
        from src.db import get_db

        conn = get_db(":memory:")
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
        )
        assert cursor.fetchone() is not None
        conn.close()
