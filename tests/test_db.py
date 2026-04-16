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
