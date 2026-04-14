# Comprehensive Test Suite — Design Spec

## Goal

Add full pytest test coverage to biz-prospector. Every module in `src/` gets a corresponding test file. External API calls are mocked so tests run offline with no API keys.

## Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── test_models.py                 # Pydantic model validation
├── test_config.py                 # YAML config loading
├── test_dedup.py                  # Deduplication logic
├── test_rate_limit.py             # Rate limiter behavior
├── scrapers/
│   ├── __init__.py
│   ├── test_google_maps.py        # SerpAPI/Apify response parsing + Lead creation
│   ├── test_reviews.py            # Review sentiment analysis + Outscraper mock
│   └── test_job_posts.py          # Job posting analysis + search mock
├── enrichment/
│   ├── __init__.py
│   ├── test_website_audit.py      # HTML pattern matching (CRM, chat, scheduling, tech stack)
│   ├── test_contacts.py           # Apollo/Hunter waterfall + contact ranking
│   └── test_async_processor.py    # Async orchestration with mocked services
├── scoring/
│   ├── __init__.py
│   └── test_score.py              # Scoring engine with parametrized weight combos
└── outreach/
    ├── __init__.py
    ├── test_generate.py           # Claude API email generation (mocked)
    └── test_delivery.py           # Instantly.ai integration (mocked)
```

## Dependencies

Add to requirements.txt:
- `pytest>=8.0`
- `pytest-asyncio>=0.23`
- `respx>=0.21` (httpx mocking library — cleaner than pytest-httpx for this project)

## Shared Fixtures (`conftest.py`)

### `sample_lead(**overrides)` — Factory fixture
Returns a Lead with realistic defaults. Any field can be overridden:
```python
def sample_lead(**overrides):
    defaults = {
        "id": "abc123def456",
        "business_name": "Acme HVAC Services",
        "address": "123 Main St, Portland, OR 97201",
        "phone": "(503) 555-0100",
        "website": "https://acmehvac.com",
        "category": "HVAC",
        "metro": "portland-or",
        "source": "google_maps",
        # ... all fields with sensible test defaults
    }
    defaults.update(overrides)
    return Lead(**defaults)
