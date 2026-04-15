# Solo Orchestrator Framework Adoption — Design Spec

## Overview

Full adoption of the [solo-orchestrator framework](https://github.com/kraulerson/solo-orchestrator) into the existing biz-prospector project. The framework provides phase-gated, test-driven, security-scanning development methodology for solo builders using AI as the execution layer.

**Track:** Standard
**Governance:** Private POC (sole approver)
**Phase entry:** Phase 2 (Construction) — retroactive Phase 0-1 artifacts produced at adoption time
**CI/CD:** GitHub Actions with full Python pipeline
**Approach:** Framework-as-Submodule — the solo-orchestrator repo lives in `.claude/framework/` as a git submodule

## Repository Structure

```
biz-prospector/
├── .claude/
│   ├── framework/                    ← git submodule → kraulerson/solo-orchestrator
│   ├── framework-config.yml          ← project profile config
│   ├── framework-version.txt         ← pinned framework commit SHA
│   ├── phase-state.json              ← current phase tracking
│   ├── build-progress.json           ← feature/test cycle tracking
│   ├── process-state.json            ← build loop enforcement
│   └── settings.local.json           ← (already exists, unchanged)
├── .github/workflows/
│   ├── ci.yml                        ← Python CI pipeline
│   └── release.yml                   ← tag-triggered release pipeline
├── .git/hooks/
│   └── pre-commit                    ← gitleaks + TDD ordering check
├── CLAUDE.md                         ← updated with phase-gate methodology
├── PROJECT_INTAKE.md                 ← product definition (retrofitted)
├── APPROVAL_LOG.md                   ← phase gate approvals
├── FEATURES.md                       ← living feature reference
├── BUGS.md                           ← bug tracking
├── CHANGELOG.md                      ← change log
├── RELEASE_NOTES.md                  ← user-facing release history
├── docs/
│   ├── reference/                    ← symlinks to framework's builders-guide.md, user-guide.md, security-scan-guide.md
│   ├── ADR documentation/            ← architecture decision records
│   ├── test-results/                 ← Phase 3 evidence
│   └── superpowers/                  ← (already exists)
├── evaluation-prompts/
│   └── Projects/                     ← 6 adversarial reviewer prompts
└── scripts/
    ├── validate.sh                   ← compliance checking
    ├── check-phase-gate.sh           ← phase validation
    └── check-updates.sh              ← framework update checker
```

## Phase State & Retrofit Strategy

### Initial phase-state.json

```json
{
  "project": "biz-prospector",
  "framework_version": "1.0",
  "current_phase": 2,
  "track": "standard",
  "deployment": "personal",
  "poc_mode": "private-poc",
  "compliance_ready": false,
  "gates": {
    "phase_0_to_1": "2026-04-14",
    "phase_1_to_2": "2026-04-14",
    "phase_2_to_3": null,
    "phase_3_to_4": null
  }
}
```

Phases 0 and 1 are retroactively gated. The project enters Phase 2 active.

### framework-config.yml

```yaml
project: biz-prospector
track: standard
platform: web-api
language: python
governance: private-poc
test_interval: 2
uat_required: false
```

### Retroactive Artifacts

**PROJECT_INTAKE.md** — Derived from existing CLAUDE.md. Contains:
- Product name, description, target users
- Architecture overview (4-stage pipeline)
- API dependencies (SerpAPI, Apify, Outscraper, BuiltWith, Apollo, Hunter, Anthropic, Instantly)
- Data flow (JSON files in data/ subdirectories)
- Constraints (Python 3.11+, CLI-only, config-driven)
- Success criteria (find businesses needing modernization, score them, generate outreach)

**APPROVAL_LOG.md** — Pre-populated with:
- Phase 0→1 approval: dated 2026-04-14, note "retroactive — project existed prior to framework adoption"
- Phase 1→2 approval: dated 2026-04-14, same note

**FEATURES.md** — Populated from existing functionality:
- Google Maps scraping (SerpAPI + Apify providers)
- Website auditing (HTML detection + BuiltWith API)
- Review scraping + sentiment analysis
- Job posting scraping + keyword matching
- Contact enrichment (Apollo/Hunter waterfall + email verification)
- Scoring engine with configurable weights per vertical
- Outreach email generation via Claude API
- Instantly.ai delivery integration
- Async concurrent enrichment with rate limiting
- Deduplication across pipeline runs
- HTML report generation
- 8 vertical configs (hvac, dental, legal, property_management, construction, insurance, accounting, auto_repair)

**CHANGELOG.md** — Single retroactive entry covering all work prior to framework adoption.

**BUGS.md** — Empty, no known bugs. Format established for future use.

**RELEASE_NOTES.md** — Empty, no releases yet.

## CI Pipeline

`.github/workflows/ci.yml` runs on push/PR to `main`, single job on `ubuntu-latest`:

1. **Checkout** — with `submodules: recursive` to pull `.claude/framework/`
2. **Setup Python** — 3.11
3. **Install dependencies** — `pip install -r requirements.txt`
4. **Install dev tools** — `pip install ruff pytest pytest-cov pip-audit pip-licenses`
5. **Lint** — `ruff check .`
6. **Test** — `pytest --cov=src --cov-branch --cov-fail-under=95`
7. **SAST** — Semgrep GitHub Action (OWASP Top Ten + security-audit rulesets)
8. **Secret detection** — gitleaks GitHub Action
9. **Dependency audit** — `pip-audit` (fail on known vulnerabilities)
10. **License check** — `pip-licenses --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0;LGPL-2.0;LGPL-2.1;LGPL-3.0;SSPL-1.0;EUPL-1.1;EUPL-1.2"`
11. **Phase gate check** — `bash scripts/check-phase-gate.sh`
12. **Approval log integrity** — verify APPROVAL_LOG.md is append-only (no deleted/modified lines vs base branch)

`.github/workflows/release.yml` — tag-triggered, builds wheel and source dist. Minimal since this is a CLI tool.

All GitHub Action versions pinned by commit SHA (not tags) for supply chain security.

## Pre-commit Hook

`.git/hooks/pre-commit` performs:

1. **gitleaks** — scan staged files for patterns matching API keys, tokens, passwords. Exit 1 if found.
2. **TDD ordering check** — if any `src/**/*.py` files are staged without a corresponding `tests/**/*.py` file also staged, print a warning. Warning only, does not block commit.

Installed by a setup script or manually copied. Not managed by the submodule.

## Validation Scripts

### scripts/check-phase-gate.sh

Reads `.claude/phase-state.json` and validates current phase requirements:

- **Phase 2→3 gate:** `FEATURES.md` exists, `CHANGELOG.md` exists, `BUGS.md` has zero SEV-1/SEV-2 open, all tests pass, CI green
- **Phase 3→4 gate:** `docs/test-results/` non-empty, `SECURITY.md` exists, security scan results clean, evaluation prompts completed
- Returns exit 0 (pass) or exit 1 (fail with details printed to stdout)

### scripts/validate.sh

General compliance checking:
- All required framework files exist (phase-state.json, framework-config.yml, APPROVAL_LOG.md, etc.)
- APPROVAL_LOG.md follows correct format
- phase-state.json is valid JSON with required fields
- No secrets in tracked files (quick gitleaks scan)

### scripts/check-updates.sh

Compares `.claude/framework/` submodule HEAD against latest `kraulerson/solo-orchestrator` main. Prints whether an update is available and how to update.

## Evaluation Prompts

Six adversarial reviewer perspectives in `evaluation-prompts/Projects/`:

1. **security-reviewer.md** — API key handling, PII in scraped data, GDPR/CAN-SPAM compliance, secret storage
2. **architecture-reviewer.md** — pipeline stage coupling, JSON file scalability, error recovery, async patterns
3. **ux-operations-reviewer.md** — CLI usability, error messages, rate limit feedback, progress indicators
4. **data-quality-reviewer.md** — scraping accuracy, dedup reliability, scoring calibration across verticals
5. **compliance-reviewer.md** — email outreach legality, scraping ToS compliance, data retention policies
6. **performance-reviewer.md** — async throughput, rate limit efficiency, large batch handling, memory usage

Each is a markdown file with a structured prompt that can be fed to an AI reviewer during Phase 3 validation.

## CLAUDE.md Updates

The existing CLAUDE.md gets these additions:

- **Framework section** — overview of solo-orchestrator adoption, link to phase-state.json
- **Phase methodology** — summary of 5-phase process, current phase, gate criteria
- **TDD mandate** — tests first, implementation second
- **Security requirements** — no secrets in code, run scans before phase transitions
- **Artifact checklist** — which docs to update when (FEATURES.md on new feature, CHANGELOG.md on changes, BUGS.md on bugs found)

Existing content (architecture, running, APIs, constraints) remains unchanged.

## What Does NOT Change

- `src/` directory structure — untouched
- `tests/` directory structure — untouched
- `config/` directory — untouched
- `data/` directory — untouched
- `requirements.txt` — no new runtime dependencies (dev tools installed separately in CI)
- Existing test suite (375 tests, 99% coverage) — untouched
- Existing CLAUDE.md content — augmented, not replaced
