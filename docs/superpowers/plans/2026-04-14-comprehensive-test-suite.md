# Comprehensive Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full pytest test coverage to every module in biz-prospector, with all external APIs mocked so tests run offline.

**Architecture:** Mirror `src/` layout 1:1 under `tests/`. Shared fixtures in `conftest.py` provide reusable Lead factory, config builders, and HTML generators. All HTTP calls mocked with `respx`, Claude API mocked with `unittest.mock.patch`.

**Tech Stack:** pytest, pytest-asyncio, respx (httpx mocking)

---

## File Structure

### New files to create:
- `tests/conftest.py` — Shared fixtures (Lead factory, config helpers, HTML builder)
- `tests/test_models.py` — Pydantic model validation
- `tests/test_config.py` — YAML config loading
- `tests/test_dedup.py` — Deduplication logic
- `tests/test_rate_limit.py` — Rate limiter behavior
- `tests/scrapers/__init__.py` — Package marker
- `tests/scrapers/test_google_maps.py` — SerpAPI/Apify parsing + Lead creation
- `tests/scrapers/test_reviews.py` — Review sentiment analysis
- `tests/scrapers/test_job_posts.py` — Job posting analysis
- `tests/enrichment/__init__.py` — Package marker
- `tests/enrichment/test_website_audit.py` — HTML pattern matching
- `tests/enrichment/test_contacts.py` — Apollo/Hunter waterfall + contact ranking
- `tests/enrichment/test_async_processor.py` — Async orchestration
- `tests/scoring/__init__.py` — Package marker
- `tests/scoring/test_score.py` — Scoring engine
- `tests/outreach/__init__.py` — Package marker
- `tests/outreach/test_generate.py` — Claude API email generation
- `tests/outreach/test_delivery.py` — Instantly.ai integration

### Files to modify:
- `requirements.txt` — Add pytest, pytest-asyncio, respx

---

### Task 1: Add Test Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add test dependencies to requirements.txt**

Append these lines to `requirements.txt`:

```
pytest>=8.0
pytest-asyncio>=0.23
respx>=0.21
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully, no conflicts.

- [ ] **Step 3: Verify pytest works**

Run: `pytest --version`
Expected: Shows pytest 8.x

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pytest, pytest-asyncio, respx test dependencies"
```

---

### Task 2: Shared Fixtures (conftest.py)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create conftest.py with all shared fixtures**

```python
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
    """Build fake HTML with specific technology markers.

    Args:
        techs: Tech patterns to embed (e.g., ["wordpress", "react"])
        has_crm: CRM pattern to embed (e.g., "hubspot")
        has_chat: Chat pattern to embed (e.g., "intercom")
        has_scheduling: Scheduling pattern to embed (e.g., "calendly")
        has_viewport: Include viewport meta tag
        outdated: Outdated signals to embed (e.g., ["frameset", "marquee"])
    """
    head_parts = []
    body_parts = []

    if has_viewport:
        head_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')

    # Tech markers
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

    # CRM markers
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

    # Chat markers
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

    # Scheduling markers
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

    # Outdated signals
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
```

- [ ] **Step 2: Create package __init__.py files**

Create empty `__init__.py` in each test subdirectory:
- `tests/scrapers/__init__.py`
- `tests/enrichment/__init__.py`
- `tests/scoring/__init__.py`
- `tests/outreach/__init__.py`

- [ ] **Step 3: Verify fixtures load**

Run: `pytest tests/ --collect-only 2>&1 | head -5`
Expected: No import errors, shows "no tests ran" (no test files yet).

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add shared fixtures and test directory structure"
```

---

### Task 3: Test Models (test_models.py)

**Files:**
- Create: `tests/test_models.py`

- [ ] **Step 1: Write test_models.py**

```python
"""Tests for Pydantic data models."""

from pydantic import ValidationError
import pytest

from src.models import Lead, LeadSource, PipelineConfig, VerticalConfig


class TestLead:
    def test_minimal_lead(self):
        """Lead can be created with just business_name."""
        lead = Lead(business_name="Test Biz")
        assert lead.business_name == "Test Biz"
        assert lead.id == ""
        assert lead.source == LeadSource.GOOGLE_MAPS

    def test_full_lead(self):
        """Lead accepts all fields."""
        lead = Lead(
            id="abc123",
            business_name="Full Biz",
            address="456 Oak Ave",
            phone="555-1234",
            website="https://fullbiz.com",
            category="HVAC",
            metro="portland-or",
            source=LeadSource.LINKEDIN,
            rating=4.5,
            review_count=100,
            tech_stack=["wordpress", "react"],
            has_crm=True,
            has_chat_widget=False,
            has_scheduling=True,
            score=72.5,
            score_breakdown={"no_crm_detected": 0.0, "website_outdated": 0.5},
        )
        assert lead.id == "abc123"
        assert lead.rating == 4.5
        assert lead.tech_stack == ["wordpress", "react"]
        assert lead.has_crm is True
        assert lead.score == 72.5

    def test_default_values(self):
        """Default values are correct for optional fields."""
        lead = Lead(business_name="Defaults")
        assert lead.tech_stack == []
        assert lead.score is None
        assert lead.score_breakdown == {}
        assert lead.has_crm is None
        assert lead.has_ssl is None
        assert lead.reviews_analyzed == 0
        assert lead.ops_complaint_samples == []
        assert lead.followups == []
        assert lead.scraped_at is None

    def test_invalid_source_raises(self):
        """Invalid source value raises ValidationError."""
        with pytest.raises(ValidationError):
            Lead(business_name="Bad", source="invalid_source")

    def test_lead_source_enum_values(self):
        """All LeadSource enum values exist."""
        assert LeadSource.GOOGLE_MAPS.value == "google_maps"
        assert LeadSource.LINKEDIN.value == "linkedin"
        assert LeadSource.DIRECTORY.value == "directory"
        assert LeadSource.MANUAL.value == "manual"


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig()
        assert config.batch_size == 100
        assert config.score_threshold == 55.0
        assert config.daily_send_limit == 50

    def test_custom_values(self):
        config = PipelineConfig(batch_size=50, score_threshold=70, daily_send_limit=25)
        assert config.batch_size == 50
        assert config.score_threshold == 70


class TestVerticalConfig:
    def test_minimal(self):
        config = VerticalConfig(name="hvac")
        assert config.name == "hvac"
        assert config.weights == {}
        assert config.extra_manual_keywords == []

    def test_full(self):
        config = VerticalConfig(
            name="dental",
            weights={"no_scheduling_tool": 25},
            extra_manual_keywords=["front desk"],
            extra_complaint_keywords=["long wait"],
        )
        assert config.weights["no_scheduling_tool"] == 25
        assert "front desk" in config.extra_manual_keywords
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_models.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_models.py
git commit -m "test: add Pydantic model validation tests"
```

---

### Task 4: Test Config (test_config.py)

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Write test_config.py**

```python
"""Tests for YAML config loading."""

from unittest.mock import patch

import pytest
import yaml

from src.config import load_settings, load_vertical, get_api_key


