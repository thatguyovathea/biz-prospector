# Scheduled Pipeline Runs with Email Summary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate recurring pipeline runs via system cron and deliver weekly email briefings of outreach targets to the user's inbox.

**Architecture:** New `src/scheduler.py` manages crontab entries generated from YAML config. New `src/notifications/email_summary.py` composes and sends HTML digest emails via stdlib `smtplib`. Pipeline's `run` command gains `--notify` flag; new `re-enrich` command refreshes stale leads. New `schedule` Click group provides install/list/remove subcommands.

**Tech Stack:** Python stdlib (smtplib, email.mime, subprocess), Click CLI framework, crontab

---

### Task 1: Create email summary module with compose function

**Files:**
- Create: `src/notifications/__init__.py`
- Create: `src/notifications/email_summary.py`
- Create: `tests/notifications/__init__.py`
- Create: `tests/notifications/test_email_summary.py`

- [ ] **Step 1: Write failing tests for _get_smtp_config and compose_summary_html**

Create `tests/notifications/__init__.py` (empty file) and `tests/notifications/test_email_summary.py`:

```python
"""Tests for email summary notifications."""

import os
from unittest.mock import patch

from tests.conftest import make_lead

from src.notifications.email_summary import _get_smtp_config, compose_summary_html


class TestGetSmtpConfig:
    def test_reads_from_settings(self):
        settings = {
            "schedule": {
                "summary_email": {
                    "to": "user@example.com",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 465,
                    "smtp_user": "myuser",
                    "smtp_password": "mypass",
                    "subject_prefix": "[test]",
                }
            }
        }
        cfg = _get_smtp_config(settings)
        assert cfg["to"] == "user@example.com"
        assert cfg["host"] == "smtp.example.com"
        assert cfg["port"] == 465
        assert cfg["user"] == "myuser"
        assert cfg["password"] == "mypass"
        assert cfg["subject_prefix"] == "[test]"

    def test_falls_back_to_env_vars(self):
        settings = {"schedule": {"summary_email": {"to": "user@example.com"}}}
        with patch.dict(os.environ, {"BIZ_SMTP_USER": "envuser", "BIZ_SMTP_PASSWORD": "envpass"}):
            cfg = _get_smtp_config(settings)
        assert cfg["user"] == "envuser"
        assert cfg["password"] == "envpass"

    def test_defaults_when_empty(self):
        cfg = _get_smtp_config({})
        assert cfg["host"] == "smtp.gmail.com"
        assert cfg["port"] == 587
        assert cfg["to"] == ""
        assert cfg["user"] == ""
        assert cfg["subject_prefix"] == "[biz-prospector]"


class TestComposeSummaryHtml:
    def test_includes_lead_data(self):
        leads = [
            make_lead(business_name="Acme HVAC", score=78.5, contact_name="Bob",
                      contact_title="Owner", has_crm=False),
            make_lead(business_name="Portland Air", score=72.1, contact_name="Jane",
                      contact_title="CEO", has_scheduling=False),
        ]
        run_info = {
            "vertical": "hvac",
            "metro": "portland-or",
            "timestamp": "2026-04-14 06:00",
            "scraped_count": 87,
            "qualified_count": 2,
            "threshold": 55,
            "is_re_enrich": False,
        }
        html = compose_summary_html(leads, run_info)
        assert "Acme HVAC" in html
        assert "Portland Air" in html
        assert "78.5" in html
        assert "87" in html

    def test_re_enrich_label(self):
        leads = [make_lead(score=60.0)]
        run_info = {
            "vertical": "hvac",
            "metro": "portland-or",
            "timestamp": "2026-04-14",
            "scraped_count": 0,
            "qualified_count": 1,
            "threshold": 55,
            "is_re_enrich": True,
        }
        html = compose_summary_html(leads, run_info)
        assert "Re-enrichment" in html or "re-enrich" in html.lower()

    def test_empty_leads(self):
        run_info = {
            "vertical": "hvac",
            "metro": "portland-or",
            "timestamp": "2026-04-14",
            "scraped_count": 50,
            "qualified_count": 0,
            "threshold": 55,
            "is_re_enrich": False,
        }
        html = compose_summary_html([], run_info)
        assert "0" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/notifications/test_email_summary.py -v`
