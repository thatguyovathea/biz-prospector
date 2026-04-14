"""Shared test fixtures for biz-prospector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models import Lead, LeadSource


def make_lead(**overrides) -> Lead:
    """Factory function to create a Lead with realistic defaults.

    Any field can be overridden via kwargs.
    """
    defaults = {
        "id": "abc123def456",
        "business_name": "Acme HVAC Services",
        "address": "123 Main St, Portland, OR 97201",
        "phone": "(503) 555-0100",
        "website": "https://acmehvac.com",
        "category": "HVAC",
        "metro": "portland-or",
        "source": LeadSource.GOOGLE_MAPS,
        "rating": 4.2,
        "review_count": 85,
        "place_id": "ChIJ_test_place_id",
        "tech_stack": [],
        "has_crm": None,
        "has_chat_widget": None,
        "has_scheduling": None,
        "has_ssl": None,
        "is_mobile_responsive": None,
        "reviews_analyzed": 0,
        "ops_complaint_count": 0,
        "ops_complaint_samples": [],
        "owner_response_rate": None,
        "active_job_postings": 0,
        "manual_process_postings": 0,
        "manual_process_titles": [],
        "contact_name": "",
        "contact_email": "",
        "contact_title": "",
        "score": None,
        "score_breakdown": {},
        "outreach_email": "",
        "followups": [],
    }
    defaults.update(overrides)
    return Lead(**defaults)


@pytest.fixture
def sample_lead():
    """Fixture that returns the make_lead factory."""
    return make_lead


@pytest.fixture
def sample_settings():
    """Minimal settings dict with fake API keys."""
    return {
        "apis": {
            "serpapi_key": "fake-serpapi-key",
            "apify_token": "fake-apify-token",
            "outscraper_key": "fake-outscraper-key",
            "apollo_key": "fake-apollo-key",
            "hunter_key": "fake-hunter-key",
            "anthropic_key": "fake-anthropic-key",
            "instantly_key": "fake-instantly-key",
            "builtwith_key": "fake-builtwith-key",
        },
        "pipeline": {
            "batch_size": 100,
            "score_threshold": 55,
            "daily_send_limit": 50,
        },
        "scoring": {
            "weights": {
                "website_outdated": 20,
                "no_crm_detected": 15,
                "no_scheduling_tool": 10,
                "no_chat_widget": 5,
                "manual_job_postings": 25,
                "negative_reviews_ops": 15,
                "business_age": 5,
                "employee_count": 5,
            },
            "manual_process_keywords": [
                "data entry",
                "filing",
                "receptionist",
                "spreadsheet",
            ],
            "ops_complaint_keywords": [
                "never called back",
                "disorganized",
                "hard to reach",
            ],
        },
        "outreach": {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "followup_count": 2,
            "followup_interval_days": 3,
        },
    }


@pytest.fixture
def sample_vertical_config():
    """Returns a known HVAC vertical config dict."""
    return {
        "name": "hvac",
        "weights": {
            "website_outdated": 15,
            "no_crm_detected": 15,
            "no_scheduling_tool": 20,
            "no_chat_widget": 5,
            "manual_job_postings": 20,
            "negative_reviews_ops": 20,
            "business_age": 5,
        },
        "extra_manual_keywords": ["dispatch", "work orders"],
        "extra_complaint_keywords": ["no show", "missed appointment"],
    }


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create an isolated temp data directory structure."""
    dedup_dir = tmp_path / "data" / ".dedup"
    dedup_dir.mkdir(parents=True)
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    return tmp_path