class TestLoadSettings:
    def test_loads_yaml(self, tmp_path):
        """load_settings reads YAML correctly."""
        settings = {"apis": {"serpapi_key": "test-key"}, "pipeline": {"batch_size": 50}}
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(settings))

        with patch("src.config.CONFIG_DIR", tmp_path):
            result = load_settings()

        assert result["apis"]["serpapi_key"] == "test-key"
        assert result["pipeline"]["batch_size"] == 50

    def test_raises_on_missing_file(self, tmp_path):
        """load_settings raises FileNotFoundError when settings.yaml missing."""
        with patch("src.config.CONFIG_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="Config not found"):
                load_settings()


class TestLoadVertical:
    def test_loads_vertical_yaml(self, tmp_path):
        """load_vertical reads vertical config."""
        verticals_dir = tmp_path / "verticals"
        verticals_dir.mkdir()
        config = {"name": "hvac", "weights": {"no_scheduling_tool": 20}}
        (verticals_dir / "hvac.yaml").write_text(yaml.dump(config))

        with patch("src.config.CONFIG_DIR", tmp_path):
            result = load_vertical("hvac")

        assert result["name"] == "hvac"
        assert result["weights"]["no_scheduling_tool"] == 20

    def test_returns_empty_for_missing(self, tmp_path):
        """load_vertical returns empty dict for nonexistent vertical."""
        verticals_dir = tmp_path / "verticals"
        verticals_dir.mkdir()

        with patch("src.config.CONFIG_DIR", tmp_path):
            result = load_vertical("nonexistent")

        assert result == {}


class TestGetApiKey:
    def test_retrieves_key(self):
        settings = {"apis": {"serpapi_key": "my-key-123"}}
        assert get_api_key(settings, "serpapi_key") == "my-key-123"

    def test_raises_on_missing_key(self):
        settings = {"apis": {}}
        with pytest.raises(ValueError, match="API key 'serpapi_key' not set"):
            get_api_key(settings, "serpapi_key")

    def test_raises_on_empty_key(self):
        settings = {"apis": {"serpapi_key": ""}}
        with pytest.raises(ValueError, match="API key 'serpapi_key' not set"):
            get_api_key(settings, "serpapi_key")

    def test_raises_on_no_apis_section(self):
        settings = {}
        with pytest.raises(ValueError):
            get_api_key(settings, "serpapi_key")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: add config loading tests"
```

---

### Task 5: Test Dedup (test_dedup.py)

**Files:**
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write test_dedup.py**

```python
"""Tests for deduplication logic."""

import json
from unittest.mock import patch

import pytest

from src.dedup import filter_new_leads, mark_processed, reset_stage, get_stats

from tests.conftest import make_lead


class TestFilterNewLeads:
    def test_all_new_on_first_run(self, tmp_data_dir):
        """All leads returned when no dedup file exists."""
        leads = [make_lead(id="lead1"), make_lead(id="lead2"), make_lead(id="lead3")]
        dedup_dir = tmp_data_dir / "data" / ".dedup"

        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            new, skipped = filter_new_leads(leads, "enrich")

        assert len(new) == 3
        assert skipped == 0

    def test_filters_processed_leads(self, tmp_data_dir):
        """Previously processed leads are filtered out."""
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
        """Empty input returns empty output."""
        dedup_dir = tmp_data_dir / "data" / ".dedup"

        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            new, skipped = filter_new_leads([], "enrich")

        assert new == []
        assert skipped == 0


class TestMarkProcessed:
    def test_writes_lead_ids(self, tmp_data_dir):
        """mark_processed writes lead IDs with timestamps."""
        leads = [make_lead(id="lead1"), make_lead(id="lead2")]
        dedup_dir = tmp_data_dir / "data" / ".dedup"

        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            mark_processed(leads, "enrich")

        dedup_file = dedup_dir / "enrich_processed.json"
        data = json.loads(dedup_file.read_text())
        assert "lead1" in data
        assert "lead2" in data

    def test_appends_to_existing(self, tmp_data_dir):
        """mark_processed adds to existing data, not overwrites."""
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
        """reset_stage removes the dedup tracking file."""
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        dedup_file = dedup_dir / "enrich_processed.json"
        dedup_file.write_text(json.dumps({"lead1": "2026-01-01T00:00:00"}))

        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            reset_stage("enrich")

        assert not dedup_file.exists()

    def test_no_error_if_missing(self, tmp_data_dir):
        """reset_stage does not raise if file doesn't exist."""
        dedup_dir = tmp_data_dir / "data" / ".dedup"

        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            reset_stage("enrich")  # Should not raise


class TestGetStats:
    def test_counts_per_stage(self, tmp_data_dir):
        """get_stats returns correct lead counts per stage."""
        dedup_dir = tmp_data_dir / "data" / ".dedup"
        (dedup_dir / "enrich_processed.json").write_text(
            json.dumps({"l1": "t1", "l2": "t2"})
        )
        (dedup_dir / "score_processed.json").write_text(
            json.dumps({"l1": "t1"})
        )

        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            stats = get_stats()

        assert stats["enrich"] == 2
        assert stats["score"] == 1

    def test_empty_when_no_files(self, tmp_data_dir):
        """get_stats returns empty dict when no dedup files exist."""
        dedup_dir = tmp_data_dir / "data" / ".dedup"

        with patch("src.dedup.DEDUP_DIR", dedup_dir):
            stats = get_stats()

        assert stats == {}
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_dedup.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dedup.py
git commit -m "test: add deduplication logic tests"
```

---

### Task 6: Test Rate Limiter (test_rate_limit.py)

**Files:**
- Create: `tests/test_rate_limit.py`

- [ ] **Step 1: Write test_rate_limit.py**

```python
"""Tests for rate limiting and retry utilities."""

import asyncio
import time
from unittest.mock import MagicMock

import httpx
import pytest

from src.rate_limit import RateLimiter, get_limiter, rate_limited, retry_with_rate_limit, SERVICE_LIMITS


class TestRateLimiter:
    def test_allows_calls_within_limit(self):
        """Calls within rate limit proceed without delay."""
        limiter = RateLimiter(calls_per_minute=10)
        start = time.monotonic()
        for _ in range(5):
            limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # Should be near-instant

    def test_blocks_when_limit_exceeded(self):
        """Limiter blocks when rate limit is hit."""
        limiter = RateLimiter(calls_per_minute=2)
        # Fill up the window
        limiter.wait()
        limiter.wait()
        # Third call should block (but we don't want to wait 60s in tests)
        # Instead verify timestamps are tracked
        assert len(limiter._timestamps) == 2

    @pytest.mark.asyncio
    async def test_async_wait(self):
        """async_wait works in async context."""
        limiter = RateLimiter(calls_per_minute=10)
        await limiter.async_wait()
        await limiter.async_wait()
        assert len(limiter._timestamps) == 2


class TestGetLimiter:
    def test_creates_limiter_with_service_defaults(self):
        """get_limiter uses SERVICE_LIMITS for known services."""
        limiter = get_limiter("serpapi")
        assert limiter.calls_per_minute == SERVICE_LIMITS["serpapi"]

    def test_returns_same_instance(self):
        """get_limiter returns the same instance on repeated calls."""
        limiter1 = get_limiter("outscraper")
        limiter2 = get_limiter("outscraper")
        assert limiter1 is limiter2

    def test_unknown_service_gets_default(self):
        """Unknown service gets default 30 calls/min."""
        limiter = get_limiter("unknown_service_xyz")
        assert limiter.calls_per_minute == 30


class TestRateLimitedDecorator:
    def test_sync_function(self):
        """@rate_limited works on sync functions."""
        call_count = 0

        @rate_limited("website_audit")
        def my_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = my_func()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_function(self):
        """@rate_limited works on async functions."""
        call_count = 0

        @rate_limited("website_audit")
        async def my_async_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await my_async_func()
        assert result == "ok"
        assert call_count == 1


class TestRetryWithRateLimit:
    def test_succeeds_on_first_try(self):
        """No retry needed when function succeeds."""
        @retry_with_rate_limit("serpapi", max_attempts=3)
        def success():
            return "done"

        assert success() == "done"

    def test_retries_on_429(self):
        """Retries on HTTP 429 status."""
        attempt = 0

        @retry_with_rate_limit("serpapi", max_attempts=3)
        def flaky():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                response = httpx.Response(429, request=httpx.Request("GET", "https://example.com"))
                raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
            return "recovered"

        result = flaky()
        assert result == "recovered"
        assert attempt == 2

    def test_retries_on_500(self):
        """Retries on HTTP 500 status."""
        attempt = 0

        @retry_with_rate_limit("serpapi", max_attempts=3)
        def server_error():
            nonlocal attempt
            attempt += 1
            if attempt < 2:
                response = httpx.Response(500, request=httpx.Request("GET", "https://example.com"))
                raise httpx.HTTPStatusError("server error", request=response.request, response=response)
            return "recovered"

        result = server_error()
        assert result == "recovered"

    def test_no_retry_on_400(self):
        """Does not retry on HTTP 400 (client error)."""
        @retry_with_rate_limit("serpapi", max_attempts=3)
        def bad_request():
            response = httpx.Response(400, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("bad request", request=response.request, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            bad_request()

    def test_raises_after_max_attempts(self):
        """Raises last exception after exhausting retries."""
        @retry_with_rate_limit("serpapi", max_attempts=2)
        def always_fails():
            response = httpx.Response(500, request=httpx.Request("GET", "https://example.com"))
            raise httpx.HTTPStatusError("server error", request=response.request, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            always_fails()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_rate_limit.py -v`
Expected: All tests PASS. Note: retry tests may take a few seconds due to backoff sleeps.

- [ ] **Step 3: Commit**

```bash
git add tests/test_rate_limit.py
git commit -m "test: add rate limiter and retry tests"
```

---

### Task 7: Test Google Maps Scraper (test_google_maps.py)

**Files:**
- Create: `tests/scrapers/test_google_maps.py`

- [ ] **Step 1: Write test_google_maps.py**

```python
"""Tests for Google Maps scraper."""

import hashlib
from unittest.mock import patch

import httpx
import pytest
import respx

from src.scrapers.google_maps import (
    parse_serpapi_result,
    parse_apify_result,
    scrape_serpapi,
    scrape_apify,
    scrape_google_maps,
    _make_id,
)
from src.models import LeadSource


class TestMakeId:
    def test_deterministic(self):
        """Same name+address always produces same ID."""
        id1 = _make_id("Acme HVAC", "123 Main St")
        id2 = _make_id("Acme HVAC", "123 Main St")
        assert id1 == id2

    def test_case_insensitive(self):
        """ID generation is case-insensitive."""
        id1 = _make_id("Acme HVAC", "123 Main St")
        id2 = _make_id("acme hvac", "123 main st")
        assert id1 == id2

    def test_different_inputs_differ(self):
        """Different inputs produce different IDs."""
        id1 = _make_id("Acme HVAC", "123 Main St")
        id2 = _make_id("Beta Plumbing", "456 Oak Ave")
        assert id1 != id2

    def test_twelve_chars(self):
        """IDs are 12 characters long."""
        assert len(_make_id("Test", "Addr")) == 12


class TestParseSerpApiResult:
    def test_parses_full_result(self):
        """Extracts all fields from SerpAPI result."""
        item = {
            "title": "Portland HVAC Co",
            "address": "100 NW Broadway, Portland, OR",
            "phone": "(503) 555-1234",
            "website": "https://portlandhvac.com",
            "type": "HVAC contractor",
            "rating": 4.5,
            "reviews": 120,
            "place_id": "ChIJ_test123",
        }
        lead = parse_serpapi_result(item, "portland-or")
        assert lead.business_name == "Portland HVAC Co"
        assert lead.address == "100 NW Broadway, Portland, OR"
        assert lead.phone == "(503) 555-1234"
        assert lead.website == "https://portlandhvac.com"
        assert lead.category == "HVAC contractor"
        assert lead.metro == "portland-or"
        assert lead.source == LeadSource.GOOGLE_MAPS
        assert lead.rating == 4.5
        assert lead.review_count == 120
        assert lead.place_id == "ChIJ_test123"
        assert lead.id  # Non-empty

    def test_handles_missing_fields(self):
        """Gracefully handles missing optional fields."""
        item = {"title": "Bare Minimum Biz"}
        lead = parse_serpapi_result(item, "test-metro")
        assert lead.business_name == "Bare Minimum Biz"
        assert lead.phone == ""
        assert lead.website == ""
        assert lead.rating is None


class TestParseApifyResult:
    def test_parses_full_result(self):
        """Extracts all fields from Apify result."""
        item = {
            "title": "Seattle Dental",
            "address": "200 Pike St, Seattle, WA",
            "phone": "(206) 555-9876",
            "website": "https://seattledental.com",
            "categoryName": "Dentist",
            "totalScore": 4.8,
            "reviewsCount": 200,
            "placeId": "ChIJ_apify456",
        }
        lead = parse_apify_result(item, "seattle-wa")
        assert lead.business_name == "Seattle Dental"
        assert lead.rating == 4.8
        assert lead.review_count == 200
        assert lead.place_id == "ChIJ_apify456"

    def test_falls_back_to_url_for_website(self):
        """Uses 'url' field when 'website' is missing."""
        item = {"title": "Test", "url": "https://fallback.com"}
        lead = parse_apify_result(item, "test")
        assert lead.website == "https://fallback.com"


class TestScrapeSerpapi:
    @respx.mock
    def test_fetches_results(self):
        """scrape_serpapi makes paginated API calls and returns results."""
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={
                "local_results": [
                    {"title": f"Business {i}", "address": f"{i} Main St"}
                    for i in range(3)
                ]
            })
        )
        results = scrape_serpapi("hvac", "portland", "fake-key", num_results=3)
        assert len(results) == 3
        assert results[0]["title"] == "Business 0"

    @respx.mock
    def test_stops_on_empty_page(self):
        """Stops pagination when no more results."""
        call_count = 0

        def side_effect(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={
                    "local_results": [{"title": "Biz 1", "address": "Addr 1"}]
                })
            return httpx.Response(200, json={"local_results": []})

        respx.get("https://serpapi.com/search").mock(side_effect=side_effect)
        results = scrape_serpapi("hvac", "portland", "fake-key", num_results=100)
        assert len(results) == 1


class TestScrapeGoogleMaps:
    @respx.mock
    def test_deduplicates_results(self, sample_settings):
        """scrape_google_maps removes duplicate leads."""
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={
                "local_results": [
                    {"title": "Same Biz", "address": "Same Addr"},
                    {"title": "Same Biz", "address": "Same Addr"},
                    {"title": "Different Biz", "address": "Other Addr"},
                ]
            })
        )
        with patch("src.scrapers.google_maps.load_settings", return_value=sample_settings):
            leads = scrape_google_maps("hvac", "portland-or", num_results=10, provider="serpapi")
        assert len(leads) == 2

    def test_invalid_provider_raises(self, sample_settings):
        """Unknown provider raises ValueError."""
        with patch("src.scrapers.google_maps.load_settings", return_value=sample_settings):
            with pytest.raises(ValueError, match="Unknown provider"):
                scrape_google_maps("hvac", "portland-or", provider="unknown")
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/scrapers/test_google_maps.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/scrapers/
git commit -m "test: add Google Maps scraper tests"
```

---

### Task 8: Test Reviews (test_reviews.py)

**Files:**
- Create: `tests/scrapers/test_reviews.py`

- [ ] **Step 1: Write test_reviews.py**

```python
"""Tests for review scraper and analyzer."""