Expected: FAIL — `cannot import name '_get_smtp_config'`

- [ ] **Step 3: Implement _get_smtp_config and compose_summary_html**

Create `src/notifications/__init__.py` (empty file) and `src/notifications/email_summary.py`:

```python
"""Email summary notifications for scheduled pipeline runs.

Composes HTML digest emails with top leads and run stats,
sends via SMTP (stdlib smtplib — no external dependencies).
"""

from __future__ import annotations

import html as html_lib
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from rich.console import Console

from src.models import Lead

console = Console()


def _get_smtp_config(settings: dict) -> dict:
    """Get SMTP config from settings, with env var fallback."""
    email_cfg = settings.get("schedule", {}).get("summary_email", {})
    return {
        "host": email_cfg.get("smtp_host", "smtp.gmail.com"),
        "port": email_cfg.get("smtp_port", 587),
        "user": email_cfg.get("smtp_user") or os.environ.get("BIZ_SMTP_USER", ""),
        "password": email_cfg.get("smtp_password") or os.environ.get("BIZ_SMTP_PASSWORD", ""),
        "to": email_cfg.get("to", ""),
        "subject_prefix": email_cfg.get("subject_prefix", "[biz-prospector]"),
    }


def _build_signals(lead: Lead) -> str:
    """Build a short signal summary string for a lead."""
    signals = []
    if lead.has_crm is False:
        signals.append("No CRM")
    if lead.has_scheduling is False:
        signals.append("No scheduling")
    if lead.has_chat_widget is False:
        signals.append("No chat")
    if lead.manual_role_count > 0:
        signals.append(f"{lead.manual_role_count} manual roles")
    if lead.ops_complaint_count > 0:
        signals.append(f"{lead.ops_complaint_count} complaints")
    return ", ".join(signals) if signals else "—"


def compose_summary_html(leads: list[Lead], run_info: dict) -> str:
    """Compose an HTML email body summarizing a pipeline run."""
    vertical = run_info.get("vertical", "").upper()
    metro = run_info.get("metro", "")
    timestamp = run_info.get("timestamp", "")
    scraped = run_info.get("scraped_count", 0)
    qualified = run_info.get("qualified_count", len(leads))
    threshold = run_info.get("threshold", 55)
    is_re_enrich = run_info.get("is_re_enrich", False)

    run_type = "Re-enrichment Update" if is_re_enrich else "Run Summary"

    # Stats
    scores = [l.score for l in leads if l.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_score = max(scores) if scores else 0
    with_email = sum(1 for l in leads if l.contact_email)

    # Top 10 leads table rows
    top_leads = sorted(leads, key=lambda l: l.score or 0, reverse=True)[:10]
    rows = ""
    for lead in top_leads:
        score_str = f"{lead.score:.1f}" if lead.score else "—"
        name = html_lib.escape(lead.business_name[:30])
        contact = html_lib.escape(f"{lead.contact_name} ({lead.contact_title})" if lead.contact_name else "—")
        signals = html_lib.escape(_build_signals(lead))
        rows += f"<tr><td>{score_str}</td><td>{name}</td><td>{contact}</td><td>{signals}</td></tr>\n"

    return f"""<html>
<body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<h2>{run_type}: {vertical} {metro}</h2>
<p>
  <strong>Run time:</strong> {html_lib.escape(timestamp)}<br>
  <strong>Scraped:</strong> {scraped} |
  <strong>Qualified:</strong> {qualified} (threshold: {threshold})
</p>

<h3>Top Leads</h3>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">
<tr style="background: #f0f0f0;">
  <th>Score</th><th>Business</th><th>Contact</th><th>Signals</th>
</tr>
{rows if rows else '<tr><td colspan="4">No qualified leads this run.</td></tr>'}
</table>

<h3>Quick Stats</h3>
<p>
  Average score: {avg_score:.1f} | Highest: {max_score:.1f}<br>
  With contact email: {with_email}/{len(leads)}{f' ({with_email*100//len(leads)}%)' if leads else ''}<br>
</p>

<p style="color: #888; font-size: 12px;">Full report attached.</p>
</body>
</html>"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/notifications/test_email_summary.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/notifications/__init__.py src/notifications/email_summary.py \
        tests/notifications/__init__.py tests/notifications/test_email_summary.py
git commit -m "feat: add email summary compose and SMTP config"
```

