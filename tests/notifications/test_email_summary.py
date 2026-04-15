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
