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


class TestLeadRoundTrip:
    """Tests for _lead_to_row / _row_to_lead serialization."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.db import get_db

        self.conn = get_db(":memory:")
        yield
        self.conn.close()

    def test_basic_fields_survive_round_trip(self):
        from src.db import _lead_to_row, _row_to_lead, upsert_leads

        lead = make_lead()
        upsert_leads(self.conn, [lead])
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead.id,)).fetchone()
        restored = _row_to_lead(row)
        assert restored.business_name == lead.business_name
        assert restored.address == lead.address
        assert restored.phone == lead.phone
        assert restored.metro == lead.metro

    def test_json_list_fields_round_trip(self):
        from src.db import upsert_leads, _row_to_lead

        lead = make_lead(
            tech_stack=["wordpress", "react"],
            ops_complaint_samples=["never called back"],
            manual_process_titles=["data entry clerk"],
            employee_titles=["Office Manager", "Dispatcher"],
            followups=["followup1", "followup2"],
        )
        upsert_leads(self.conn, [lead])
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead.id,)).fetchone()
        restored = _row_to_lead(row)
        assert restored.tech_stack == ["wordpress", "react"]
        assert restored.ops_complaint_samples == ["never called back"]
        assert restored.manual_process_titles == ["data entry clerk"]
        assert restored.employee_titles == ["Office Manager", "Dispatcher"]
        assert restored.followups == ["followup1", "followup2"]

    def test_json_dict_field_round_trip(self):
        from src.db import upsert_leads, _row_to_lead

        lead = make_lead(score_breakdown={"website": 15.0, "crm": 10.0})
        upsert_leads(self.conn, [lead])
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead.id,)).fetchone()
        restored = _row_to_lead(row)
        assert restored.score_breakdown == {"website": 15.0, "crm": 10.0}

    def test_bool_fields_round_trip(self):
        from src.db import upsert_leads, _row_to_lead

        lead = make_lead(has_crm=True, has_chat_widget=False, has_scheduling=None)
        upsert_leads(self.conn, [lead])
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead.id,)).fetchone()
        restored = _row_to_lead(row)
        assert restored.has_crm is True
        assert restored.has_chat_widget is False
        assert restored.has_scheduling is None

    def test_enum_source_round_trip(self):
        from src.db import upsert_leads, _row_to_lead

        lead = make_lead(source=LeadSource.LINKEDIN)
        upsert_leads(self.conn, [lead])
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead.id,)).fetchone()
        restored = _row_to_lead(row)
        assert restored.source == LeadSource.LINKEDIN

    def test_datetime_fields_round_trip(self):
        from src.db import upsert_leads, _row_to_lead

        now = datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
        lead = make_lead(scraped_at=now, enriched_at=now)
        upsert_leads(self.conn, [lead])
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead.id,)).fetchone()
        restored = _row_to_lead(row)
        assert restored.scraped_at == now
        assert restored.enriched_at == now

    def test_none_optional_fields_round_trip(self):
        from src.db import upsert_leads, _row_to_lead

        lead = make_lead(
            rating=None, review_count=None, score=None,
            page_speed_score=None, employee_count=None, founded_year=None,
            owner_response_rate=None, scraped_at=None,
        )
        upsert_leads(self.conn, [lead])
        row = self.conn.execute("SELECT * FROM leads WHERE id = ?", (lead.id,)).fetchone()
        restored = _row_to_lead(row)
        assert restored.rating is None
        assert restored.review_count is None
        assert restored.score is None
        assert restored.scraped_at is None


class TestUpsertLeads:
    """Tests for upsert_leads and get_lead."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.db import get_db

        self.conn = get_db(":memory:")
        yield
        self.conn.close()

    def test_insert_single_lead(self):
        from src.db import upsert_leads, get_lead

        lead = make_lead()
        upsert_leads(self.conn, [lead])
        restored = get_lead(self.conn, lead.id)
        assert restored is not None
        assert restored.business_name == lead.business_name

    def test_upsert_updates_existing(self):
        from src.db import upsert_leads, get_lead

        lead = make_lead()
        upsert_leads(self.conn, [lead])
        updated = make_lead(business_name="Updated HVAC Co")
        upsert_leads(self.conn, [updated])
        restored = get_lead(self.conn, lead.id)
        assert restored.business_name == "Updated HVAC Co"
        # Should still be only one row
        count = self.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        assert count == 1

    def test_upsert_multiple_leads(self):
        from src.db import upsert_leads

        leads = [make_lead(id=f"lead-{i}", business_name=f"Biz {i}") for i in range(5)]
        upsert_leads(self.conn, leads)
        count = self.conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        assert count == 5

    def test_get_lead_returns_none_for_missing(self):
        from src.db import get_lead

        assert get_lead(self.conn, "nonexistent") is None