---

### Task 2: Add send_run_summary with SMTP sending

**Files:**
- Modify: `src/notifications/email_summary.py`
- Modify: `tests/notifications/test_email_summary.py`

- [ ] **Step 1: Write failing tests for send_run_summary**

Append to `tests/notifications/test_email_summary.py`:

```python
import smtplib
from unittest.mock import MagicMock

from src.notifications.email_summary import send_run_summary


class TestSendRunSummary:
    def test_sends_email_with_attachment(self, tmp_path):
        leads = [make_lead(score=70.0, business_name="Acme")]
        run_info = {
            "vertical": "hvac", "metro": "portland-or",
            "timestamp": "2026-04-14", "scraped_count": 50,
            "qualified_count": 1, "threshold": 55, "is_re_enrich": False,
        }
        settings = {
            "schedule": {
                "summary_email": {
                    "enabled": True,
                    "to": "user@example.com",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_user": "myuser",
                    "smtp_password": "mypass",
                    "subject_prefix": "[test]",
                }
            }
        }
        report_path = tmp_path / "report.html"
        report_path.write_text("<html><body>Report</body></html>")

        mock_smtp = MagicMock()
        with patch("src.notifications.email_summary.smtplib.SMTP", return_value=mock_smtp):
            send_run_summary(leads, run_info, settings, report_path=report_path)

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("myuser", "mypass")
        mock_smtp.send_message.assert_called_once()
        mock_smtp.quit.assert_called_once()

    def test_skips_when_no_to_address(self):
        settings = {"schedule": {"summary_email": {"enabled": True, "to": ""}}}
        mock_smtp = MagicMock()
        with patch("src.notifications.email_summary.smtplib.SMTP", return_value=mock_smtp):
            send_run_summary([], {}, settings)
        mock_smtp.send_message.assert_not_called()

    def test_skips_when_disabled(self):
        settings = {"schedule": {"summary_email": {"enabled": False, "to": "user@test.com"}}}
        mock_smtp = MagicMock()
        with patch("src.notifications.email_summary.smtplib.SMTP", return_value=mock_smtp):
            send_run_summary([], {}, settings)
        mock_smtp.send_message.assert_not_called()

    def test_smtp_failure_does_not_crash(self):
        leads = [make_lead(score=70.0)]
        run_info = {
            "vertical": "hvac", "metro": "portland-or",
            "timestamp": "2026-04-14", "scraped_count": 50,
            "qualified_count": 1, "threshold": 55, "is_re_enrich": False,
        }
        settings = {
            "schedule": {
                "summary_email": {
                    "enabled": True,
                    "to": "user@example.com",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_user": "myuser",
                    "smtp_password": "mypass",
                }
            }
        }
        with patch("src.notifications.email_summary.smtplib.SMTP",
                    side_effect=smtplib.SMTPException("Connection refused")):
            # Should not raise
            send_run_summary(leads, run_info, settings)

    def test_sends_without_attachment_when_no_report(self):
        leads = [make_lead(score=70.0)]
        run_info = {
            "vertical": "hvac", "metro": "portland-or",
            "timestamp": "2026-04-14", "scraped_count": 50,
            "qualified_count": 1, "threshold": 55, "is_re_enrich": False,
        }
        settings = {
            "schedule": {
                "summary_email": {
                    "enabled": True,
                    "to": "user@example.com",
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_user": "u",
                    "smtp_password": "p",
                }
            }
        }
        mock_smtp = MagicMock()
        with patch("src.notifications.email_summary.smtplib.SMTP", return_value=mock_smtp):
            send_run_summary(leads, run_info, settings, report_path=None)
        mock_smtp.send_message.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/notifications/test_email_summary.py::TestSendRunSummary -v`
Expected: FAIL — `cannot import name 'send_run_summary'`

- [ ] **Step 3: Implement send_run_summary**

Append to `src/notifications/email_summary.py`:

