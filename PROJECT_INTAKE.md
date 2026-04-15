# Project Intake — biz-prospector

## Product Name
biz-prospector

## Description
CLI pipeline for finding businesses that need AI/automation modernization, scoring them on likelihood to benefit, and generating personalized cold outreach emails.

## Target Users
Solo consultants and agencies selling AI/automation services to local businesses.

## Architecture
Linear pipeline with 4 stages, each runnable independently or chained:
1. **Scrape** — Google Maps listings, reviews, job postings (SerpAPI, Apify, Outscraper)
2. **Enrich** — Website audit for CRM/chat/scheduling/tech stack (HTML detection + BuiltWith API), contact enrichment (Apollo/Hunter waterfall)
3. **Score** — Weighted multi-factor scoring, configurable per vertical (8 verticals supported)
4. **Outreach** — Claude API generates personalized emails, Instantly.ai delivers campaigns

## API Dependencies
- SerpAPI: Google Maps scraping, job posting search
- Apify: Alternative Google Maps scraping provider
- Outscraper: Google review scraping
- BuiltWith: Tech stack lookups
- Apollo: Contact enrichment (primary)
- Hunter: Contact enrichment (fallback) + email verification
- Anthropic Claude: Outreach email generation
- Instantly.ai: Email campaign delivery

## Data Flow
All stages read/write JSON files in `data/` subdirectories. The `Lead` Pydantic model in `src/models.py` is the shared schema — it accumulates fields as it flows through the pipeline.

## Constraints
- Python 3.11+
- CLI-only (Click framework)
- Config-driven via `config/settings.yaml`
- All intermediate data is JSON in `data/` subdirs
- Dependencies in `requirements.txt`

## Success Criteria
- Find businesses needing modernization based on missing CRM, scheduling, chat tools
- Score leads 0-100 based on configurable weighted factors
- Generate personalized outreach emails using enrichment data
- Deliver campaigns via Instantly.ai with follow-up sequences
- Support multiple business verticals with per-vertical keyword and weight configs