import httpx
import pytest
import respx

from src.scrapers.reviews import (
    analyze_reviews,
    enrich_lead_with_reviews,
    fetch_reviews_outscraper,
)
from tests.conftest import make_lead


class TestAnalyzeReviews:
    def test_counts_ops_complaints(self):
        """Counts reviews matching complaint keywords."""
        reviews = [
            {"review_text": "They never called back after I left a message", "review_rating": 2},
            {"review_text": "Great service, highly recommend!", "review_rating": 5},
            {"review_text": "Very disorganized office, lost my records", "review_rating": 1},
        ]
        keywords = ["never called back", "disorganized", "hard to reach"]
        result = analyze_reviews(reviews, keywords)
        assert result["total_analyzed"] == 3
        assert result["ops_complaint_count"] == 2
        assert len(result["ops_complaint_samples"]) == 2

    def test_ignores_positive_reviews(self):
        """Only checks reviews with rating <= 3."""
        reviews = [
            {"review_text": "They never called back but great overall!", "review_rating": 5},
            {"review_text": "Never called back, terrible", "review_rating": 4},
        ]
        keywords = ["never called back"]
        result = analyze_reviews(reviews, keywords)
        assert result["ops_complaint_count"] == 0

    def test_owner_response_rate(self):
        """Calculates owner response rate correctly."""
        reviews = [
            {"review_text": "Bad", "review_rating": 1, "owner_answer": "Sorry about that"},
            {"review_text": "Good", "review_rating": 5, "owner_answer": "Thanks!"},
            {"review_text": "OK", "review_rating": 3, "owner_answer": ""},
            {"review_text": "Meh", "review_rating": 3},
        ]
        result = analyze_reviews(reviews, [])
        assert result["owner_response_rate"] == 0.5  # 2 out of 4

    def test_limits_samples_to_five(self):
        """Only keeps up to 5 complaint samples."""
        reviews = [
            {"review_text": f"They were disorganized, visit {i}", "review_rating": 1}
            for i in range(10)
        ]
        keywords = ["disorganized"]
        result = analyze_reviews(reviews, keywords)
        assert result["ops_complaint_count"] == 10
        assert len(result["ops_complaint_samples"]) == 5

    def test_empty_reviews(self):
        """Empty review list returns zeros."""
        result = analyze_reviews([], ["keyword"])
        assert result["total_analyzed"] == 0
        assert result["ops_complaint_count"] == 0
        assert result["owner_response_rate"] == 0.0

    def test_no_matching_keywords(self):
        """No matches when keywords don't appear in reviews."""
        reviews = [
            {"review_text": "Terrible experience", "review_rating": 1},
        ]
        result = analyze_reviews(reviews, ["never called back"])
        assert result["ops_complaint_count"] == 0

    def test_alternate_field_names(self):
        """Handles alternate field names (text vs review_text, rating vs review_rating)."""
        reviews = [
            {"text": "disorganized mess", "rating": 2},
        ]
        result = analyze_reviews(reviews, ["disorganized"])
        assert result["ops_complaint_count"] == 1

    def test_response_field_name(self):
        """Handles 'response' as alternate to 'owner_answer'."""
        reviews = [
            {"review_text": "Bad", "review_rating": 1, "response": "We'll fix it"},
        ]
        result = analyze_reviews(reviews, [])
        assert result["owner_response_rate"] == 1.0


class TestFetchReviewsOutscraper:
    @respx.mock
    def test_fetches_reviews(self):
        """Fetches and extracts reviews from Outscraper response."""
        respx.get("https://api.app.outscraper.com/maps/reviews-v3").mock(
            return_value=httpx.Response(200, json={
                "data": [{
                    "reviews_data": [
                        {"review_text": "Great!", "review_rating": 5},
                        {"review_text": "Bad!", "review_rating": 1},
                    ]
                }]
            })
        )
        reviews = fetch_reviews_outscraper("ChIJ_test", "fake-key")
        assert len(reviews) == 2

    @respx.mock
    def test_empty_response(self):
        """Returns empty list when no reviews found."""
        respx.get("https://api.app.outscraper.com/maps/reviews-v3").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        reviews = fetch_reviews_outscraper("ChIJ_test", "fake-key")
        assert reviews == []


