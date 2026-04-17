# Changelog — biz-prospector

All notable changes to this project are documented here.

## [Unreleased]

### Added
- **TUI dashboard** — Interactive Textual-based terminal dashboard (`python -m src.pipeline tui`) with leads browser, run history, and stats views
- **SQLite backend** — replaced all JSON file I/O with SQLite database (`data/biz-prospector.db`)
- Pipeline run tracking (`pipeline_runs` table) with stats command
- `import-json` and `export-json` CLI commands for data portability
- Flexible lead queries by metro, category, score threshold
- Solo-orchestrator framework adoption (phase-gating, CI pipeline, security scanning)
- Employee title analysis via Apollo People Search (free endpoint) for scoring
- Business age scoring from Apollo organization data (founded year)
- LinkedIn URL capture for contacts
- Scheduled pipeline runs via crontab (schedule install/list/remove commands)
- Re-enrich command for refreshing stale scored leads
- Email summary notifications after scheduled runs (SMTP, HTML digest with report attachment)

### Changed
- `enrich`, `score`, `outreach`, `report` commands now use `--metro`/`--category` filters instead of `--input` file paths
- Dedup tracking moved from JSON files to SQLite `dedup` table
- `stats` command shows pipeline run history table instead of file counts

### Removed
- JSON file I/O for lead storage (replaced by SQLite)
- `save_leads()` standalone function from google_maps scraper

## [0.1.0] — 2026-04-14 (Retroactive)

### Added
- Google Maps scraper with SerpAPI and Apify providers
- Website auditor with HTML-based tech/tool detection
- BuiltWith API integration for tech stack enrichment
- Review scraper with Outscraper + ops complaint sentiment analysis
- Job posting scraper with manual process keyword matching
- Contact enrichment via Apollo/Hunter waterfall with email verification
- Weighted multi-factor scoring engine (8 factors)
- 8 vertical configs: hvac, dental, legal, property_management, construction, insurance, accounting, auto_repair
- Outreach email generation via Claude API
- Instantly.ai delivery integration (campaigns, leads, sequences)
- Full CLI pipeline orchestrator (Click-based)
- Async concurrent enrichment with per-service rate limiting
- Deduplication across pipeline runs
- Retry logic with exponential backoff
- HTML report generator (score distributions, top leads, tech stack, tool gaps)
- Comprehensive test suite (375 tests, 99% branch coverage)