class TestGetLeads:
    """Tests for get_leads() with various filters."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.db import get_db, upsert_leads

        self.conn = get_db(":memory:")
        # Seed 6 leads across 2 metros and 2 categories, some scored
        self.leads = [
            make_lead(id="p1", metro="portland-or", category="HVAC", score=80.0),
            make_lead(id="p2", metro="portland-or", category="HVAC", score=60.0),
            make_lead(id="p3", metro="portland-or", category="dental", score=None),
            make_lead(id="s1", metro="seattle-wa", category="HVAC", score=90.0),
            make_lead(id="s2", metro="seattle-wa", category="dental", score=40.0),
            make_lead(id="s3", metro="seattle-wa", category="dental", score=None),
        ]
        upsert_leads(self.conn, self.leads)
        yield
        self.conn.close()

    def test_get_all_leads(self):
        from src.db import get_leads

        results = get_leads(self.conn)
        assert len(results) == 6

    def test_filter_by_metro(self):
        from src.db import get_leads

        results = get_leads(self.conn, metro="portland-or")
        assert len(results) == 3
        assert all(l.metro == "portland-or" for l in results)

    def test_filter_by_category(self):
        from src.db import get_leads

        results = get_leads(self.conn, category="dental")
        assert len(results) == 3
        assert all(l.category == "dental" for l in results)

    def test_filter_by_min_score(self):
        from src.db import get_leads

        results = get_leads(self.conn, min_score=70.0)
        assert len(results) == 2
        assert {l.id for l in results} == {"p1", "s1"}

    def test_scored_only(self):
        from src.db import get_leads

        results = get_leads(self.conn, scored_only=True)
        assert len(results) == 4
        assert all(l.score is not None for l in results)

    def test_limit(self):
        from src.db import get_leads

        results = get_leads(self.conn, limit=2)
        assert len(results) == 2

    def test_combined_filters(self):
        from src.db import get_leads

        results = get_leads(self.conn, metro="seattle-wa", category="dental", scored_only=True)
        assert len(results) == 1
        assert results[0].id == "s2"

    def test_no_matches(self):
        from src.db import get_leads

        results = get_leads(self.conn, metro="nonexistent")
        assert results == []


class TestDedup:
    """Tests for mark_processed, filter_new_leads, get_dedup_stats."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.db import get_db

        self.conn = get_db(":memory:")
        yield
        self.conn.close()

    def test_mark_processed_inserts_records(self):
        from src.db import mark_processed

        leads = [make_lead(id=f"lead-{i}") for i in range(3)]
        mark_processed(self.conn, leads, "scrape")
        count = self.conn.execute("SELECT COUNT(*) FROM dedup").fetchone()[0]
        assert count == 3

    def test_mark_processed_idempotent(self):
        from src.db import mark_processed

        leads = [make_lead(id="lead-1")]
        mark_processed(self.conn, leads, "scrape")
        mark_processed(self.conn, leads, "scrape")  # duplicate — should not fail
        count = self.conn.execute("SELECT COUNT(*) FROM dedup").fetchone()[0]
        assert count == 1

    def test_filter_new_leads_returns_unprocessed(self):
        from src.db import mark_processed, filter_new_leads

        old = [make_lead(id="old-1"), make_lead(id="old-2")]
        mark_processed(self.conn, old, "enrich")

        candidates = [make_lead(id="old-1"), make_lead(id="new-1"), make_lead(id="new-2")]
        new_leads, skipped = filter_new_leads(self.conn, candidates, "enrich")
        assert len(new_leads) == 2
        assert skipped == 1
        assert {l.id for l in new_leads} == {"new-1", "new-2"}

    def test_filter_new_leads_different_stage(self):
        from src.db import mark_processed, filter_new_leads

        leads = [make_lead(id="lead-1")]
        mark_processed(self.conn, leads, "scrape")
        # Same lead but different stage should be considered new
        new_leads, skipped = filter_new_leads(self.conn, leads, "enrich")
        assert len(new_leads) == 1
        assert skipped == 0

    def test_get_dedup_stats(self):
        from src.db import mark_processed, get_dedup_stats

        mark_processed(self.conn, [make_lead(id=f"s-{i}") for i in range(3)], "scrape")
        mark_processed(self.conn, [make_lead(id=f"e-{i}") for i in range(2)], "enrich")
        stats = get_dedup_stats(self.conn)
        assert stats == {"scrape": 3, "enrich": 2}

    def test_get_dedup_stats_empty(self):
        from src.db import get_dedup_stats

        stats = get_dedup_stats(self.conn)
        assert stats == {}