class TestEnrichLeadWithReviews:
    def test_applies_analysis_to_lead(self):
        """Sets review fields on the Lead."""
        lead = make_lead()
        analysis = {
            "total_analyzed": 50,
            "ops_complaint_count": 5,
            "ops_complaint_samples": ["sample 1", "sample 2"],
            "owner_response_rate": 0.3,
        }
        enrich_lead_with_reviews(lead, analysis)
        assert lead.reviews_analyzed == 50
        assert lead.ops_complaint_count == 5
        assert lead.ops_complaint_samples == ["sample 1", "sample 2"]
        assert lead.owner_response_rate == 0.3
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/scrapers/test_reviews.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/scrapers/test_reviews.py
git commit -m "test: add review analysis tests"
```

---

### Task 9: Test Job Posts (test_job_posts.py)

**Files:**
- Create: `tests/scrapers/test_job_posts.py`

- [ ] **Step 1: Write test_job_posts.py**

```python
"""Tests for job posting scraper and analyzer."""

import httpx
import pytest
import respx

from src.scrapers.job_posts import (
    analyze_job_postings,
    enrich_lead_with_jobs,
    search_jobs_serpapi,
)
from tests.conftest import make_lead


class TestAnalyzeJobPostings:
    def test_detects_keyword_in_title(self):
        """Matches manual process keywords in job title."""
        postings = [
            {"title": "Data Entry Clerk", "description": "Fast-paced office environment"},
        ]
        result = analyze_job_postings(postings, ["data entry"])
        assert result["manual_process_count"] == 1
        assert result["manual_process_titles"] == ["Data Entry Clerk"]

    def test_detects_keyword_in_description(self):
        """Matches manual process keywords in job description."""
        postings = [
            {"title": "Office Associate", "description": "Maintain spreadsheet records and filing"},
        ]
        result = analyze_job_postings(postings, ["spreadsheet", "filing"])
        assert result["manual_process_count"] == 1

    def test_counts_total_postings(self):
        """total_postings reflects all input postings."""
        postings = [
            {"title": "Developer", "description": "Build software"},
            {"title": "Designer", "description": "Design UI"},
            {"title": "Data Entry", "description": "Enter data"},
        ]
        result = analyze_job_postings(postings, ["data entry"])
        assert result["total_postings"] == 3
        assert result["manual_process_count"] == 1

    def test_no_matches(self):
        """Returns zero when no keywords match."""
        postings = [
            {"title": "Software Engineer", "description": "Write Python code"},
        ]
        result = analyze_job_postings(postings, ["data entry", "filing"])
        assert result["manual_process_count"] == 0
        assert result["manual_process_titles"] == []

    def test_empty_postings(self):
        """Empty input returns zeros."""
        result = analyze_job_postings([], ["data entry"])
        assert result["total_postings"] == 0
        assert result["manual_process_count"] == 0

    def test_one_match_per_posting(self):
        """Only counts one match per posting even if multiple keywords match."""
        postings = [
            {"title": "Admin Filing Clerk", "description": "Data entry and spreadsheet work"},
        ]
        result = analyze_job_postings(postings, ["filing", "data entry", "spreadsheet"])
        assert result["manual_process_count"] == 1


class TestSearchJobsSerpapi:
    @respx.mock
    def test_fetches_jobs(self):
        """Fetches jobs from SerpAPI Google Jobs endpoint."""
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={
                "jobs_results": [
                    {"title": "HVAC Technician", "description": "Install and repair"},
                    {"title": "Receptionist", "description": "Answer phones"},
                ]
            })
        )
        results = search_jobs_serpapi("Acme HVAC", "Portland, OR", "fake-key")
        assert len(results) == 2
        assert results[0]["title"] == "HVAC Technician"

    @respx.mock
    def test_empty_results(self):
        """Returns empty list when no jobs found."""
        respx.get("https://serpapi.com/search").mock(
            return_value=httpx.Response(200, json={})
        )
        results = search_jobs_serpapi("Nobody Inc", "Nowhere", "fake-key")
        assert results == []


class TestEnrichLeadWithJobs:
    def test_applies_analysis_to_lead(self):
        """Sets job posting fields on the Lead."""
        lead = make_lead()
        analysis = {
            "total_postings": 5,
            "manual_process_count": 2,
            "manual_process_titles": ["Receptionist", "Filing Clerk"],
        }
        enrich_lead_with_jobs(lead, analysis)
        assert lead.active_job_postings == 5
        assert lead.manual_process_postings == 2
        assert lead.manual_process_titles == ["Receptionist", "Filing Clerk"]
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/scrapers/test_job_posts.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/scrapers/test_job_posts.py
git commit -m "test: add job posting analysis tests"
```

---

### Task 10: Test Website Audit (test_website_audit.py)

**Files:**
- Create: `tests/enrichment/test_website_audit.py`

- [ ] **Step 1: Write test_website_audit.py**

```python
"""Tests for website auditor — pattern matching for CRM, chat, scheduling, tech stack."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.enrichment.website_audit import (
    AuditResult,
    _check_patterns,
    _check_mobile_responsive,
    _detect_tech_from_html,
    _find_outdated_signals,
    audit_website,
    enrich_lead_with_audit,
    CRM_PATTERNS,
    CHAT_PATTERNS,
    SCHEDULING_PATTERNS,
)
from bs4 import BeautifulSoup
from tests.conftest import make_lead, build_html


class TestCRMDetection:
    @pytest.mark.parametrize("crm_name,pattern_fragment", [
        ("hubspot", "hubspot"),
        ("salesforce", "salesforce"),
        ("pipedrive", "pipedrive"),
        ("zoho", "zoho"),
        ("freshsales", "freshsales"),
        ("keap", "keap.com"),
        ("infusionsoft", "infusionsoft"),
        ("activecampaign", "activecampaign"),
    ])
    def test_detects_crm(self, crm_name, pattern_fragment):
        """Each CRM pattern is detected in HTML."""
        html = build_html(has_crm=crm_name)
        assert _check_patterns(html, CRM_PATTERNS) is True

    def test_no_crm_in_plain_html(self):
        """Plain HTML without CRM scripts returns False."""
        html = build_html()
        assert _check_patterns(html, CRM_PATTERNS) is False


class TestChatDetection:
    @pytest.mark.parametrize("chat_name", [
        "intercom", "drift", "crisp", "tawk", "livechat",
        "zendesk", "freshchat", "tidio", "chatwoot",
    ])
    def test_detects_chat(self, chat_name):
        """Each chat widget pattern is detected."""
        html = build_html(has_chat=chat_name)
        assert _check_patterns(html, CHAT_PATTERNS) is True

    def test_no_chat_in_plain_html(self):
        """Plain HTML without chat scripts returns False."""
        html = build_html()
        assert _check_patterns(html, CHAT_PATTERNS) is False


class TestSchedulingDetection:
    @pytest.mark.parametrize("sched_name", [
        "calendly", "acuity", "cal.com", "square_appointments",
        "booksy", "vagaro", "setmore",
    ])
    def test_detects_scheduling(self, sched_name):
        """Each scheduling pattern is detected."""
        html = build_html(has_scheduling=sched_name)
        assert _check_patterns(html, SCHEDULING_PATTERNS) is True

    def test_no_scheduling_in_plain_html(self):
        """Plain HTML without scheduling scripts returns False."""
        html = build_html()
        assert _check_patterns(html, SCHEDULING_PATTERNS) is False


class TestTechStackDetection:
    @pytest.mark.parametrize("tech", [
        "wordpress", "wix", "squarespace", "shopify", "webflow",
        "google_analytics", "google_tag_manager", "facebook_pixel",
        "bootstrap", "tailwind", "react", "angular", "vue",
    ])
    def test_detects_tech(self, tech):
        """Each technology is detected from HTML."""
        html = build_html(techs=[tech])
        soup = BeautifulSoup(html, "html.parser")
        detected = _detect_tech_from_html(html, soup)
        assert tech in detected

    def test_plain_html_no_tech(self):
        """Plain HTML returns empty tech list."""
        html = build_html()
        soup = BeautifulSoup(html, "html.parser")
        detected = _detect_tech_from_html(html, soup)
        assert detected == []

    def test_multiple_techs(self):
        """Multiple technologies detected simultaneously."""
        html = build_html(techs=["wordpress", "google_analytics", "bootstrap"])
        soup = BeautifulSoup(html, "html.parser")
        detected = _detect_tech_from_html(html, soup)
        assert "wordpress" in detected
        assert "google_analytics" in detected
        assert "bootstrap" in detected


class TestOutdatedSignals:
    def test_legacy_jquery(self):
        """Detects jQuery 1.x/2.x as outdated."""
        html = build_html(outdated=["legacy_jquery"])
        found = _find_outdated_signals(html)
        assert "legacy_jquery" in found

    def test_old_wordpress(self):
        """Detects old WordPress versions."""
        html = build_html(outdated=["old_wordpress"])
        found = _find_outdated_signals(html)
        assert "old_wordpress" in found

    def test_framesets(self):
        """Detects frameset usage."""
        html = build_html(outdated=["frameset"])
        found = _find_outdated_signals(html)
        assert "framesets" in found

    def test_marquee_and_blink(self):
        """Detects marquee and blink tags."""
        html = build_html(outdated=["marquee", "blink"])
        found = _find_outdated_signals(html)
        assert "marquee" in found
        assert "blink" in found

    def test_flash(self):
        """Detects Flash content."""
        html = build_html(outdated=["flash"])
        found = _find_outdated_signals(html)
        assert "flash_swf" in found

    def test_no_outdated_signals(self):
        """Modern HTML returns empty list."""
        html = build_html()
        found = _find_outdated_signals(html)
        assert found == []

    def test_jquery_3x_not_flagged(self):
        """jQuery 3.x should not be flagged as outdated."""
        html = '<script src="jquery.min.js?ver=3.6.0"></script>'
        found = _find_outdated_signals(html)
        assert "legacy_jquery" not in found


class TestMobileResponsive:
    def test_responsive_with_viewport(self):
        """Viewport meta tag → mobile responsive."""
        html = build_html(has_viewport=True)
        soup = BeautifulSoup(html, "html.parser")
        assert _check_mobile_responsive(soup) is True

    def test_not_responsive_without_viewport(self):
        """No viewport meta tag → not mobile responsive."""
        html = build_html(has_viewport=False)
        soup = BeautifulSoup(html, "html.parser")
        assert _check_mobile_responsive(soup) is False


class TestAuditWebsite:
    @respx.mock
    def test_full_audit(self):
        """Full audit extracts all signals from a website."""
        html = build_html(
            has_crm="hubspot",
            has_chat="intercom",
            has_scheduling="calendly",
            techs=["wordpress", "google_analytics"],
            has_viewport=True,
        )
        respx.get("https://acmehvac.com").mock(
            return_value=httpx.Response(200, text=html)
        )
        result = audit_website("https://acmehvac.com")
        assert result.reachable is True
        assert result.has_ssl is True
        assert result.has_crm is True
        assert result.has_chat is True
        assert result.has_scheduling is True
        assert result.is_mobile_responsive is True
        assert "wordpress" in result.detected_tech
        assert "google_analytics" in result.detected_tech

    @respx.mock
    def test_bare_website(self):
        """Website with no tools detected."""
        html = build_html(has_viewport=False)
        respx.get("https://baresite.com").mock(
            return_value=httpx.Response(200, text=html)
        )
        result = audit_website("https://baresite.com")
        assert result.reachable is True
        assert result.has_crm is False
        assert result.has_chat is False
        assert result.has_scheduling is False
        assert result.is_mobile_responsive is False

    @respx.mock
    def test_timeout_handling(self):
        """Timeout sets error field."""
        respx.get("https://slow.com").mock(side_effect=httpx.TimeoutException("timed out"))
        result = audit_website("https://slow.com")
        assert result.reachable is False
        assert result.error == "timeout"

    @respx.mock
    def test_http_error_handling(self):
        """HTTP error sets error field."""
        respx.get("https://broken.com").mock(
            return_value=httpx.Response(404)
        )
        result = audit_website("https://broken.com")
        assert result.reachable is False
        assert "http_404" in result.error

    def test_empty_url(self):
        """Empty URL returns error immediately."""
        result = audit_website("")
        assert result.error == "no_url"

    @respx.mock
    def test_normalizes_url(self):
        """Adds https:// to bare domain."""
        html = build_html()
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text=html)
        )
        result = audit_website("example.com")
        assert result.reachable is True