```

### `sample_settings()` — Minimal config dict
Returns settings with fake API keys and default values. No real secrets.

### `sample_vertical_config(name="hvac")` — Vertical config
Returns a known vertical config dict for deterministic scoring tests.

### `tmp_data_dir(tmp_path)` — Isolated data directory
Creates a temporary data directory for dedup and file I/O tests. Avoids touching real `data/`.

### `mock_html(techs=[], has_crm=False, has_chat=False, has_scheduling=False)` — HTML builder
Generates fake HTML with specific technology markers embedded, for website audit tests.

## Test Plan by Module

### `test_models.py` — Pydantic Model Validation
- Valid Lead construction with all fields
- Valid Lead construction with minimal fields (only required)
- Default values are correct (e.g., score=None, tech_stack=[])
- Invalid field types raise ValidationError (e.g., score="not a number")
- LeadSource enum values
- PipelineConfig and VerticalConfig validation

### `test_config.py` — Config Loading
- `load_settings()` reads YAML correctly from a temp file
- `load_settings()` raises on missing file
- `load_vertical()` reads vertical YAML
- `load_vertical()` returns empty dict for missing vertical
- `get_api_key()` retrieves existing key
- `get_api_key()` raises on missing key

### `test_dedup.py` — Deduplication
- `filter_new_leads()` returns all leads on first run (empty dedup file)
- `filter_new_leads()` filters out previously processed leads
- `mark_processed()` writes lead IDs with timestamps
- `mark_processed()` appends to existing processed dict (doesn't overwrite)
- `reset_stage()` clears the dedup file for a stage
- `get_stats()` returns correct counts per stage
- Concurrent calls don't corrupt the JSON file
- Handles malformed dedup JSON gracefully

### `test_rate_limit.py` — Rate Limiter
- `RateLimiter` allows calls within rate limit
- `RateLimiter` blocks when limit exceeded (verify delay)
- `async_wait()` works in async context
- Different services get independent limiters
- `@rate_limited` decorator applies limiting
- `@retry_with_rate_limit` retries on 429 and 5xx

### `tests/scrapers/test_google_maps.py` — Google Maps Scraper
- `parse_serpapi_result()` correctly extracts Lead fields from SerpAPI JSON
- `parse_apify_result()` correctly extracts Lead fields from Apify JSON
- ID generation is deterministic (same name+address = same ID)
- Duplicate results are filtered
- Missing fields handled gracefully (e.g., no phone number)
- `scrape_google_maps()` with mocked SerpAPI response returns leads
- `scrape_google_maps()` with mocked Apify response returns leads
- Pagination works for SerpAPI (multiple pages)

### `tests/scrapers/test_reviews.py` — Review Analysis
- `analyze_reviews()` counts ops complaints correctly
- `analyze_reviews()` only considers negative reviews (rating <= 3)
- `analyze_reviews()` calculates owner response rate
- `analyze_reviews()` limits samples to 5
- Reviews with no complaint keywords return zero complaints
- `fetch_reviews_outscraper()` with mocked response returns reviews
- `enrich_lead_with_reviews()` updates Lead fields correctly

### `tests/scrapers/test_job_posts.py` — Job Post Analysis
- `analyze_job_postings()` detects manual process keywords in title
- `analyze_job_postings()` detects manual process keywords in description
- `analyze_job_postings()` returns correct counts and titles
- No matching keywords returns zero manual process postings
- `search_jobs_serpapi()` with mocked response returns postings
- `enrich_lead_with_jobs()` updates Lead fields correctly

### `tests/enrichment/test_website_audit.py` — Website Audit (Pattern Matching)
The most important test file — validates all detection patterns work:

**CRM detection** (parametrized across all patterns):
- HubSpot, Salesforce, Pipedrive, Zoho, Freshsales, Keap/Infusionsoft detected
- Non-CRM HTML returns has_crm=False

**Chat widget detection** (parametrized):
- Intercom, Drift, Crisp, Tawk.to, LiveChat, Zendesk, Freshchat, Tidio, Chatwoot detected
- Non-chat HTML returns has_chat=False

**Scheduling detection** (parametrized):
- Calendly, Acuity, Cal.com, Square Appointments, Booksy, Vagaro, Setmore detected
- Non-scheduling HTML returns has_scheduling=False

**Tech stack detection** (parametrized):
- WordPress, Wix, Squarespace, Shopify, Webflow detected
- Google Analytics, GTM, Facebook Pixel detected
- Bootstrap, Tailwind, React, Angular, Vue detected

**Outdated signals**:
- jQuery 1.x/2.x flagged, jQuery 3.x not flagged
- Old WordPress versions flagged
- Framesets, marquee, blink, flash detected

**Other checks**:
- SSL detection (https vs http)
- Mobile responsiveness (viewport meta tag present/absent)
- Unreachable website handling (connection error → reachable=False)
- Redirect handling
- Timeout handling

### `tests/enrichment/test_contacts.py` — Contact Enrichment
- `search_apollo()` with mocked response returns contacts
- `search_hunter()` with mocked response returns contacts
- `_pick_best_contact()` prefers owner/founder over other titles
- `_pick_best_contact()` prefers contacts with emails
- `verify_email_hunter()` with mocked response returns status
- Waterfall: Apollo success → no Hunter call
- Waterfall: Apollo fails → falls back to Hunter
- Empty results from both → Lead contact fields stay None

### `tests/enrichment/test_async_processor.py` — Async Processing
- `run_async_enrichment()` calls all enrichment services per lead
- Concurrency semaphore limits parallel calls
- Failed enrichment for one lead doesn't block others
- Results preserve original lead order
- Rate limiters are applied per service

### `tests/scoring/test_score.py` — Scoring Engine
The second most important test file — validates all scoring logic:

**Individual factor scoring** (parametrized):
- `website_outdated`: no SSL (0.3), not mobile (0.4), no modern tech (0.3), combinations
- `no_crm_detected`: True → 1.0, False → 0.0
- `no_scheduling_tool`: True → 1.0, False → 0.0
- `no_chat_widget`: True → 1.0, False → 0.0
- `manual_job_postings`: 0 → 0.0, 1 → ~0.33, 3+ → 1.0
- `negative_reviews_ops`: complaint ratios, owner response rate bonus

**Composite scoring**:
- Perfect lead (all tools present, no complaints) scores near 0
- Worst-case lead (nothing modern, many complaints) scores near 100
- Default weights sum correctly
- Score is always in 0-100 range

**Vertical overrides**:
- HVAC weights applied correctly (scheduling=20, reviews=20)
- Dental weights applied correctly (scheduling=25)
- Legal weights applied correctly (CRM=20)
- Property management weights applied correctly

**Edge cases**:
- Lead with no enrichment data (all None/empty) → sensible score
- Lead with partial enrichment → only scored on available factors
- Custom weight dict → applied correctly
- Zero-weight factor → excluded from score

**Breakdown output**:
- `score_breakdown` dict contains all factors
- Each factor value is between 0 and 1

### `tests/outreach/test_generate.py` — Email Generation
- `_build_lead_context()` includes all relevant Lead fields
- `_build_lead_context()` omits None/empty fields
- `generate_outreach()` with mocked Claude response sets outreach_email
- `generate_outreach()` with mocked response sets followups
- `generate_outreach()` sets contacted_at timestamp
- Malformed Claude response handled gracefully

### `tests/outreach/test_delivery.py` — Instantly.ai Integration
- `InstantlyClient.create_campaign()` with mocked API
- `InstantlyClient.add_leads_to_campaign()` formats lead data correctly
- `InstantlyClient.set_campaign_sequences()` sets initial + followups
- `push_to_instantly()` filters leads without email/outreach
- `push_to_instantly()` creates campaign and adds leads
- `push_to_instantly()` with auto_launch=False doesn't launch
- `push_to_instantly()` with auto_launch=True launches campaign

## Mocking Strategy

- **httpx calls**: Use `respx` library to mock all HTTP requests. Each test file sets up route mocks matching the real API endpoints.
- **File I/O**: Use pytest's `tmp_path` fixture for any file reads/writes (dedup, config).
- **Claude API**: Mock `anthropic.Anthropic().messages.create()` with `unittest.mock.patch`.
- **Async**: Use `pytest-asyncio` with `@pytest.mark.asyncio` for async tests.
- **No real API keys needed**: All external calls mocked. Tests run fully offline.

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific module
pytest tests/scoring/test_score.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

## Success Criteria

- All tests pass with `pytest tests/ -v`
- No test requires real API keys or network access
- Each source module has corresponding test coverage
- Scoring edge cases are thoroughly parametrized
- Website audit patterns are individually tested
