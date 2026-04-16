"""Tests for deduplication logic."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from src.dedup import filter_new_leads, mark_processed, reset_stage, get_stats
from tests.conftest import make_lead


class TestFilterNewLeads:
    def test_all_new_on_first_run(self, tmp_data_dir):
        leads = [make_lead(id="lead1"), make_lead(id="lead2"), make_lead(id="lead3")]
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            new, skipped = filter_new_leads(leads, "enrich")
        assert len(new) == 3
        assert skipped == 0

    def test_filters_processed_leads(self, tmp_data_dir):
        leads = [make_lead(id="lead1"), make_lead(id="lead2"), make_lead(id="lead3")]
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        dedup_file = dedup_dir / "enrich_processed.json"
        dedup_file.write_text(json.dumps({"lead1": "2026-01-01T00:00:00", "lead2": "2026-01-01T00:00:00"}))
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            new, skipped = filter_new_leads(leads, "enrich")
        assert len(new) == 1
        assert new[0].id == "lead3"
        assert skipped == 2

    def test_empty_leads_list(self, tmp_data_dir):
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            new, skipped = filter_new_leads([], "enrich")
        assert new == []
        assert skipped == 0


class TestMarkProcessed:
    def test_writes_lead_ids(self, tmp_data_dir):
        leads = [make_lead(id="lead1"), make_lead(id="lead2")]
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            mark_processed(leads, "enrich")
        dedup_file = dedup_dir / "enrich_processed.json"
        data = json.loads(dedup_file.read_text())
        assert "lead1" in data
        assert "lead2" in data
        # Values must be valid ISO-format timestamps
        datetime.fromisoformat(data["lead1"])
        datetime.fromisoformat(data["lead2"])

    def test_appends_to_existing(self, tmp_data_dir):
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        dedup_file = dedup_dir / "enrich_processed.json"
        dedup_file.write_text(json.dumps({"existing_lead": "2026-01-01T00:00:00"}))
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            mark_processed([make_lead(id="new_lead")], "enrich")
        data = json.loads(dedup_file.read_text())
        assert "existing_lead" in data
        assert "new_lead" in data


class TestResetStage:
    def test_deletes_dedup_file(self, tmp_data_dir):
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        dedup_file = dedup_dir / "enrich_processed.json"
        dedup_file.write_text(json.dumps({"lead1": "2026-01-01T00:00:00"}))
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            reset_stage("enrich")
        assert not dedup_file.exists()

    def test_no_error_if_missing(self, tmp_data_dir):
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            reset_stage("enrich")


class TestGetStats:
    def test_counts_per_stage(self, tmp_data_dir):
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        (dedup_dir / "enrich_processed.json").write_text(json.dumps({"l1": "t1", "l2": "t2"}))
        (dedup_dir / "score_processed.json").write_text(json.dumps({"l1": "t1"}))
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            stats = get_stats()
        assert stats["enrich"] == 2
        assert stats["score"] == 1

    def test_empty_when_no_files(self, tmp_data_dir):
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            stats = get_stats()
        assert stats == {}