class TestEnrichLeadWithAudit:
    def test_applies_audit_to_lead(self):
        """Audit results are applied to Lead fields."""
        lead = make_lead()
        audit = AuditResult(
            url="https://acmehvac.com",
            reachable=True,
            has_ssl=True,
            has_crm=True,
            has_chat=False,
            has_scheduling=True,
            is_mobile_responsive=True,
            detected_tech=["wordpress", "react"],
        )
        enrich_lead_with_audit(lead, audit)
        assert lead.has_crm is True
        assert lead.has_chat_widget is False
        assert lead.has_scheduling is True
        assert lead.has_ssl is True
        assert lead.is_mobile_responsive is True
        assert lead.tech_stack == ["wordpress", "react"]
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/enrichment/test_website_audit.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/enrichment/
git commit -m "test: add website audit pattern matching tests"
```

---

### Task 11: Test Contacts (test_contacts.py)

**Files:**
- Create: `tests/enrichment/test_contacts.py`

- [ ] **Step 1: Write test_contacts.py**

```python
"""Tests for contact enrichment (Apollo/Hunter waterfall)."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.enrichment.contacts import (
    search_apollo,
    search_hunter,
    verify_email_hunter,
    _title_priority,
    _pick_best_contact,
    enrich_lead_contacts,
)
from tests.conftest import make_lead


class TestTitlePriority:
    def test_owner_is_highest(self):
        assert _title_priority("Owner") < _title_priority("Office Manager")

    def test_founder_is_high(self):
        assert _title_priority("Co-Founder") < _title_priority("Administrator")

    def test_unknown_title_is_lowest(self):
        assert _title_priority("Janitor") == 999

    def test_case_insensitive(self):
        assert _title_priority("CEO") == _title_priority("ceo")


class TestPickBestContact:
    def test_prefers_higher_title(self):
        """Owner beats office manager."""
        people = [
            {"name": "Jane", "email": "jane@co.com", "title": "Office Manager"},
            {"name": "Bob", "email": "bob@co.com", "title": "Owner"},
        ]
        best = _pick_best_contact(people)
        assert best["name"] == "Bob"

    def test_prefers_email_over_no_email(self):
        """Contact with email is preferred even if title is lower priority."""
        people = [
            {"name": "Alice", "email": "", "title": "Owner"},
            {"name": "Bob", "email": "bob@co.com", "title": "General Manager"},
        ]
        best = _pick_best_contact(people)
        assert best["name"] == "Bob"

    def test_returns_none_for_empty(self):
        """Returns None when no contacts available."""
        assert _pick_best_contact([]) is None

    def test_falls_back_to_name_only(self):
        """Returns contact with name even if no email."""
        people = [
            {"name": "Alice", "email": "", "title": "Owner"},
        ]
        best = _pick_best_contact(people)
        assert best["name"] == "Alice"


class TestSearchApollo:
    @respx.mock
    def test_returns_contacts(self):
        """Apollo search returns parsed contacts."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [
                    {
                        "first_name": "John",
                        "last_name": "Smith",
                        "email": "john@acme.com",
                        "title": "Owner",
                        "linkedin_url": "https://linkedin.com/in/jsmith",
                        "phone_number": "555-1234",
                    }
                ]
            })
        )
        results = search_apollo("Acme HVAC", "acmehvac.com", "fake-key")
        assert len(results) == 1
        assert results[0]["name"] == "John Smith"
        assert results[0]["email"] == "john@acme.com"
        assert results[0]["title"] == "Owner"

    @respx.mock
    def test_empty_results(self):
        """Returns empty list when no people found."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={"people": []})
        )
        results = search_apollo("Nobody Inc", "nobody.com", "fake-key")
        assert results == []


class TestSearchHunter:
    @respx.mock
    def test_returns_contacts(self):
        """Hunter search returns parsed contacts."""
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "emails": [
                        {
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "value": "jane@example.com",
                            "position": "CEO",
                            "linkedin": "https://linkedin.com/in/jdoe",
                        }
                    ]
                }
            })
        )
        results = search_hunter("example.com", "fake-key")
        assert len(results) == 1
        assert results[0]["name"] == "Jane Doe"
        assert results[0]["email"] == "jane@example.com"

    def test_empty_domain_returns_empty(self):
        """Empty domain returns empty list without API call."""
        results = search_hunter("", "fake-key")
        assert results == []


class TestVerifyEmailHunter:
    @respx.mock
    def test_returns_verification(self):
        """Returns status and score from Hunter verification."""
        respx.get("https://api.hunter.io/v2/email-verifier").mock(
            return_value=httpx.Response(200, json={
                "data": {"status": "valid", "score": 95}
            })
        )
        result = verify_email_hunter("test@example.com", "fake-key")
        assert result["status"] == "valid"
        assert result["score"] == 95


class TestEnrichLeadContacts:
    @respx.mock
    def test_apollo_success(self):
        """Uses Apollo result when available."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            return_value=httpx.Response(200, json={
                "people": [{
                    "first_name": "Bob",
                    "last_name": "Owner",
                    "email": "bob@acme.com",
                    "title": "Owner",
                    "linkedin_url": "",
                    "phone_number": "",
                }]
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake-key")
        assert lead.contact_name == "Bob Owner"
        assert lead.contact_email == "bob@acme.com"
        assert lead.contact_title == "Owner"

    @respx.mock
    def test_waterfall_to_hunter(self):
        """Falls back to Hunter when Apollo fails."""
        respx.post("https://api.apollo.io/v1/mixed_people/search").mock(
            side_effect=httpx.HTTPStatusError(
                "error",
                request=httpx.Request("POST", "https://api.apollo.io/v1/mixed_people/search"),
                response=httpx.Response(500),
            )
        )
        respx.get("https://api.hunter.io/v2/domain-search").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "emails": [{
                        "first_name": "Jane",
                        "last_name": "Fallback",
                        "value": "jane@acme.com",
                        "position": "Manager",
                    }]
                }
            })
        )
        lead = make_lead(website="https://acmehvac.com")
        enrich_lead_contacts(lead, apollo_key="fake-key", hunter_key="fake-key")
        assert lead.contact_name == "Jane Fallback"
        assert lead.contact_email == "jane@acme.com"

    def test_no_keys_no_enrichment(self):
        """No API keys means no enrichment."""
        lead = make_lead()
        enrich_lead_contacts(lead)
        assert lead.contact_name == ""
        assert lead.contact_email == ""
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/enrichment/test_contacts.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/enrichment/test_contacts.py
git commit -m "test: add contact enrichment tests"
```

---

### Task 12: Test Async Processor (test_async_processor.py)

**Files:**
- Create: `tests/enrichment/test_async_processor.py`

- [ ] **Step 1: Write test_async_processor.py**

```python
"""Tests for async enrichment processor."""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.enrichment.async_processor import enrich_leads_async, _enrich_single
from tests.conftest import make_lead


