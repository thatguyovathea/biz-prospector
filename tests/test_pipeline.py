"""Tests for the pipeline CLI orchestrator."""

import json
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from src.pipeline import (
    cli,
    _load_leads,
    _save_json,
    _print_top_leads,
)
from src.models import Lead
from tests.conftest import make_lead


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def leads_json_file(tmp_path):
    """Create a temp JSON file with sample leads."""
    leads = [
        make_lead(id="l1", business_name="Lead One", score=70.0, has_crm=False).model_dump(mode="json"),
        make_lead(id="l2", business_name="Lead Two", score=40.0, has_crm=True).model_dump(mode="json"),
    ]
    path = tmp_path / "leads.json"
    path.write_text(json.dumps(leads))
    return str(path)


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


class TestLoadLeads:
    def test_loads_from_json(self, tmp_path):
        data = [{"business_name": "Test Biz"}, {"business_name": "Another"}]
        path = tmp_path / "test.json"
        path.write_text(json.dumps(data))
        leads = _load_leads(str(path))
        assert len(leads) == 2
        assert leads[0].business_name == "Test Biz"


class TestSaveJson:
    def test_saves_leads(self, tmp_path):
        leads = [make_lead(id="a"), make_lead(id="b")]
        with patch("src.pipeline.DATA_DIR", tmp_path):
            path = _save_json(leads, "test_sub", "output.json")
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 2

    def test_creates_subdirectory(self, tmp_path):
        leads = [make_lead()]
        with patch("src.pipeline.DATA_DIR", tmp_path):
            path = _save_json(leads, "new_sub", "out.json")
        assert (tmp_path / "new_sub").is_dir()


class TestPrintTopLeads:
    def test_prints_without_error(self):
        leads = [
            make_lead(score=80.0, has_crm=False, has_chat_widget=True, has_scheduling=None),
            make_lead(score=None, has_crm=None),
        ]
        # Should not raise
        _print_top_leads(leads, n=5)


class TestScrapeCommand:
    def test_scrape_cli(self, runner, sample_settings, tmp_path):
        mock_leads = [make_lead(id="s1")]
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline._save_json"):
            result = runner.invoke(cli, ["scrape", "--vertical", "hvac", "--metro", "portland-or"])
        assert result.exit_code == 0


class TestEnrichCommand:
    def test_enrich_cli(self, runner, leads_json_file, sample_settings, tmp_path):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.audit_website") as mock_audit, \
             patch("src.pipeline.enrich_lead_with_audit"), \
             patch("src.pipeline.fetch_reviews_outscraper", return_value=[]), \
             patch("src.pipeline.search_jobs_serpapi", return_value=[]), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            mock_audit.return_value = MagicMock()
            result = runner.invoke(cli, ["enrich", "--input", leads_json_file])
        assert result.exit_code == 0

    def test_enrich_handles_review_exception(self, runner, sample_settings, tmp_path):
        leads = [make_lead(id="l1", place_id="place_abc", website="").model_dump(mode="json")]
        path = tmp_path / "leads.json"
        path.write_text(json.dumps(leads))

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.fetch_reviews_outscraper", side_effect=Exception("API down")), \
             patch("src.pipeline.search_jobs_serpapi", return_value=[]), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["enrich", "--input", str(path)])
        assert result.exit_code == 0

    def test_enrich_handles_job_search_exception(self, runner, sample_settings, tmp_path):
        leads = [make_lead(id="l1", place_id="", website="").model_dump(mode="json")]
        path = tmp_path / "leads.json"
        path.write_text(json.dumps(leads))

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.search_jobs_serpapi", side_effect=Exception("SerpAPI down")), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["enrich", "--input", str(path)])
        assert result.exit_code == 0


class TestScoreCommand:
    def test_score_cli(self, runner, leads_json_file, sample_settings, tmp_path):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["score", "--input", leads_json_file])
        assert result.exit_code == 0

    def test_score_with_threshold(self, runner, leads_json_file, sample_settings, tmp_path):
        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["score", "--input", leads_json_file, "--threshold", "80"])
        assert result.exit_code == 0


class TestOutreachCommand:
    def test_outreach_cli(self, runner, leads_json_file, sample_settings, tmp_path):
        with patch("src.pipeline.generate_batch_outreach", side_effect=lambda leads, **kw: leads), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["outreach", "--input", leads_json_file])
        assert result.exit_code == 0


class TestReportCommand:
    def test_report_cli(self, runner, leads_json_file, tmp_path):
        with patch("src.pipeline.save_report", return_value=tmp_path / "report.html"):
            result = runner.invoke(cli, [
                "report", "--input", leads_json_file,
                "--vertical", "hvac", "--metro", "portland-or",
            ])
        assert result.exit_code == 0

    def test_report_no_vertical(self, runner, leads_json_file, tmp_path):
        with patch("src.pipeline.save_report", return_value=tmp_path / "report.html"):
            result = runner.invoke(cli, ["report", "--input", leads_json_file])
        assert result.exit_code == 0


class TestStatsCommand:
    def test_stats_with_data(self, runner):
        with patch("src.pipeline.get_stats", return_value={"enrich": 10, "score": 5}):
            result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "enrich" in result.output

    def test_stats_empty(self, runner):
        with patch("src.pipeline.get_stats", return_value={}):
            result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "No leads" in result.output


