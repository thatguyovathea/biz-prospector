"""Tests for crontab scheduler management."""

from unittest.mock import patch, MagicMock

import pytest

from src.scheduler import (
    _build_cron_entry,
    _read_crontab,
    _write_crontab,
    _validate_job,
    install_jobs,
    list_jobs,
    remove_jobs,
)


class TestBuildCronEntry:
    def test_basic_job(self):
        job = {
            "name": "hvac-portland",
            "vertical": "hvac",
            "metro": "portland-or",
            "cron": "0 6 * * 1",
            "count": 100,
        }
        entry = _build_cron_entry(job, "/usr/bin/python", "/home/user/biz-prospector")
        assert "# biz-prospector:hvac-portland" in entry
        assert "0 6 * * 1" in entry
        assert "--vertical hvac" in entry
        assert "--metro portland-or" in entry
        assert "--count 100" in entry
        assert "--notify" in entry
        assert "/usr/bin/python -m src.pipeline run" in entry
        assert ">> data/logs/hvac-portland.log 2>&1" in entry

    def test_push_instantly_flag(self):
        job = {
            "name": "dental-push",
            "vertical": "dental",
            "metro": "seattle-wa",
            "cron": "0 8 * * 2",
            "count": 50,
            "push_instantly": True,
        }
        entry = _build_cron_entry(job, "/usr/bin/python", "/home/user/proj")
        assert "--push-instantly" in entry

    def test_re_enrich_entry(self):
        job = {
            "name": "re-enrich",
            "cron": "0 2 * * 0",
            "max_age_days": 30,
            "_type": "re_enrich",
        }
        entry = _build_cron_entry(job, "/usr/bin/python", "/home/user/proj")
        assert "re-enrich" in entry
        assert "--max-age 30" in entry
        assert "--notify" in entry


class TestValidateJob:
    def test_valid_job(self):
        job = {"name": "test", "vertical": "hvac", "metro": "portland-or", "cron": "0 6 * * 1"}
        errors = _validate_job(job)
        assert errors == []

    def test_missing_name(self):
        job = {"vertical": "hvac", "metro": "portland-or", "cron": "0 6 * * 1"}
        errors = _validate_job(job)
        assert any("name" in e for e in errors)

    def test_missing_vertical(self):
        job = {"name": "test", "metro": "portland-or", "cron": "0 6 * * 1"}
        errors = _validate_job(job)
        assert any("vertical" in e for e in errors)

    def test_bad_cron_format(self):
        job = {"name": "test", "vertical": "hvac", "metro": "portland-or", "cron": "bad"}
        errors = _validate_job(job)
        assert any("cron" in e for e in errors)

    def test_cron_five_fields(self):
        job = {"name": "test", "vertical": "hvac", "metro": "portland-or", "cron": "0 6 * *"}
        errors = _validate_job(job)
        assert any("cron" in e for e in errors)


class TestReadWriteCrontab:
    def test_read_crontab(self):
        mock_result = MagicMock(stdout="* * * * * echo hello\n", returncode=0)
        with patch("src.scheduler.subprocess.run", return_value=mock_result):
            content = _read_crontab()
        assert "echo hello" in content

    def test_read_crontab_empty(self):
        mock_result = MagicMock(stdout="", returncode=0)
        with patch("src.scheduler.subprocess.run", return_value=mock_result):
            content = _read_crontab()
        assert content == ""

    def test_read_crontab_no_crontab(self):
        mock_result = MagicMock(stdout="", returncode=1, stderr="no crontab for user")
        with patch("src.scheduler.subprocess.run", return_value=mock_result):
            content = _read_crontab()
        assert content == ""

    def test_write_crontab(self):
        with patch("src.scheduler.subprocess.run") as mock_run:
            _write_crontab("* * * * * echo test\n")
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["crontab", "-"]
        assert "echo test" in call_args[1]["input"]