```python
def send_run_summary(
    leads: list[Lead],
    run_info: dict,
    settings: dict,
    report_path: Path | None = None,
) -> None:
    """Send a summary email for a pipeline run.

    Silently skips if email is not configured or disabled.
    Catches all SMTP errors to avoid crashing the pipeline.
    """
    email_cfg = settings.get("schedule", {}).get("summary_email", {})
    if not email_cfg.get("enabled", False):
        return

    smtp_cfg = _get_smtp_config(settings)
    if not smtp_cfg["to"] or not smtp_cfg["user"]:
        console.print("  [yellow]Email notification skipped: missing to/user config[/]")
        return

    try:
        vertical = run_info.get("vertical", "").upper()
        metro = run_info.get("metro", "")
        qualified = run_info.get("qualified_count", len(leads))
        is_re_enrich = run_info.get("is_re_enrich", False)

        prefix = smtp_cfg["subject_prefix"]
        run_type = "Re-enrichment" if is_re_enrich else ""
        subject = f"{prefix} {vertical} {metro} — {qualified} targets {run_type}".strip()

        body_html = compose_summary_html(leads, run_info)

        msg = MIMEMultipart()
        msg["From"] = smtp_cfg["user"]
        msg["To"] = smtp_cfg["to"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        # Attach report if available
        if report_path and Path(report_path).exists():
            with open(report_path, "rb") as f:
                attachment = MIMEBase("text", "html")
                attachment.set_payload(f.read())
                encoders.encode_base64(attachment)
                attachment.add_header(
                    "Content-Disposition",
                    f"attachment; filename={Path(report_path).name}",
                )
                msg.attach(attachment)

        with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"]) as server:
            server.starttls()
            server.login(smtp_cfg["user"], smtp_cfg["password"])
            server.send_message(msg)

        console.print(f"  [green]Summary email sent to {smtp_cfg['to']}[/]")

    except Exception as e:
        console.print(f"  [yellow]Email notification failed: {e}[/]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/notifications/test_email_summary.py -v`