class TestRunCommand:
    def test_full_run(self, runner, sample_settings, tmp_path):
        mock_leads = [make_lead(id="r1", score=70.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.filter_new_leads", return_value=(mock_leads, 0)), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline.generate_batch_outreach", return_value=mock_leads), \
             patch("src.pipeline.save_report", return_value=tmp_path / "report.html"), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--count", "5", "--skip-dedup",
            ])
        assert result.exit_code == 0
        assert "Pipeline Complete" in result.output

    def test_run_no_leads_after_dedup(self, runner, sample_settings, tmp_path):
        mock_leads = [make_lead(id="r1")]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.filter_new_leads", return_value=([], 1)), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
            ])
        assert result.exit_code == 0
        assert "No new leads" in result.output

    def test_run_no_qualified_after_scoring(self, runner, sample_settings, tmp_path):
        mock_leads = [make_lead(id="r1", score=10.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or", "--skip-dedup",
            ])
        assert result.exit_code == 0
        assert "No leads above threshold" in result.output

    def test_run_with_push_instantly(self, runner, sample_settings, tmp_path):
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
             patch("src.pipeline.save_report", return_value=tmp_path / "report.html"), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--skip-dedup", "--push-instantly",
            ])
        assert result.exit_code == 0
        assert "camp_123" in result.output

    def test_run_with_dedup_skipping(self, runner, sample_settings, tmp_path):
        mock_leads = [make_lead(id="r1", score=70.0), make_lead(id="r2", score=60.0)]
        filtered = [mock_leads[0]]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.filter_new_leads", return_value=(filtered, 1)), \
             patch("src.pipeline.run_async_enrichment", return_value=filtered), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=filtered), \
             patch("src.pipeline.generate_batch_outreach", return_value=filtered), \
             patch("src.pipeline.save_report", return_value=tmp_path / "report.html"), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
            ])
        assert result.exit_code == 0
        assert "Skipped 1" in result.output


class TestRunNotify:
    def test_run_with_notify_sends_email(self, runner, sample_settings, tmp_path):
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
             patch("src.pipeline.save_report", return_value=tmp_path / "report.html"), \
             patch("src.pipeline.send_run_summary") as mock_send, \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--skip-dedup", "--notify",
            ])
        assert result.exit_code == 0
        mock_send.assert_called_once()

    def test_run_without_notify_skips_email(self, runner, sample_settings, tmp_path):
        mock_leads = [make_lead(id="n1", score=70.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.scrape_google_maps", return_value=mock_leads), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_leads), \
             patch("src.pipeline.mark_processed"), \
             patch("src.pipeline.score_leads", return_value=mock_leads), \
             patch("src.pipeline.generate_batch_outreach", return_value=mock_leads), \
             patch("src.pipeline.save_report", return_value=tmp_path / "report.html"), \
             patch("src.pipeline.send_run_summary") as mock_send, \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, [
                "run", "--vertical", "hvac", "--metro", "portland-or",
                "--skip-dedup",
            ])
        assert result.exit_code == 0
        mock_send.assert_not_called()


class TestReEnrichCommand:
    def test_re_enriches_stale_leads(self, runner, sample_settings, tmp_path):
        from datetime import datetime, timezone, timedelta
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        leads = [
            make_lead(id="stale1", score=60.0, enriched_at=old_date).model_dump(mode="json"),
        ]
        scored_dir = tmp_path / "scored"
        scored_dir.mkdir()
        (scored_dir / "test_scored.json").write_text(json.dumps(leads))

        sample_settings["schedule"] = {"re_enrich": {"max_age_days": 30}}

        mock_enriched = [make_lead(id="stale1", score=65.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_enriched), \
             patch("src.pipeline.score_leads", return_value=mock_enriched), \
             patch("src.pipeline.send_run_summary"), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0

    def test_skips_fresh_leads(self, runner, sample_settings, tmp_path):
        from datetime import datetime, timezone
        fresh_date = datetime.now(timezone.utc).isoformat()
        leads = [
            make_lead(id="fresh1", score=60.0, enriched_at=fresh_date).model_dump(mode="json"),
        ]
        scored_dir = tmp_path / "scored"
        scored_dir.mkdir()
        (scored_dir / "test_scored.json").write_text(json.dumps(leads))

        sample_settings["schedule"] = {"re_enrich": {"max_age_days": 30}}

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "No stale leads" in result.output

    def test_re_enrich_with_notify(self, runner, sample_settings, tmp_path):
        from datetime import datetime, timezone, timedelta
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        leads = [
            make_lead(id="s1", score=60.0, enriched_at=old_date).model_dump(mode="json"),
        ]
        scored_dir = tmp_path / "scored"
        scored_dir.mkdir()
        (scored_dir / "test_scored.json").write_text(json.dumps(leads))

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
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["re-enrich", "--notify"])
        assert result.exit_code == 0
        mock_send.assert_called_once()

    def test_re_enrich_naive_datetime(self, runner, sample_settings, tmp_path):
        """Naive datetime enriched_at should not cause TypeError vs UTC cutoff."""
        from datetime import datetime, timedelta
        # Naive datetime (no timezone info) — 45 days old
        old_date = (datetime.now() - timedelta(days=45)).isoformat()
        leads = [
            make_lead(id="naive1", score=60.0, enriched_at=old_date).model_dump(mode="json"),
        ]
        scored_dir = tmp_path / "scored"
        scored_dir.mkdir()
        (scored_dir / "test_scored.json").write_text(json.dumps(leads))

        sample_settings["schedule"] = {"re_enrich": {"max_age_days": 30}}
        mock_enriched = [make_lead(id="naive1", score=65.0)]

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.run_async_enrichment", return_value=mock_enriched), \
             patch("src.pipeline.score_leads", return_value=mock_enriched), \
             patch("src.pipeline.send_run_summary"), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "Re-enriching 1 stale leads" in result.output

    def test_re_enrich_empty_scored_dir(self, runner, sample_settings, tmp_path):
        scored_dir = tmp_path / "scored"
        scored_dir.mkdir()

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "No stale leads" in result.output or "No scored" in result.output


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
