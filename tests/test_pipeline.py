"""Tests for the pipeline CLI orchestrator."""

import json
from io import StringIO
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner
from rich.console import Console

from src.pipeline import cli, _print_top_leads
from src.models import Lead
from src.db import get_db, upsert_leads, get_leads, get_lead
from tests.conftest import make_lead


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def db_conn():
    """In-memory SQLite database for test isolation."""
    conn = get_db(":memory:")
    return conn


@pytest.fixture
def db_with_leads(db_conn):
    """Pre-populate DB with sample leads."""
    leads = [
        make_lead(id="l1", business_name="Lead One", score=70.0, has_crm=False),
        make_lead(id="l2", business_name="Lead Two", score=40.0, has_crm=True),
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
    def test_scrape_cli(self, runner, sample_settings, db_conn):
        mock_leads = [make_lead(id="s1")]
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads) as mock_scrape, \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["scrape", "--vertical", "hvac", "--metro", "portland-or"])
        assert result.exit_code == 0
        mock_scrape.assert_called_once()
        call_args = mock_scrape.call_args
        assert call_args[0][0] == "hvac"
        assert call_args[0][1] == "portland-or"
        # Verify lead is in DB
        lead = get_lead(db_conn, "s1")
        assert lead is not None
        assert lead.business_name == "Acme HVAC Services"


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

    def test_enrich_no_leads(self, runner, db_conn, sample_settings):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["enrich", "--metro", "nonexistent"])
        assert result.exit_code == 0
        assert "No leads found" in result.output

    def test_enrich_handles_review_exception(self, runner, sample_settings, db_conn):
        leads = [make_lead(id="l1", place_id="place_abc", website="")]
        upsert_leads(db_conn, leads)

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.fetch_reviews_outscraper", side_effect=Exception("API down")), \
             patch("src.pipeline.search_jobs_serpapi", return_value=[]), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["enrich", "--metro", "portland-or"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()

    def test_enrich_handles_job_search_exception(self, runner, sample_settings, db_conn):
        leads = [make_lead(id="l1", place_id="", website="")]
        upsert_leads(db_conn, leads)

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.search_jobs_serpapi", side_effect=Exception("SerpAPI down")), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["enrich", "--metro", "portland-or"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()


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
        with patch("src.pipeline.generate_batch_outreach", side_effect=lambda leads, **kw: leads) as mock_batch, \
             patch("src.pipeline._get_conn", return_value=db_with_leads):
            result = runner.invoke(cli, ["outreach", "--min-score", "50"])
        assert result.exit_code == 0
        mock_batch.assert_called_once()

    def test_outreach_no_leads(self, runner, db_conn):
        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["outreach"])
        assert result.exit_code == 0
        assert "No scored leads" in result.output


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

    def test_report_no_leads(self, runner, db_conn, tmp_path):
        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["report"])
        assert result.exit_code == 0
        assert "No scored leads" in result.output


class TestStatsCommand:
    def test_stats_with_runs(self, runner, db_conn):
        from src.db import start_run, finish_run, mark_processed as db_mark
        run_id = start_run(db_conn, "hvac", "portland-or", threshold=55)
        finish_run(db_conn, run_id, {"scraped_count": 10, "qualified_count": 5})
        leads = [make_lead(id="st1")]
        upsert_leads(db_conn, leads)
        db_mark(db_conn, leads, "enrich")

        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "hvac" in result.output
        assert "enrich" in result.output

    def test_stats_empty(self, runner, db_conn):
        with patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "No pipeline runs" in result.output


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
    def test_re_enriches_stale_leads(self, runner, sample_settings, db_conn):
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        stale_lead = make_lead(id="stale1", score=60.0, enriched_at=old_date)
        upsert_leads(db_conn, [stale_lead])

        sample_settings["schedule"] = {"re_enrich": {"max_age_days": 30}}
        mock_enriched = [make_lead(id="stale1", score=65.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_enriched), \
             patch("src.pipeline.score_leads", return_value=mock_enriched), \
             patch("src.pipeline.send_run_summary"), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "Re-enriching" in result.output

    def test_skips_fresh_leads(self, runner, sample_settings, db_conn):
        fresh_date = datetime.now(timezone.utc).isoformat()
        fresh_lead = make_lead(id="fresh1", score=60.0, enriched_at=fresh_date)
        upsert_leads(db_conn, [fresh_lead])

        sample_settings["schedule"] = {"re_enrich": {"max_age_days": 30}}

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "No stale leads" in result.output

    def test_re_enrich_with_notify(self, runner, sample_settings, db_conn):
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        stale_lead = make_lead(id="s1", score=60.0, enriched_at=old_date)
        upsert_leads(db_conn, [stale_lead])

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
             patch("src.pipeline._get_conn", return_value=db_conn):
            result = runner.invoke(cli, ["re-enrich", "--notify"])
        assert result.exit_code == 0
        mock_send.assert_called_once()

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
             patch("src.pipeline.install_jobs", return_value=["test"]) as mock_install:
            result = runner.invoke(cli, ["schedule", "install"])
        assert result.exit_code == 0
        mock_install.assert_called_once()
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
        assert "dental-seattle" in result.output

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
