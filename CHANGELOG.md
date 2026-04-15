# Changelog — biz-prospector

All notable changes to this project are documented here.

## [Unreleased]

### Added
- Solo-orchestrator framework adoption (phase-gating, CI pipeline, security scanning)

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