class TestInstallJobs:
    def test_installs_jobs(self):
        settings = {
            "schedule": {
                "jobs": [
                    {"name": "hvac-portland", "vertical": "hvac",
                     "metro": "portland-or", "cron": "0 6 * * 1", "count": 100},
                ],
                "re_enrich": {"enabled": False},
            }
        }
        with patch("src.scheduler._read_crontab", return_value=""), \
             patch("src.scheduler._write_crontab") as mock_write, \
             patch("src.scheduler.sys") as mock_sys, \
             patch("src.scheduler.Path") as mock_path:
            mock_sys.executable = "/usr/bin/python"
            mock_path.cwd.return_value = "/home/user/proj"
            names = install_jobs(settings)

        assert names == ["hvac-portland"]
        mock_write.assert_called_once()
        written = mock_write.call_args[0][0]
        assert "biz-prospector:hvac-portland" in written

    def test_installs_with_re_enrich(self):
        settings = {
            "schedule": {
                "jobs": [
                    {"name": "test", "vertical": "hvac",
                     "metro": "portland-or", "cron": "0 6 * * 1"},
                ],
                "re_enrich": {"enabled": True, "cron": "0 2 * * 0", "max_age_days": 30},
            }
        }
        with patch("src.scheduler._read_crontab", return_value=""), \
             patch("src.scheduler._write_crontab") as mock_write, \
             patch("src.scheduler.sys") as mock_sys, \
             patch("src.scheduler.Path") as mock_path:
            mock_sys.executable = "/usr/bin/python"
            mock_path.cwd.return_value = "/home/user/proj"
            names = install_jobs(settings)

        assert "test" in names
        assert "re-enrich" in names
        written = mock_write.call_args[0][0]
        assert "biz-prospector:re-enrich" in written

    def test_replaces_existing_entries(self):
        existing = "# biz-prospector:old-job\n0 0 * * * old command\n# other stuff\n* * * * * keep this\n"
        settings = {
            "schedule": {
                "jobs": [{"name": "new", "vertical": "hvac",
                          "metro": "portland-or", "cron": "0 6 * * 1"}],
                "re_enrich": {"enabled": False},
            }
        }
        with patch("src.scheduler._read_crontab", return_value=existing), \
             patch("src.scheduler._write_crontab") as mock_write, \
             patch("src.scheduler.sys") as mock_sys, \
             patch("src.scheduler.Path") as mock_path:
            mock_sys.executable = "/usr/bin/python"
            mock_path.cwd.return_value = "/home/user/proj"
            install_jobs(settings)

        written = mock_write.call_args[0][0]
        assert "old-job" not in written
        assert "old command" not in written
        assert "keep this" in written
        assert "biz-prospector:new" in written

    def test_rejects_invalid_job(self):
        settings = {
            "schedule": {
                "jobs": [{"name": "", "vertical": "hvac", "metro": "portland-or", "cron": "0 6 * * 1"}],
                "re_enrich": {"enabled": False},
            }
        }
        with pytest.raises(ValueError, match="validation"):
            install_jobs(settings)


class TestListJobs:
    def test_lists_biz_prospector_jobs(self):
        crontab = (
            "# biz-prospector:hvac-portland\n"
            "0 6 * * 1 cd /proj && python -m src.pipeline run --vertical hvac\n"
            "* * * * * some other job\n"
            "# biz-prospector:dental-seattle\n"
            "0 6 * * 3 cd /proj && python -m src.pipeline run --vertical dental\n"
        )
        with patch("src.scheduler._read_crontab", return_value=crontab):
            jobs = list_jobs()
        assert len(jobs) == 2
        assert jobs[0]["name"] == "hvac-portland"
        assert jobs[0]["schedule"] == "0 6 * * 1"
        assert jobs[1]["name"] == "dental-seattle"

    def test_empty_crontab(self):
        with patch("src.scheduler._read_crontab", return_value=""):
            jobs = list_jobs()
        assert jobs == []


class TestRemoveJobs:
    def test_removes_only_biz_prospector_entries(self):
        crontab = (
            "# biz-prospector:hvac-portland\n"
            "0 6 * * 1 cd /proj && python run\n"
            "* * * * * keep this\n"
            "# biz-prospector:dental\n"
            "0 6 * * 3 cd /proj && python run\n"
        )
        with patch("src.scheduler._read_crontab", return_value=crontab), \
             patch("src.scheduler._write_crontab") as mock_write:
            count = remove_jobs()
        assert count == 2
        written = mock_write.call_args[0][0]
        assert "biz-prospector" not in written
        assert "keep this" in written

    def test_remove_nothing(self):
        with patch("src.scheduler._read_crontab", return_value="* * * * * other\n"), \
             patch("src.scheduler._write_crontab") as mock_write:
            count = remove_jobs()
        assert count == 0