class TestPipelineRuns:
    """Tests for start_run, finish_run, get_run_history."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.db import get_db

        self.conn = get_db(":memory:")
        yield
        self.conn.close()

    def test_start_run_returns_id(self):
        from src.db import start_run

        run_id = start_run(self.conn, "hvac", "portland-or", threshold=55.0)
        assert isinstance(run_id, int)
        assert run_id > 0

    def test_start_run_stores_metadata(self):
        from src.db import start_run

        run_id = start_run(self.conn, "dental", "seattle-wa", threshold=60.0, is_re_enrich=True)
        row = self.conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        assert row["vertical"] == "dental"
        assert row["metro"] == "seattle-wa"
        assert row["threshold"] == 60.0
        assert row["is_re_enrich"] == 1

    def test_finish_run_updates_counts(self):
        from src.db import start_run, finish_run

        run_id = start_run(self.conn, "hvac", "portland-or", threshold=55.0)
        finish_run(self.conn, run_id, {
            "scraped_count": 100,
            "enriched_count": 80,
            "qualified_count": 30,
            "emailed_count": 25,
        })
        row = self.conn.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        assert row["scraped_count"] == 100
        assert row["enriched_count"] == 80
        assert row["qualified_count"] == 30
        assert row["emailed_count"] == 25
        assert row["completed_at"] is not None

    def test_get_run_history(self):
        from src.db import start_run, finish_run, get_run_history

        for i in range(3):
            rid = start_run(self.conn, "hvac", f"metro-{i}", threshold=55.0)
            finish_run(self.conn, rid, {"scraped_count": i * 10})
        history = get_run_history(self.conn, limit=2)
        assert len(history) == 2
        # Most recent first
        assert history[0]["metro"] == "metro-2"

    def test_get_stale_leads(self):
        from src.db import get_db, upsert_leads, get_stale_leads

        cutoff = datetime(2026, 4, 1, tzinfo=timezone.utc)
        stale = make_lead(
            id="stale-1",
            score=70.0,
            enriched_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        fresh = make_lead(
            id="fresh-1",
            score=70.0,
            enriched_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        )
        unscored = make_lead(
            id="unscored",
            score=None,
            enriched_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        upsert_leads(self.conn, [stale, fresh, unscored])
        results = get_stale_leads(self.conn, cutoff)
        assert len(results) == 1
        assert results[0].id == "stale-1"
