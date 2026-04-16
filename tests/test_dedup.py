"""Tests for deduplication logic (SQLite backend)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.db import get_db, mark_processed as db_mark
from src.dedup import filter_new_leads, mark_processed, reset_stage, get_stats
from tests.conftest import make_lead


@pytest.fixture
def db_conn():
    """In-memory SQLite database for isolated tests."""
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
        # Pre-populate two leads as already processed
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

        rows = db_conn.execute(
            "SELECT lead_id, processed_at FROM dedup WHERE stage = 'enrich'"
        ).fetchall()
        ids = {row["lead_id"] for row in rows}
        assert ids == {"lead1", "lead2"}
        # processed_at should be valid ISO timestamps
        for row in rows:
            assert row["processed_at"] is not None

    def test_appends_to_existing(self, db_conn):
        # Pre-populate one lead
        db_mark(db_conn, [make_lead(id="existing_lead")], "enrich")

        with patch("src.dedup._get_conn", return_value=db_conn):
            mark_processed([make_lead(id="new_lead")], "enrich")

        rows = db_conn.execute(
            "SELECT lead_id FROM dedup WHERE stage = 'enrich'"
        ).fetchall()
        ids = {row["lead_id"] for row in rows}
        assert "existing_lead" in ids
        assert "new_lead" in ids


class TestResetStage:
    def test_deletes_dedup_records(self, db_conn):
        db_mark(db_conn, [make_lead(id="lead1")], "enrich")
        with patch("src.dedup._get_conn", return_value=db_conn):
            reset_stage("enrich")

        count = db_conn.execute(
            "SELECT COUNT(*) as cnt FROM dedup WHERE stage = 'enrich'"
        ).fetchone()["cnt"]
        assert count == 0

    def test_no_error_if_empty(self, db_conn):
        with patch("src.dedup._get_conn", return_value=db_conn):
            reset_stage("enrich")  # Should not raise


class TestGetStats:
    def test_counts_per_stage(self, db_conn):
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
