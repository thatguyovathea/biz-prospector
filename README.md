# biz-prospector

Automated pipeline for finding businesses that need AI/automation modernization, scoring them, and generating personalized outreach.

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌───────────┐
│  Scrapers    │───▶│  Enrichment  │───▶│  Scoring    │───▶│  Outreach    │───▶│  Delivery │
│              │    │              │    │             │    │  Generation  │    │           │
│ google_maps  │    │ website_audit│    │ weighted    │    │ claude API   │    │ instantly │
│ job_posts    │    │ builtwith    │    │ multi-factor│    │ personalized │    │ API push  │
│ reviews      │    │ contacts     │    │ per-vertical│    │ emails       │    │           │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └───────────┘
```

## Pipeline stages

1. **Scrape** — Pull raw business listings from Google Maps by industry + metro
2. **Enrich** — Audit websites, pull tech stack, scrape reviews, cross-ref job postings
3. **Score** — Weighted scoring based on modernization signals
4. **Generate** — Claude API writes personalized outreach per lead
5. **Deliver** — Push sequences to Instantly.ai for sending

## Setup

```bash
# Clone and install
pip install -r requirements.txt

# Copy and fill in API keys
cp config/settings.example.yaml config/settings.yaml

# Run full pipeline for a vertical + metro
python -m src.pipeline --vertical hvac --metro portland-or

# Run individual stages
python -m src.scrapers.google_maps --metro portland-or --vertical hvac
python -m src.enrichment.website_audit --input data/raw/leads.json
python -m src.scoring.score --input data/raw/leads_enriched.json
python -m src.outreach.generate --input data/scored/leads_scored.json
```

## Config

All API keys and scoring weights live in `config/settings.yaml`. Vertical-specific scoring weights live in `config/verticals/`.

## Data flow

All intermediate data stored as JSON in `data/`:
- `data/raw/` — scraped leads, raw reviews, raw job postings
- `data/scored/` — leads with scores attached
- `data/outreach/` — generated email sequences per lead
