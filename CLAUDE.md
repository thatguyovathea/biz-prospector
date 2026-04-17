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
All stages read/write a SQLite database at `data/biz-prospector.db` via `src/db.py`. The `Lead` model in `src/models.py` is the shared schema across all stages — it accumulates fields as it flows through the pipeline. List/dict fields are stored as JSON text columns. Pipeline runs are tracked in a `pipeline_runs` table.

## Key files
- `src/models.py` — Pydantic models (Lead, PipelineConfig, VerticalConfig)
- `src/db.py` — SQLite storage backend (schema, Lead ↔ row serialization, queries, dedup, run tracking)
- `src/config.py` — YAML config loader
- `src/pipeline.py` — CLI entry point and orchestrator (Click-based)
- `config/settings.example.yaml` — All config including API keys, scoring weights, keyword lists

## Running
```bash
python -m src.pipeline run --vertical hvac --metro portland-or
python -m src.pipeline scrape --vertical dental --metro seattle-wa
python -m src.pipeline enrich --metro portland-or
python -m src.pipeline score --metro portland-or --vertical hvac
python -m src.pipeline outreach --min-score 55 --metro portland-or
python -m src.pipeline import-json --input data/raw/leads.json
python -m src.pipeline export-json --output leads.json --metro portland-or --min-score 55
python -m src.pipeline stats
python -m src.pipeline tui
```

## APIs used
- SerpAPI or Apify: Google Maps scraping, job posting search
- Outscraper: Google review scraping
- BuiltWith: Tech stack lookups (integrated via BuiltWith Domain API v22)
- Apollo/Hunter: Contact enrichment (Apollo primary, Hunter fallback, email verification)
- Anthropic Claude: Outreach email generation
- Instantly.ai: Email delivery (campaign creation, lead push, sequence setup)

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
- Vertical configs: HVAC, dental, legal, property management, construction, insurance, accounting, auto repair

### TODO — priority order:
1. ~~BuiltWith API integration~~ ✓
2. ~~Tests~~ ✓ (543 tests)
3. ~~HTML report generator~~ ✓
4. ~~More verticals~~ ✓ (construction, insurance, accounting, auto repair)
5. ~~LinkedIn enrichment for employee title analysis~~ ✓
6. ~~Scheduled/cron pipeline runs~~ ✓
7. ~~SQLite backend~~ ✓ (replaced JSON files with SQLite via src/db.py)
8. ~~Web dashboard~~ ✓ (replaced with Textual TUI dashboard — `python -m src.pipeline tui`)

## Constraints
- Settings in config/settings.yaml (copy from settings.example.yaml)
- All data stored in SQLite at data/biz-prospector.db (use import-json/export-json for JSON interop)
- Python 3.11+, dependencies in requirements.txt

## Solo Orchestrator Framework

This project follows the [solo-orchestrator](https://github.com/kraulerson/solo-orchestrator) development methodology. The framework is installed as a git submodule at `.claude/framework/`.

### Current Phase
Read `.claude/phase-state.json` for the current phase. Phase gate criteria are enforced by `scripts/check-phase-gate.sh` and the CI pipeline.

### Five-Phase Model
- **Phase 0:** Product Discovery → Product Manifesto (`PROJECT_INTAKE.md`)
- **Phase 1:** Architecture & Planning → Project Bible
- **Phase 2:** Construction → Working codebase with tests (CURRENT)
- **Phase 3:** Validation & Security → Scan results and test evidence
- **Phase 4:** Release & Maintenance → Deployment readiness

### Development Rules
- **Tests first** — write failing tests before implementation code (TDD)
- **No secrets in code** — API keys go in `config/settings.yaml` (gitignored), never in source
- **Update artifacts** — when adding a feature update `FEATURES.md`; when changing behavior update `CHANGELOG.md`; when finding a bug add to `BUGS.md`
- **Phase gates** — run `bash scripts/check-phase-gate.sh` before requesting a phase transition

### Pre-commit Hook
Install the pre-commit hook (not tracked by git):
```bash
cp docs/reference/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```
The hook runs gitleaks for secret detection and warns if source files are committed without tests.

### CI Pipeline
GitHub Actions runs on push/PR to main: lint (ruff), test (pytest), SAST (Semgrep), secret detection (gitleaks), dependency audit (pip-audit), license check (pip-licenses), phase gate validation.
