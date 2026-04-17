# Features — biz-prospector

Living reference of all implemented features.

## Scraping
- **Google Maps scraping** — SerpAPI and Apify providers, configurable result count, deduplication by business name + address
- **Review scraping** — Outscraper integration, sentiment analysis for ops complaint keywords
- **Job posting scraping** — SerpAPI and Apify, keyword matching for manual process indicators

## Enrichment
- **Website auditing** — HTML-based detection of CRM, chat widgets, scheduling tools, SSL, mobile responsiveness
- **BuiltWith API integration** — Tech stack detection via BuiltWith Domain API v22, merged with HTML detection
- **Contact enrichment** — Apollo (primary) → Hunter (fallback) waterfall, email verification, title-priority ranking
- **Employee title analysis** — Apollo People Search fetches employee rosters, classifies titles as manual-process or tech-maturity signals, feeds into scoring
- **Async concurrent enrichment** — Semaphore-based concurrency with per-service rate limiting

## Scoring
- **Weighted multi-factor scoring** — 8 factors: website outdated, no CRM, no scheduling, no chat, manual job postings, negative reviews, business age, employee count
- **Configurable per vertical** — Weight overrides via YAML configs
- **8 vertical configs** — hvac, dental, legal, property_management, construction, insurance, accounting, auto_repair

## Outreach
- **Email generation** — Claude API generates personalized emails from enrichment data
- **Instantly.ai delivery** — Campaign creation, lead push, sequence setup with follow-ups

## Pipeline
- **CLI orchestrator** — Click-based, run full pipeline or individual stages
- **SQLite backend** — All data stored in SQLite (replaced JSON files), pipeline run tracking, flexible lead queries
- **JSON import/export** — `import-json` and `export-json` commands for data portability
- **Deduplication** — Track processed leads across pipeline runs (SQLite-backed)
- **HTML report generation** — Score distributions, top leads, tech stack breakdown, tool gaps
- **Rate limiting** — Token bucket pattern with configurable per-service limits
- **Retry logic** — Exponential backoff for all HTTP calls
- **Scheduled runs** — Cron-based automation with install/list/remove management
- **Re-enrichment** — Refresh stale leads (older than N days) with updated data
- **Email summaries** — HTML digest of top leads sent after each scheduled run