Expected: PASS (all 11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/notifications/email_summary.py tests/notifications/test_email_summary.py
git commit -m "feat: add send_run_summary for SMTP email notifications"
```

---

### Task 3: Create scheduler module for crontab management

**Files:**
- Create: `src/scheduler.py`
- Create: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_scheduler.py`:

```python
"""Tests for crontab scheduler management."""

import subprocess
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.scheduler'`

- [ ] **Step 3: Implement src/scheduler.py**

Create `src/scheduler.py`:

```python
"""Crontab scheduler management for biz-prospector.

Generates, installs, lists, and removes crontab entries
for scheduled pipeline runs.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()

MARKER = "# biz-prospector:"


def _validate_job(job: dict) -> list[str]:
    """Validate a job config dict. Returns list of error strings."""
    errors = []
    if not job.get("name"):
        errors.append("Job missing 'name'")
    if job.get("_type") != "re_enrich":
        if not job.get("vertical"):
            errors.append(f"Job '{job.get('name', '?')}' missing 'vertical'")
        if not job.get("metro"):
            errors.append(f"Job '{job.get('name', '?')}' missing 'metro'")
    cron = job.get("cron", "")
    if not cron or len(cron.split()) != 5:
        errors.append(f"Job '{job.get('name', '?')}' has invalid cron expression: '{cron}'")
    return errors


def _build_cron_entry(job: dict, python_path: str, project_dir: str) -> str:
    """Build a crontab entry string from a job config dict."""
    name = job["name"]
    cron = job["cron"]

    if job.get("_type") == "re_enrich":
        max_age = job.get("max_age_days", 30)
        cmd = f"{python_path} -m src.pipeline re-enrich --max-age {max_age} --notify"
    else:
        vertical = job["vertical"]
        metro = job["metro"]
        count = job.get("count", 100)
        cmd = f"{python_path} -m src.pipeline run --vertical {vertical} --metro {metro} --count {count} --notify"
        if job.get("push_instantly"):
            cmd += " --push-instantly"

    log_path = f"data/logs/{name}.log"
    return f"{MARKER}{name}\n{cron} cd {project_dir} && {cmd} >> {log_path} 2>&1"


def _read_crontab() -> str:
    """Read current user crontab."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def _write_crontab(content: str):
    """Write content to user crontab."""
    subprocess.run(
        ["crontab", "-"],
        input=content,
        text=True,
        check=True,
    )


def _strip_biz_entries(crontab: str) -> list[str]:
    """Remove all biz-prospector entries from crontab lines.

    Returns cleaned lines and count of removed entries.
    """
    lines = crontab.splitlines()
    cleaned = []
    skip_next = False
    removed = 0
    for line in lines:
        if line.startswith(MARKER):
            skip_next = True
            removed += 1
            continue
        if skip_next:
            skip_next = False
            continue
        cleaned.append(line)
    return cleaned, removed


def install_jobs(settings: dict) -> list[str]:
    """Generate and install crontab entries from settings.

    Returns list of installed job names.
    Raises ValueError if any job fails validation.
    """
    schedule = settings.get("schedule", {})
    jobs = list(schedule.get("jobs", []))

    # Add re-enrich job if enabled
    re_enrich = schedule.get("re_enrich", {})
    if re_enrich.get("enabled"):
        jobs.append({
            "name": "re-enrich",
            "cron": re_enrich.get("cron", "0 2 * * 0"),
            "max_age_days": re_enrich.get("max_age_days", 30),
            "_type": "re_enrich",
        })

    # Validate all jobs
    all_errors = []
    for job in jobs:
        errors = _validate_job(job)
        all_errors.extend(errors)
    if all_errors:
        raise ValueError(f"Job validation failed:\n" + "\n".join(all_errors))

    # Build entries
    python_path = sys.executable
    project_dir = str(Path.cwd())

    entries = []
    names = []
    for job in jobs:
        entries.append(_build_cron_entry(job, python_path, project_dir))
        names.append(job["name"])

    # Read existing crontab, strip old biz-prospector entries
    existing = _read_crontab()
    cleaned, _ = _strip_biz_entries(existing)

    # Build new crontab
    new_lines = cleaned + [""] + entries + [""]
    new_crontab = "\n".join(new_lines) + "\n"

    # Create log directory
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    _write_crontab(new_crontab)
    return names


def list_jobs() -> list[dict]:
    """Read crontab and return biz-prospector jobs."""
    crontab = _read_crontab()
    if not crontab:
        return []

    jobs = []
    lines = crontab.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(MARKER):
            name = line[len(MARKER):]
            # Next line is the cron entry
            if i + 1 < len(lines):
                cron_line = lines[i + 1]
                parts = cron_line.split(None, 5)
                schedule = " ".join(parts[:5]) if len(parts) >= 5 else cron_line
                jobs.append({"name": name, "schedule": schedule, "command": cron_line})
    return jobs


def remove_jobs() -> int:
    """Remove all biz-prospector entries from crontab.

    Returns count of removed entries.
    """
    existing = _read_crontab()
    if not existing:
        return 0

    cleaned, removed = _strip_biz_entries(existing)
    if removed > 0:
        _write_crontab("\n".join(cleaned) + "\n")
    return removed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS (all 17 tests)

- [ ] **Step 5: Commit**

```bash
git add src/scheduler.py tests/test_scheduler.py
git commit -m "feat: add crontab scheduler management module"
```

---

### Task 4: Add --notify flag to run command

**Files:**
- Modify: `src/pipeline.py:188-273`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py::TestRunNotify -v`
Expected: FAIL — `run` command has no `--notify` option

- [ ] **Step 3: Add --notify flag and email sending to run command**

In `src/pipeline.py`, add import at the top (after line 36):

```python
from src.notifications.email_summary import send_run_summary
```

Add the `--notify` option to the `run` command. Replace lines 188-204:

```python
@cli.command()
@click.option("--vertical", required=True)
@click.option("--metro", required=True)
@click.option("--count", default=100)
@click.option("--provider", default="serpapi", type=click.Choice(["serpapi", "apify"]))
@click.option("--concurrent", default=10, help="Max concurrent enrichment tasks")
@click.option("--skip-dedup", is_flag=True, help="Process all leads even if seen before")
@click.option("--push-instantly", is_flag=True, help="Push results to Instantly.ai")
@click.option("--notify", is_flag=True, help="Send summary email after completion")
def run(
    vertical: str,
    metro: str,
    count: int,
    provider: str,
    concurrent: int,
    skip_dedup: bool,
    push_instantly: bool,
    notify: bool,
):
```

Then at the end of the `run` function, before the final `console.rule("[bold green]Pipeline Complete")` (line 269), add:

```python
    # Email notification (for scheduled runs)
    if notify:
        run_info = {
            "vertical": vertical,
            "metro": metro,
            "timestamp": timestamp,
            "scraped_count": len(leads),
            "qualified_count": len(qualified),
            "threshold": threshold,
            "is_re_enrich": False,
        }
        send_run_summary(results, run_info, settings, report_path=report_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add --notify flag to run command for email summaries"
```

---

### Task 5: Add re-enrich command

**Files:**
- Modify: `src/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_pipeline.py`:

```python
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

    def test_re_enrich_empty_scored_dir(self, runner, sample_settings, tmp_path):
        scored_dir = tmp_path / "scored"
        scored_dir.mkdir()

        with patch("src.pipeline.load_settings", return_value=sample_settings), \
             patch("src.pipeline.DATA_DIR", tmp_path):
            result = runner.invoke(cli, ["re-enrich"])
        assert result.exit_code == 0
        assert "No stale leads" in result.output or "No scored" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline.py::TestReEnrichCommand -v`
Expected: FAIL — `No such command 're-enrich'`

- [ ] **Step 3: Implement re-enrich command**

In `src/pipeline.py`, add after the `stats` command (before `if __name__ == "__main__":`):

```python
@cli.command(name="re-enrich")
@click.option("--max-age", default=None, type=int, help="Override max_age_days from config")
@click.option("--notify", is_flag=True, help="Send summary email after completion")
def re_enrich(max_age: int | None, notify: bool):
    """Re-enrich and re-score stale leads."""
    settings = load_settings()
    max_age_days = max_age or settings.get("schedule", {}).get(
        "re_enrich", {}
    ).get("max_age_days", 30)

    scored_dir = DATA_DIR / "scored"
    if not scored_dir.exists():
        console.print("[yellow]No scored leads directory found.[/]")
        return

    # Load all scored leads grouped by source file
    from datetime import timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale_by_file: dict[Path, list[Lead]] = {}

    for json_file in sorted(scored_dir.glob("*.json")):
        leads = _load_leads(str(json_file))
        stale = []
        for lead in leads:
            if lead.enriched_at:
                if isinstance(lead.enriched_at, str):
                    enriched_dt = datetime.fromisoformat(lead.enriched_at)
                else:
                    enriched_dt = lead.enriched_at
                if enriched_dt < cutoff:
                    stale.append(lead)
            else:
                stale.append(lead)
        if stale:
            stale_by_file[json_file] = stale

    total_stale = sum(len(v) for v in stale_by_file.values())
    if total_stale == 0:
        console.print("[yellow]No stale leads to re-enrich.[/]")
        return

    console.print(f"[bold]Re-enriching {total_stale} stale leads from {len(stale_by_file)} files[/]")

    all_refreshed = []
    for json_file, stale_leads in stale_by_file.items():
        console.rule(f"[blue]{json_file.name}")
        enriched = run_async_enrichment(stale_leads)
        scored = score_leads(enriched)
        all_refreshed.extend(scored)

        # Save back to source file
        _save_json(scored, "scored", json_file.name)

    console.rule("[bold green]Re-enrichment Complete")
    console.print(f"Refreshed {len(all_refreshed)} leads")

    if notify:
        run_info = {
            "vertical": "all",
            "metro": "all",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "scraped_count": 0,
            "qualified_count": len(all_refreshed),
            "threshold": settings.get("pipeline", {}).get("score_threshold", 55),
            "is_re_enrich": True,
        }
        send_run_summary(all_refreshed, run_info, settings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add re-enrich command for refreshing stale leads"
```

---

### Task 6: Add schedule CLI subcommands

**Files:**
- Modify: `src/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_pipeline.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline.py::TestScheduleCommands -v`
Expected: FAIL — `No such command 'schedule'`

- [ ] **Step 3: Add schedule group and subcommands**

In `src/pipeline.py`, add import after the `send_run_summary` import:

```python
from src.scheduler import install_jobs, list_jobs, remove_jobs
```

Then add after the `re_enrich` command (before `if __name__ == "__main__":`):

```python
@cli.group()
def schedule():
    """Manage scheduled pipeline runs (cron jobs)."""
    pass


@schedule.command(name="install")
def schedule_install():
    """Install cron jobs from settings.yaml schedule config."""
    settings = load_settings()
    try:
        names = install_jobs(settings)
        if names:
            console.print(f"[green]Installed {len(names)} scheduled jobs:[/]")
            for name in names:
                console.print(f"  • {name}")
        else:
            console.print("[yellow]No jobs configured in settings.yaml[/]")
    except ValueError as e:
        console.print(f"[red]{e}[/]")


@schedule.command(name="list")
def schedule_list():
    """List installed biz-prospector cron jobs."""
    jobs = list_jobs()
    if not jobs:
        console.print("No scheduled jobs found.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("Job", style="cyan")
    table.add_column("Schedule")
    for job in jobs:
        table.add_row(job["name"], job["schedule"])
    console.print(table)


@schedule.command(name="remove")
def schedule_remove():
    """Remove all biz-prospector cron jobs."""
    if not click.confirm("Remove all scheduled biz-prospector jobs?"):
        return
    count = remove_jobs()
    if count > 0:
        console.print(f"[green]Removed {count} scheduled job(s)[/]")
    else:
        console.print("No scheduled jobs to remove.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: add schedule install/list/remove CLI commands"
```

---

### Task 7: Update config and documentation

**Files:**
- Modify: `config/settings.example.yaml`
- Modify: `FEATURES.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update settings.example.yaml**

Append after the last line (line 113) of `config/settings.example.yaml`:

```yaml

schedule:
  # Prospecting jobs — each becomes a crontab entry
  # Run 'python -m src.pipeline schedule install' after configuring
  jobs: []
    # Example:
    # - name: "hvac-portland"
    #   vertical: hvac
    #   metro: portland-or
    #   cron: "0 6 * * 1"         # Every Monday at 6am
    #   count: 100
    #   push_instantly: false

  # Re-enrichment of stale leads
  re_enrich:
    enabled: false
    cron: "0 2 * * 0"             # Every Sunday at 2am
    max_age_days: 30

  # Email notification after scheduled runs
  summary_email:
    enabled: false
    to: ""
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: ""                  # Or set env var BIZ_SMTP_USER
    smtp_password: ""              # Or set env var BIZ_SMTP_PASSWORD
    subject_prefix: "[biz-prospector]"
```

- [ ] **Step 2: Update FEATURES.md**

In `FEATURES.md`, add under `## Pipeline`:

```markdown
- **Scheduled runs** — Cron-based automation with install/list/remove management
- **Re-enrichment** — Refresh stale leads (older than N days) with updated data
- **Email summaries** — HTML digest of top leads sent after each scheduled run
```

- [ ] **Step 3: Update CHANGELOG.md**

In `CHANGELOG.md`, add under `## [Unreleased]` → `### Added`:

```markdown
- Scheduled pipeline runs via crontab (schedule install/list/remove commands)
- Re-enrich command for refreshing stale scored leads
- Email summary notifications after scheduled runs (SMTP, HTML digest with report attachment)
```

- [ ] **Step 4: Commit**

```bash
git add config/settings.example.yaml FEATURES.md CHANGELOG.md
git commit -m "docs: add schedule config, features, and changelog entries"
```

---

### Task 8: Run full test suite and verify coverage

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest --cov=src --cov-branch -q`
Expected: All tests pass, coverage remains high.

- [ ] **Step 2: Check for any missed coverage**

Run: `python -m pytest --cov=src --cov-branch --cov-report=term-missing -q 2>&1 | grep -E "FAIL|scheduler|email_summary|pipeline"`
Expected: New modules have good coverage. `src/scheduler.py` and `src/notifications/email_summary.py` at 90%+.

- [ ] **Step 3: Run validation scripts**

Run: `bash scripts/validate.sh`
Expected: All checks PASS.

Run: `bash scripts/check-phase-gate.sh`
Expected: Phase gate PASSED.

- [ ] **Step 4: Commit if any fixes were needed**

If any tests failed or coverage dropped, fix and commit. Otherwise, no commit needed.
