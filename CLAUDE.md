# CLAUDE.md — Project context for Claude Code

## What this is
biz-prospector is a CLI pipeline for finding businesses that need AI/automation modernization, scoring them on how likely they are to benefit, and generating personalized cold outreach emails.

## Architecture
Linear pipeline with 4 stages, each runnable independently or chained:
1. **Scrape** (`src/scrapers/`) — Google Maps listings, reviews, job postings
2. **Enrich** (`src/enrichment/`) — Website audit (CRM, chat, scheduling, tech stack detection)
3. **Score** (`src/scoring/`) — Weighted multi-factor scoring, configurable per vertical
4. **Outreach** (`src/outreach/`) — Claude API generates personalized emails from enrichment data

## Data flow
All stages read/write JSON files in `data/` subdirectories. The `Lead` model in `src/models.py` is the shared schema across all stages — it accumulates fields as it flows through the pipeline.

## Key files
- `src/models.py` — Pydantic models (Lead, PipelineConfig, VerticalConfig)
- `src/config.py` — YAML config loader
- `src/pipeline.py` — CLI entry point and orchestrator (Click-based)
- `config/settings.example.yaml` — All config including API keys, scoring weights, keyword lists

## Running
```bash
python -m src.pipeline run --vertical hvac --metro portland-or
python -m src.pipeline scrape --vertical dental --metro seattle-wa
python -m src.pipeline enrich --input data/raw/leads.json
python -m src.pipeline score --input data/raw/leads_enriched.json
python -m src.pipeline outreach --input data/scored/leads_scored.json
```

## APIs used
- SerpAPI or Apify: Google Maps scraping, job posting search
- Outscraper: Google review scraping
- BuiltWith: Tech stack lookups (not yet wired in, currently using HTML detection)
- Apollo/Hunter: Contact enrichment (not yet implemented)
- Anthropic Claude: Outreach email generation
- Instantly.ai: Email delivery (not yet implemented)

## What's built vs TODO
### Built (functional structure, needs API keys to run):
- Google Maps scraper (SerpAPI + Apify)
- Website auditor (HTML-based tech detection, CRM/chat/scheduling detection)
- Review scraper + sentiment analysis for ops complaints
- Job posting scraper + manual process keyword matching
- Contact enrichment (Apollo waterfall to Hunter, email verification, title-priority ranking)
- Scoring engine with configurable weights
- Outreach generator via Claude API
- Instantly.ai delivery integration (campaign creation, lead push, sequence setup)
- Full pipeline orchestrator with CLI
- Async concurrent enrichment with per-service rate limiting
- Deduplication across pipeline runs
- Retry logic with exponential backoff for all HTTP calls
- Vertical configs: HVAC, dental, legal, property management

### TODO — priority order:
1. BuiltWith API integration for better tech stack data (currently HTML-only detection)
2. Tests — unit tests for scoring logic, website audit pattern matching, dedup
3. HTML report generator (summary of run results, top leads, score distributions)
4. More verticals (construction, insurance, accounting, auto repair)
5. LinkedIn enrichment for employee title analysis
6. Scheduled/cron pipeline runs
7. SQLite or Postgres backend instead of JSON files (for larger scale)
8. Web dashboard (optional — Flask/FastAPI for non-CLI users)

## Constraints
- Settings in config/settings.yaml (copy from settings.example.yaml)
- All intermediate data is JSON in data/ subdirs
- Python 3.11+, dependencies in requirements.txt