def build_html(
    techs: list[str] | None = None,
    has_crm: str | None = None,
    has_chat: str | None = None,
    has_scheduling: str | None = None,
    has_viewport: bool = True,
    outdated: list[str] | None = None,
) -> str:
    """Build fake HTML with specific technology markers."""
    head_parts = []
    body_parts = []

    if has_viewport:
        head_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')

    tech_markers = {
        "wordpress": '<link rel="stylesheet" href="/wp-content/themes/flavor=starter/style.css">',
        "wix": '<script src="https://static.wix.com/script.js"></script>',
        "squarespace": '<script src="https://static.squarespace.com/script.js"></script>',
        "shopify": '<script src="https://cdn.shopify.com/s/files/script.js"></script>',
        "webflow": '<script src="https://assets.webflow.com/script.js"></script>',
        "google_analytics": '<script async src="https://www.google-analytics.com/analytics.js"></script>',
        "google_tag_manager": '<script src="https://www.googletagmanager.com/gtm.js"></script>',
        "facebook_pixel": '<script src="https://connect.facebook.net/en_US/fbevents.js"></script>',
        "bootstrap": '<link rel="stylesheet" href="bootstrap.min.css">',
        "tailwind": '<link rel="stylesheet" href="tailwindcss.css">',
        "react": '<script src="react.production.min.js"></script>',
        "angular": '<script src="angular.min.js"></script><div ng-version="16"></div>',
        "vue": '<script src="vue.min.js"></script>',
    }
    for tech in (techs or []):
        if tech in tech_markers:
            body_parts.append(tech_markers[tech])

    crm_markers = {
        "hubspot": '<script src="https://js.hs-scripts.com/hubspot/tracker.js"></script>',
        "salesforce": '<script src="https://cdn.salesforce.com/script.js"></script>',
        "pipedrive": '<script src="https://pipedrive.com/widget.js"></script>',
        "zoho": '<script src="https://crm.zoho.com/script.js"></script>',
        "freshsales": '<script src="https://freshsales.io/widget.js"></script>',
        "keap": '<script src="https://app.keap.com/script.js"></script>',
        "infusionsoft": '<script src="https://infusionsoft.com/app/form.js"></script>',
        "activecampaign": '<script src="https://activecampaign.com/f/embed.js"></script>',
    }
    if has_crm and has_crm in crm_markers:
        body_parts.append(crm_markers[has_crm])

    chat_markers = {
        "intercom": '<script src="https://widget.intercom.io/widget/abc"></script>',
        "drift": '<script src="https://js.driftt.com/drift.js"></script>',
        "crisp": '<script src="https://client.crisp.chat/l.js"></script>',
        "tawk": '<script src="https://embed.tawk.to/script.js"></script>',
        "livechat": '<script src="https://cdn.livechat.com/widget.js"></script>',
        "zendesk": '<script src="https://static.zdassets.com/zendesk/widget.js"></script>',
        "freshchat": '<script src="https://wchat.freshchat.com/js/widget.js"></script>',
        "tidio": '<script src="https://code.tidio.co/script.js"></script>',
        "chatwoot": '<script src="https://app.chatwoot.com/packs/js/sdk.js"></script>',
    }
    if has_chat and has_chat in chat_markers:
        body_parts.append(chat_markers[has_chat])

    sched_markers = {
        "calendly": '<script src="https://assets.calendly.com/assets/external/widget.js"></script>',
        "acuity": '<script src="https://embed.acuityscheduling.com/js/embed.js"></script>',
        "cal.com": '<script src="https://app.cal.com/embed/embed.js"></script>',
        "square_appointments": '<script src="https://square.site/appointments/widget.js"></script>',
        "booksy": '<script src="https://booksy.com/widget/script.js"></script>',
        "vagaro": '<script src="https://www.vagaro.com/widget.js"></script>',
        "setmore": '<script src="https://my.setmore.com/widget.js"></script>',
    }
    if has_scheduling and has_scheduling in sched_markers:
        body_parts.append(sched_markers[has_scheduling])

    outdated_markers = {
        "legacy_jquery": '<script src="jquery.min.js?ver=1.12.4"></script>',
        "old_wordpress": '<meta name="generator" content="WordPress 3.9">',
        "frameset": "<frameset><frame src='page1.html'></frameset>",
        "marquee": "<marquee>Welcome to our site!</marquee>",
        "blink": "<blink>SALE!</blink>",
        "flash": '<object data="intro.swf" type="application/x-shockwave-flash"></object>',
    }
    for signal in (outdated or []):
        if signal in outdated_markers:
            body_parts.append(outdated_markers[signal])

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    {''.join(head_parts)}
</head>
<body>
    {''.join(body_parts)}
</body>
</html>"""