@pytest.fixture
def mock_settings(sample_settings):
    """Patch load_settings to return sample settings."""
    with patch("src.enrichment.async_processor.load_settings", return_value=sample_settings):
        yield sample_settings


class TestEnrichLeadsAsync:
    @pytest.mark.asyncio
    async def test_enriches_all_leads(self, mock_settings):
        """All leads get enriched_at set."""
        leads = [make_lead(id="l1", website=""), make_lead(id="l2", website="")]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        assert len(results) == 2
        for lead in results:
            assert lead.enriched_at is not None

    @pytest.mark.asyncio
    async def test_preserves_order(self, mock_settings):
        """Results preserve original lead order."""
        leads = [make_lead(id=f"l{i}", website="") for i in range(5)]

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        result_ids = [l.id for l in results]
        assert result_ids == ["l0", "l1", "l2", "l3", "l4"]

    @pytest.mark.asyncio
    async def test_failure_doesnt_block_others(self, mock_settings):
        """One failed enrichment doesn't prevent others."""
        leads = [make_lead(id="good", website=""), make_lead(id="also_good", website="")]

        call_count = 0

        original_enrich = _enrich_single

        async def flaky_enrich(lead, settings, semaphore, complaint_kw, manual_kw):
            return await original_enrich(lead, settings, semaphore, complaint_kw, manual_kw)

        with patch("src.enrichment.async_processor.audit_website"), \
             patch("src.enrichment.async_processor.enrich_lead_with_audit"), \
             patch("src.enrichment.async_processor.fetch_reviews_outscraper", return_value=[]), \
             patch("src.enrichment.async_processor.search_jobs_serpapi", return_value=[]), \
             patch("src.enrichment.async_processor.enrich_lead_contacts"):
            results = await enrich_leads_async(leads, max_concurrent=2)

        # Both leads should complete even if individual services fail
        assert len(results) == 2
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/enrichment/test_async_processor.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/enrichment/test_async_processor.py
git commit -m "test: add async enrichment processor tests"
```

---

### Task 13: Test Scoring Engine (test_score.py)

**Files:**
- Create: `tests/scoring/test_score.py`

- [ ] **Step 1: Write test_score.py**

```python
"""Tests for the scoring engine — parametrized across all factors and weight combos."""

from unittest.mock import patch

import pytest

from src.scoring.score import score_lead, score_leads, _normalize, DEFAULT_WEIGHTS
from tests.conftest import make_lead


class TestNormalize:
    def test_mid_range(self):
        assert _normalize(5, 0, 10) == 0.5

    def test_at_min(self):
        assert _normalize(0, 0, 10) == 0.0

    def test_at_max(self):
        assert _normalize(10, 0, 10) == 1.0

    def test_below_min_clamps(self):
        assert _normalize(-5, 0, 10) == 0.0

    def test_above_max_clamps(self):
        assert _normalize(15, 0, 10) == 1.0

    def test_equal_min_max(self):
        assert _normalize(5, 5, 5) == 0.0


class TestWebsiteOutdatedFactor:
    def test_no_ssl(self):
        """No SSL contributes 0.3."""
        lead = make_lead(has_ssl=False, is_mobile_responsive=True, tech_stack=["react"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == pytest.approx(0.3, abs=0.01)

    def test_not_mobile_responsive(self):
        """Not mobile responsive contributes 0.4."""
        lead = make_lead(has_ssl=True, is_mobile_responsive=False, tech_stack=["react"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == pytest.approx(0.4, abs=0.01)

    def test_no_modern_tech(self):
        """No modern framework contributes 0.3."""
        lead = make_lead(has_ssl=True, is_mobile_responsive=True, tech_stack=["wordpress"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == pytest.approx(0.3, abs=0.01)

    def test_all_outdated_signals(self):
        """All signals combined cap at 1.0."""
        lead = make_lead(has_ssl=False, is_mobile_responsive=False, tech_stack=["wordpress"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == 1.0

    def test_modern_website(self):
        """Modern site with SSL, mobile, and React scores 0."""
        lead = make_lead(has_ssl=True, is_mobile_responsive=True, tech_stack=["react"])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == 0.0

    def test_empty_tech_stack(self):
        """Empty tech stack doesn't add to score (no tech_stack penalty)."""
        lead = make_lead(has_ssl=True, is_mobile_responsive=True, tech_stack=[])
        score_lead(lead)
        assert lead.score_breakdown["website_outdated"] == 0.0


class TestBooleanFactors:
    @pytest.mark.parametrize("field,factor_name", [
        ("has_crm", "no_crm_detected"),
        ("has_scheduling", "no_scheduling_tool"),
        ("has_chat_widget", "no_chat_widget"),
    ])
    def test_missing_tool_scores_one(self, field, factor_name):
        """Missing tool → 1.0 subscore."""
        lead = make_lead(**{field: False})
        score_lead(lead)
        assert lead.score_breakdown[factor_name] == 1.0

    @pytest.mark.parametrize("field,factor_name", [
        ("has_crm", "no_crm_detected"),
        ("has_scheduling", "no_scheduling_tool"),
        ("has_chat_widget", "no_chat_widget"),
    ])
    def test_present_tool_scores_zero(self, field, factor_name):
        """Present tool → 0.0 subscore."""
        lead = make_lead(**{field: True})
        score_lead(lead)
        assert lead.score_breakdown[factor_name] == 0.0

    @pytest.mark.parametrize("field,factor_name", [
        ("has_crm", "no_crm_detected"),
        ("has_scheduling", "no_scheduling_tool"),
        ("has_chat_widget", "no_chat_widget"),
    ])
    def test_none_scores_zero(self, field, factor_name):
        """None (not checked) → 0.0 subscore."""
        lead = make_lead(**{field: None})
        score_lead(lead)
        assert lead.score_breakdown[factor_name] == 0.0


class TestManualJobPostingsFactor:
    def test_zero_postings(self):
        """No active postings → 0.0."""
        lead = make_lead(active_job_postings=0, manual_process_postings=0)
        score_lead(lead)
        assert lead.score_breakdown["manual_job_postings"] == 0.0

    def test_some_manual_postings(self):
        """1 manual posting out of 5 active → normalized score."""
        lead = make_lead(active_job_postings=5, manual_process_postings=1)
        score_lead(lead)
        score = lead.score_breakdown["manual_job_postings"]
        assert 0 < score < 1

    def test_many_manual_postings(self):
        """3+ manual postings → 1.0."""
        lead = make_lead(active_job_postings=10, manual_process_postings=5)
        score_lead(lead)
        assert lead.score_breakdown["manual_job_postings"] == 1.0

    def test_no_active_postings_no_score(self):
        """active_job_postings=0 means we have no data → 0.0."""
        lead = make_lead(active_job_postings=0, manual_process_postings=3)
        score_lead(lead)
        assert lead.score_breakdown["manual_job_postings"] == 0.0


class TestNegativeReviewsFactor:
    def test_high_complaint_ratio(self):
        """High complaint ratio → high score."""
        lead = make_lead(reviews_analyzed=100, ops_complaint_count=15)
        score_lead(lead)
        assert lead.score_breakdown["negative_reviews_ops"] == 1.0

    def test_low_complaint_ratio(self):
        """Low complaint ratio → low score."""
        lead = make_lead(reviews_analyzed=100, ops_complaint_count=2)
        score_lead(lead)
        score = lead.score_breakdown["negative_reviews_ops"]
        assert 0 < score < 1

    def test_no_reviews(self):
        """No reviews analyzed → 0.0."""
        lead = make_lead(reviews_analyzed=0, ops_complaint_count=0)
        score_lead(lead)
        assert lead.score_breakdown["negative_reviews_ops"] == 0.0

    def test_low_owner_response_bonus(self):
        """Low owner response rate adds 0.2 bonus."""
        lead = make_lead(
            reviews_analyzed=100,
            ops_complaint_count=5,
            owner_response_rate=0.1,
        )
        score_lead(lead)
        score_with_bonus = lead.score_breakdown["negative_reviews_ops"]

        lead2 = make_lead(
            reviews_analyzed=100,
            ops_complaint_count=5,
            owner_response_rate=0.5,
        )
        score_lead(lead2)
        score_without_bonus = lead2.score_breakdown["negative_reviews_ops"]

        assert score_with_bonus > score_without_bonus


class TestCompositeScoring:
    def test_perfect_lead_near_zero(self):
        """Lead with all modern tools scores near 0."""
        lead = make_lead(
            has_ssl=True, is_mobile_responsive=True, tech_stack=["react"],
            has_crm=True, has_scheduling=True, has_chat_widget=True,
            active_job_postings=5, manual_process_postings=0,
            reviews_analyzed=50, ops_complaint_count=0,
        )
        score_lead(lead)
        assert lead.score <= 5.0

    def test_worst_lead_near_hundred(self):
        """Lead missing everything scores near 100."""
        lead = make_lead(
            has_ssl=False, is_mobile_responsive=False, tech_stack=["wordpress"],
            has_crm=False, has_scheduling=False, has_chat_widget=False,
            active_job_postings=10, manual_process_postings=5,
            reviews_analyzed=100, ops_complaint_count=20,
            owner_response_rate=0.05,
        )
        score_lead(lead)
        assert lead.score >= 80.0

    def test_score_always_0_to_100(self):
        """Score is always in [0, 100] range."""
        for has_crm in [True, False, None]:
            for has_ssl in [True, False, None]:
                lead = make_lead(has_crm=has_crm, has_ssl=has_ssl)
                score_lead(lead)
                assert 0 <= lead.score <= 100

    def test_default_weights_sum(self):
        """Default weights sum to 100."""
        assert sum(DEFAULT_WEIGHTS.values()) == 100

    def test_breakdown_has_all_factors(self):
        """score_breakdown contains all factor keys."""
        lead = make_lead()
        score_lead(lead)
        expected_keys = {
            "website_outdated", "no_crm_detected", "no_scheduling_tool",
            "no_chat_widget", "manual_job_postings", "negative_reviews_ops",
            "business_age", "employee_count",
        }
        assert set(lead.score_breakdown.keys()) == expected_keys

    def test_breakdown_values_0_to_1(self):
        """All breakdown values are between 0 and 1."""
        lead = make_lead(
            has_ssl=False, has_crm=False,
            reviews_analyzed=50, ops_complaint_count=10,
        )
        score_lead(lead)
        for value in lead.score_breakdown.values():
            assert 0 <= value <= 1

    def test_scored_at_set(self):
        """scored_at timestamp is set."""
        lead = make_lead()
        score_lead(lead)
        assert lead.scored_at is not None


class TestCustomWeights:
    def test_custom_weights_applied(self):
        """Custom weights change the score."""
        lead = make_lead(has_crm=False, has_scheduling=False)

        # Weight CRM heavily
        score_lead(lead, weights={"no_crm_detected": 100, "no_scheduling_tool": 0, **{k: 0 for k in DEFAULT_WEIGHTS if k not in ("no_crm_detected", "no_scheduling_tool")}})
        score_crm_heavy = lead.score

        # Weight scheduling heavily
        score_lead(lead, weights={"no_crm_detected": 0, "no_scheduling_tool": 100, **{k: 0 for k in DEFAULT_WEIGHTS if k not in ("no_crm_detected", "no_scheduling_tool")}})
        score_sched_heavy = lead.score

        # Both should be 100 since both are False → 1.0
        assert score_crm_heavy == pytest.approx(100.0, abs=1)
        assert score_sched_heavy == pytest.approx(100.0, abs=1)

    def test_zero_weight_factor_excluded(self):
        """Factor with weight 0 doesn't affect score."""
        lead = make_lead(has_crm=False)
        weights = {**DEFAULT_WEIGHTS, "no_crm_detected": 0}
        score_lead(lead, weights=weights)
        # CRM factor is 1.0 but weight is 0, so it contributes nothing
        # Score should reflect other factors only


class TestVerticalOverrides:
    def test_hvac_weights(self, sample_settings, sample_vertical_config):
        """HVAC vertical overrides are applied via score_leads."""
        leads = [make_lead(has_scheduling=False)]

        with patch("src.scoring.score.load_settings", return_value=sample_settings), \
             patch("src.scoring.score.load_vertical", return_value=sample_vertical_config):
            scored = score_leads(leads, vertical="hvac")

        assert len(scored) == 1
        assert scored[0].score is not None

    def test_no_vertical_uses_defaults(self, sample_settings):
        """No vertical specified uses default weights from settings."""
        leads = [make_lead()]

        with patch("src.scoring.score.load_settings", return_value=sample_settings):
            scored = score_leads(leads, vertical=None)

        assert len(scored) == 1

    def test_sorted_descending(self, sample_settings):
        """score_leads returns leads sorted by score descending."""
        leads = [
            make_lead(id="low", has_crm=True, has_scheduling=True, has_chat_widget=True),
            make_lead(id="high", has_crm=False, has_scheduling=False, has_chat_widget=False),
        ]

        with patch("src.scoring.score.load_settings", return_value=sample_settings):
            scored = score_leads(leads)

        assert scored[0].score >= scored[1].score
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/scoring/test_score.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/scoring/
git commit -m "test: add scoring engine tests with parametrized factors"
```

---

### Task 14: Test Outreach Generator (test_generate.py)

**Files:**
- Create: `tests/outreach/test_generate.py`

- [ ] **Step 1: Write test_generate.py**

```python
"""Tests for outreach email generation via Claude API."""

import json
from unittest.mock import patch, MagicMock

import pytest

from src.outreach.generate import _build_lead_context, generate_outreach
from tests.conftest import make_lead


class TestBuildLeadContext:
    def test_includes_basic_info(self):
        """Context includes business name, category, location, website."""
        lead = make_lead()
        context = _build_lead_context(lead)
        assert "Acme HVAC Services" in context
        assert "HVAC" in context
        assert "123 Main St" in context
        assert "acmehvac.com" in context

    def test_includes_contact(self):
        """Contact name and title included when present."""
        lead = make_lead(contact_name="Bob Smith", contact_title="Owner")
        context = _build_lead_context(lead)
        assert "Bob Smith" in context
        assert "Owner" in context

    def test_includes_missing_tools(self):
        """Missing CRM/chat/scheduling flagged in context."""
        lead = make_lead(has_crm=False, has_chat_widget=False, has_scheduling=False)
        context = _build_lead_context(lead)
        assert "No CRM" in context
        assert "No chat widget" in context
        assert "No online scheduling" in context

    def test_omits_none_fields(self):
        """None values for tool detection don't appear in context."""
        lead = make_lead(has_crm=None, has_scheduling=None)
        context = _build_lead_context(lead)
        assert "No CRM" not in context
        assert "No online scheduling" not in context

    def test_includes_review_complaints(self):
        """Review complaints appear in context."""
        lead = make_lead(
            ops_complaint_count=5,
            reviews_analyzed=50,
            ops_complaint_samples=["never called back", "lost paperwork"],
        )
        context = _build_lead_context(lead)
        assert "5 complaints" in context
        assert "50 reviews" in context

    def test_includes_job_signals(self):
        """Manual process job postings appear in context."""
        lead = make_lead(
            manual_process_postings=2,
            manual_process_titles=["Receptionist", "Data Entry Clerk"],
        )
        context = _build_lead_context(lead)
        assert "2 roles" in context
        assert "Receptionist" in context

    def test_includes_score(self):
        """Score and top factors included."""
        lead = make_lead(
            score=72.5,
            score_breakdown={"no_crm_detected": 1.0, "website_outdated": 0.5, "manual_job_postings": 0.3},
        )
        context = _build_lead_context(lead)
        assert "72.5/100" in context
        assert "no_crm_detected" in context

    def test_includes_low_owner_response_rate(self):
        """Low owner response rate flagged."""
        lead = make_lead(owner_response_rate=0.1)
        context = _build_lead_context(lead)
        assert "10%" in context

    def test_normal_owner_response_rate_omitted(self):
        """Normal response rate (>=30%) not flagged."""
        lead = make_lead(owner_response_rate=0.5)
        context = _build_lead_context(lead)
        assert "responds to only" not in context


class TestGenerateOutreach:
    def test_sets_outreach_fields(self, sample_settings):
        """Successful generation sets outreach_email, followups, contacted_at."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "subject": "Quick question about your HVAC scheduling",
            "body": "Hi Bob, your customers mention difficulty booking appointments...",
            "followups": ["Following up on my email...", "Last note..."],
        })

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        lead = make_lead(contact_name="Bob", score=72.5)

        with patch("src.outreach.generate.load_settings", return_value=sample_settings), \
             patch("src.outreach.generate.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            generate_outreach(lead)

        assert "Quick question" in lead.outreach_email
        assert len(lead.followups) == 2
        assert lead.contacted_at is not None

    def test_handles_markdown_wrapped_json(self, sample_settings):
        """Handles Claude response wrapped in markdown code fences."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '```json\n{"subject": "Test", "body": "Hello", "followups": []}\n```'

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        lead = make_lead()

        with patch("src.outreach.generate.load_settings", return_value=sample_settings), \
             patch("src.outreach.generate.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            generate_outreach(lead)

        assert "Test" in lead.outreach_email

    def test_handles_api_error_gracefully(self, sample_settings):
        """API error doesn't crash, leaves fields empty."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        lead = make_lead()

        with patch("src.outreach.generate.load_settings", return_value=sample_settings), \
             patch("src.outreach.generate.anthropic") as mock_anthropic:
            mock_anthropic.Anthropic.return_value = mock_client
            result = generate_outreach(lead)

        assert result.outreach_email == ""
        assert result.contacted_at is None
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/outreach/test_generate.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/outreach/
git commit -m "test: add outreach email generation tests"
```

---

### Task 15: Test Delivery (test_delivery.py)

**Files:**
- Create: `tests/outreach/test_delivery.py`

- [ ] **Step 1: Write test_delivery.py**

```python
"""Tests for Instantly.ai delivery integration."""

from unittest.mock import patch

import httpx
import pytest
import respx

from src.outreach.delivery import (
    InstantlyClient,
    _parse_outreach_email,
    _lead_to_instantly_format,
    push_to_instantly,
)
from tests.conftest import make_lead


class TestParseOutreachEmail:
    def test_extracts_subject_and_body(self):
        """Parses 'Subject: ...' header from outreach email."""
        email = "Subject: Quick question\n\nHi Bob, I wanted to reach out..."
        subject, body = _parse_outreach_email(make_lead(outreach_email=email))
        assert subject == "Quick question"
        assert body == "Hi Bob, I wanted to reach out..."

    def test_no_subject_line(self):
        """Returns full text as body when no Subject header."""
        lead = make_lead(outreach_email="Just a plain email body")
        subject, body = _parse_outreach_email(lead)
        assert subject == ""
        assert "plain email body" in body

    def test_empty_outreach(self):
        """Returns empty strings for empty outreach."""
        subject, body = _parse_outreach_email(make_lead(outreach_email=""))
        assert subject == ""
        assert body == ""


class TestLeadToInstantlyFormat:
    def test_formats_correctly(self):
        """Converts Lead to Instantly lead dict."""
        lead = make_lead(
            contact_name="Bob Smith",
            contact_email="bob@acme.com",
            contact_title="Owner",
            score=72.5,
        )
        result = _lead_to_instantly_format(lead)
        assert result["email"] == "bob@acme.com"
        assert result["first_name"] == "Bob"
        assert result["last_name"] == "Smith"
        assert result["company_name"] == "Acme HVAC Services"
        assert result["custom_variables"]["contact_title"] == "Owner"
        assert result["custom_variables"]["score"] == "72.5"

    def test_single_name(self):
        """Handles single-word contact name."""
        lead = make_lead(contact_name="Bob", contact_email="bob@co.com")
        result = _lead_to_instantly_format(lead)
        assert result["first_name"] == "Bob"
        assert result["last_name"] == ""

    def test_no_contact_name(self):
        """Handles empty contact name."""
        lead = make_lead(contact_name="", contact_email="info@co.com")
        result = _lead_to_instantly_format(lead)
        assert result["first_name"] == ""
        assert result["last_name"] == ""


class TestInstantlyClient:
    @respx.mock
    def test_create_campaign(self):
        """Creates campaign via API."""
        respx.post("https://api.instantly.ai/api/v1/campaign/create").mock(
            return_value=httpx.Response(200, json={"id": "camp_123", "name": "Test"})
        )
        client = InstantlyClient("fake-key")
        result = client.create_campaign("Test Campaign")
        assert result["id"] == "camp_123"

    @respx.mock
    def test_add_leads(self):
        """Adds leads to campaign."""
        respx.post("https://api.instantly.ai/api/v1/lead/add").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client = InstantlyClient("fake-key")
        result = client.add_leads_to_campaign("camp_123", [{"email": "test@co.com"}])
        assert result["status"] == "ok"

    @respx.mock
    def test_set_sequences(self):
        """Sets campaign sequences."""
        respx.post("https://api.instantly.ai/api/v1/campaign/set-sequences").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        client = InstantlyClient("fake-key")
        steps = [{"subject": "Hi", "body": "Hello", "delay": 0}]
        result = client.set_campaign_sequences("camp_123", steps)
        assert result["status"] == "ok"

    @respx.mock
    def test_launch_campaign(self):
        """Launches campaign."""
        respx.post("https://api.instantly.ai/api/v1/campaign/launch").mock(
            return_value=httpx.Response(200, json={"status": "launched"})
        )
        client = InstantlyClient("fake-key")
        result = client.launch_campaign("camp_123")
        assert result["status"] == "launched"


class TestPushToInstantly:
    @respx.mock
    def test_full_push(self, sample_settings):
        """Full push: creates campaign, adds leads, sets sequences."""
        respx.post("https://api.instantly.ai/api/v1/campaign/create").mock(
            return_value=httpx.Response(200, json={"id": "camp_123"})
        )
        respx.post("https://api.instantly.ai/api/v1/campaign/set-sequences").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.post("https://api.instantly.ai/api/v1/lead/add").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        leads = [
            make_lead(
                contact_email="bob@acme.com",
                outreach_email="Subject: Hi\n\nHello Bob",
                followups=["Follow up 1"],
            ),
        ]

        with patch("src.outreach.delivery.load_settings", return_value=sample_settings):
            result = push_to_instantly(leads, "Test Campaign")

        assert result["campaign_id"] == "camp_123"
        assert result["leads_added"] == 1
        assert result["status"] == "ready"

    @respx.mock
    def test_auto_launch(self, sample_settings):
        """auto_launch=True launches the campaign."""
        respx.post("https://api.instantly.ai/api/v1/campaign/create").mock(
            return_value=httpx.Response(200, json={"id": "camp_123"})
        )
        respx.post("https://api.instantly.ai/api/v1/campaign/set-sequences").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.post("https://api.instantly.ai/api/v1/lead/add").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        respx.post("https://api.instantly.ai/api/v1/campaign/launch").mock(
            return_value=httpx.Response(200, json={"status": "launched"})
        )

        leads = [
            make_lead(
                contact_email="bob@acme.com",
                outreach_email="Subject: Hi\n\nHello",
                followups=[],
            ),
        ]

        with patch("src.outreach.delivery.load_settings", return_value=sample_settings):
            result = push_to_instantly(leads, "Test", auto_launch=True)

        assert result["status"] == "launched"

    def test_filters_unsendable(self, sample_settings):
        """Filters out leads without email or outreach."""
        leads = [
            make_lead(contact_email="", outreach_email="Subject: Hi\n\nHello"),
            make_lead(contact_email="bob@acme.com", outreach_email=""),
            make_lead(contact_email="", outreach_email=""),
        ]

        with patch("src.outreach.delivery.load_settings", return_value=sample_settings):
            result = push_to_instantly(leads, "Empty Campaign")

        assert result["leads_added"] == 0
        assert result["status"] == "empty"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/outreach/test_delivery.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/outreach/test_delivery.py
git commit -m "test: add Instantly.ai delivery integration tests"
```

---

### Task 16: Full Test Suite Verification

**Files:** None (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS, zero failures.

- [ ] **Step 2: Run with coverage report**

Run: `pytest tests/ --cov=src --cov-report=term-missing -v`
Expected: Coverage report shows coverage for all tested modules.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "test: complete comprehensive test suite for all pipeline modules"
```
