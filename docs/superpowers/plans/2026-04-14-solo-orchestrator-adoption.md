# Solo Orchestrator Framework Adoption — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the solo-orchestrator framework into biz-prospector as a git submodule with full phase-gating, CI pipeline, security scanning, and retroactive Phase 0-1 artifacts.

**Architecture:** The solo-orchestrator repo is added as a git submodule at `.claude/framework/`. Project-specific state files (phase-state.json, framework-config.yml) live in `.claude/` alongside it. Validation scripts in `scripts/` enforce phase gates. GitHub Actions CI pipeline runs lint, test, SAST, secret detection, dependency audit, license check, and phase-gate validation on every push/PR.

**Tech Stack:** Bash (scripts), GitHub Actions (CI), gitleaks (secret detection), Semgrep (SAST), pip-audit (dependency scanning), pip-licenses (license compliance), ruff (linting)

---

### Task 1: Add solo-orchestrator as git submodule

**Files:**
- Create: `.gitmodules` (auto-created by git)
- Create: `.claude/framework/` (submodule checkout)
- Create: `.claude/framework-version.txt`

- [ ] **Step 1: Add the submodule**

```bash
cd /Users/rando/Downloads/biz-prospector
git submodule add https://github.com/kraulerson/solo-orchestrator.git .claude/framework
```

- [ ] **Step 2: Pin the framework version**

```bash
cd .claude/framework && git rev-parse HEAD > ../framework-version.txt && cd ../..
```

- [ ] **Step 3: Verify submodule is tracked**

Run: `git status`
Expected: `.gitmodules` and `.claude/framework` shown as new files, `.claude/framework-version.txt` as untracked.

- [ ] **Step 4: Commit**

```bash
git add .gitmodules .claude/framework .claude/framework-version.txt
git commit -m "chore: add solo-orchestrator framework as git submodule"
```

---

### Task 2: Create framework state files

**Files:**
- Create: `.claude/phase-state.json`
- Create: `.claude/framework-config.yml`
- Create: `.claude/build-progress.json`
- Create: `.claude/process-state.json`

- [ ] **Step 1: Create phase-state.json**

Write this exact content to `.claude/phase-state.json`:

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

- [ ] **Step 2: Create framework-config.yml**

Write this exact content to `.claude/framework-config.yml`:

```yaml
project: biz-prospector
track: standard
platform: web-api
language: python
governance: private-poc
test_interval: 2
uat_required: false
```

- [ ] **Step 3: Create build-progress.json**

Write this exact content to `.claude/build-progress.json`:

```json
{
  "features_completed": 12,
  "features_since_last_test": 0,
  "test_interval": 2,
  "uat_sessions": 0,
  "notes": "Retroactive: 12 features built prior to framework adoption. 375 tests, 99% coverage."
}
```

- [ ] **Step 4: Create process-state.json**

Write this exact content to `.claude/process-state.json`:

```json
{
  "current_step": "construction",
  "build_loop_active": true,
  "uat_gate_passed": false,
  "phase_3_validation_started": false,
  "phase_4_release_started": false
}
```

- [ ] **Step 5: Verify all files are valid**

Run: `python -c "import json; [json.load(open(f'.claude/{f}')) for f in ['phase-state.json','build-progress.json','process-state.json']]; print('All JSON valid')"`
Expected: `All JSON valid`

Run: `python -c "import yaml; yaml.safe_load(open('.claude/framework-config.yml')); print('YAML valid')"`
Expected: `YAML valid`

- [ ] **Step 6: Commit**

```bash
git add .claude/phase-state.json .claude/framework-config.yml .claude/build-progress.json .claude/process-state.json
git commit -m "chore: add solo-orchestrator phase state and config files"
```

---

### Task 3: Create retroactive documentation artifacts

**Files:**
- Create: `PROJECT_INTAKE.md`
- Create: `APPROVAL_LOG.md`
- Create: `FEATURES.md`
- Create: `BUGS.md`
- Create: `CHANGELOG.md`
- Create: `RELEASE_NOTES.md`
- Create: `SECURITY.md`

- [ ] **Step 1: Create PROJECT_INTAKE.md**

Write to `PROJECT_INTAKE.md`:

```markdown
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
```

- [ ] **Step 2: Create APPROVAL_LOG.md**

Write to `APPROVAL_LOG.md`:

```markdown
# Approval Log — biz-prospector

All phase gate approvals are recorded here. This file is append-only.

---

## Phase 0 → Phase 1 (Product Discovery → Architecture)
**Date:** 2026-04-14
**Approver:** Project Owner
**Status:** APPROVED
**Note:** Retroactive — project existed prior to solo-orchestrator framework adoption. Product definition derived from existing CLAUDE.md and working codebase.

---

## Phase 1 → Phase 2 (Architecture → Construction)
**Date:** 2026-04-14
**Approver:** Project Owner
**Status:** APPROVED
**Note:** Retroactive — architecture was designed and implemented prior to framework adoption. 4-stage pipeline with scrape → enrich → score → outreach flow. All core modules built and functional.

---
```

- [ ] **Step 3: Create FEATURES.md**

Write to `FEATURES.md`:

```markdown
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
- **Deduplication** — Track processed leads across pipeline runs
- **HTML report generation** — Score distributions, top leads, tech stack breakdown, tool gaps
- **Rate limiting** — Token bucket pattern with configurable per-service limits
- **Retry logic** — Exponential backoff for all HTTP calls
```

- [ ] **Step 4: Create BUGS.md**

Write to `BUGS.md`:

```markdown
# Bug Tracker — biz-prospector

## Format
- **SEV-1:** Critical — blocks pipeline execution
- **SEV-2:** Major — incorrect results or data loss
- **SEV-3:** Minor — cosmetic or edge case
- **SEV-4:** Trivial — no user impact

## Open Bugs

(none)

## Resolved Bugs

(none)
```

- [ ] **Step 5: Create CHANGELOG.md**

Write to `CHANGELOG.md`:

```markdown
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
```

- [ ] **Step 6: Create RELEASE_NOTES.md**

Write to `RELEASE_NOTES.md`:

```markdown
# Release Notes — biz-prospector

No releases yet. Project is in Phase 2 (Construction).
```

- [ ] **Step 7: Create SECURITY.md**

Write to `SECURITY.md`:

```markdown
# Security Policy — biz-prospector

## API Key Handling
- All API keys stored in `config/settings.yaml` (gitignored)
- Never commit API keys to version control
- Example config provided in `config/settings.example.yaml` with placeholder values

## Data Privacy
- Scraped business data (names, addresses, phones, emails) stored locally in `data/` directory
- No data is transmitted except to configured API services
- Contact emails are verified before outreach delivery

## Reporting Vulnerabilities
Report security issues to the project owner directly.

## Security Scanning
- **SAST:** Semgrep (OWASP Top Ten + security-audit rulesets) runs in CI
- **Secret detection:** gitleaks runs in pre-commit hook and CI
- **Dependency audit:** pip-audit runs in CI
- **License compliance:** pip-licenses checks for copyleft licenses in CI
```

- [ ] **Step 8: Commit**

```bash
git add PROJECT_INTAKE.md APPROVAL_LOG.md FEATURES.md BUGS.md CHANGELOG.md RELEASE_NOTES.md SECURITY.md
git commit -m "docs: add solo-orchestrator retroactive artifacts (Phase 0-1 gate)"
```

---

### Task 4: Create documentation directories and symlinks

**Files:**
- Create: `docs/reference/` (directory with symlinks)
- Create: `docs/ADR documentation/` (empty directory)
- Create: `docs/test-results/` (empty directory with .gitkeep)

- [ ] **Step 1: Create directories**

```bash
mkdir -p "docs/reference" "docs/ADR documentation" "docs/test-results"
```

- [ ] **Step 2: Create symlinks to framework docs**

```bash
ln -s ../../.claude/framework/docs/reference/builders-guide.md docs/reference/builders-guide.md
ln -s ../../.claude/framework/docs/reference/user-guide.md docs/reference/user-guide.md
ln -s ../../.claude/framework/docs/reference/security-scan-guide.md docs/reference/security-scan-guide.md
```

- [ ] **Step 3: Add .gitkeep to empty directories**

```bash
touch "docs/ADR documentation/.gitkeep"
touch "docs/test-results/.gitkeep"
```

- [ ] **Step 4: Verify symlinks resolve**

Run: `ls -la docs/reference/`
Expected: Three symlinks pointing to `.claude/framework/docs/reference/` files.

Run: `head -1 docs/reference/builders-guide.md 2>/dev/null && echo "OK" || echo "Symlink broken — submodule may not have this file path. Check .claude/framework/docs/reference/ for actual filenames and fix symlinks."`

- [ ] **Step 5: Commit**

```bash
git add docs/reference docs/ADR\ documentation/.gitkeep docs/test-results/.gitkeep
git commit -m "docs: add reference symlinks and Phase 3 evidence directories"
```

---

### Task 5: Create validation scripts

**Files:**
- Create: `scripts/check-phase-gate.sh`
- Create: `scripts/validate.sh`
- Create: `scripts/check-updates.sh`

- [ ] **Step 1: Create scripts directory**

```bash
mkdir -p scripts
```

- [ ] **Step 2: Create check-phase-gate.sh**

Write to `scripts/check-phase-gate.sh`:

```bash
#!/usr/bin/env bash
# check-phase-gate.sh — Validate current phase requirements are met.
# Called by CI pipeline and can be run locally.
set -euo pipefail

PHASE_STATE=".claude/phase-state.json"

if [ ! -f "$PHASE_STATE" ]; then
  echo "FAIL: $PHASE_STATE not found"
  exit 1
fi

CURRENT_PHASE=$(python3 -c "import json; print(json.load(open('$PHASE_STATE'))['current_phase'])")
echo "Current phase: $CURRENT_PHASE"

ERRORS=0

check() {
  if ! eval "$1" > /dev/null 2>&1; then
    echo "FAIL: $2"
    ERRORS=$((ERRORS + 1))
  else
    echo "PASS: $2"
  fi
}

# Phase 2 requirements (always checked when in Phase 2+)
if [ "$CURRENT_PHASE" -ge 2 ]; then
  check "test -f FEATURES.md" "FEATURES.md exists"
  check "test -f CHANGELOG.md" "CHANGELOG.md exists"
  check "test -f BUGS.md" "BUGS.md exists"
  check "test -f APPROVAL_LOG.md" "APPROVAL_LOG.md exists"
  check "test -f PROJECT_INTAKE.md" "PROJECT_INTAKE.md exists"

  # Check no SEV-1 or SEV-2 open bugs
  if [ -f BUGS.md ]; then
    SEV1_OPEN=$(grep -c "SEV-1.*Open\|SEV-1.*open" BUGS.md 2>/dev/null || echo "0")
    SEV2_OPEN=$(grep -c "SEV-2.*Open\|SEV-2.*open" BUGS.md 2>/dev/null || echo "0")
    if [ "$SEV1_OPEN" -gt 0 ] || [ "$SEV2_OPEN" -gt 0 ]; then
      echo "FAIL: Open SEV-1 ($SEV1_OPEN) or SEV-2 ($SEV2_OPEN) bugs found"
      ERRORS=$((ERRORS + 1))
    else
      echo "PASS: No open SEV-1/SEV-2 bugs"
    fi
  fi
fi

# Phase 3 additional requirements (checked when trying to gate to Phase 4)
if [ "$CURRENT_PHASE" -ge 3 ]; then
  check "test -f SECURITY.md" "SECURITY.md exists"
  # Check test-results directory is non-empty
  if [ -z "$(ls -A docs/test-results/ 2>/dev/null | grep -v .gitkeep)" ]; then
    echo "FAIL: docs/test-results/ is empty (need Phase 3 evidence)"
    ERRORS=$((ERRORS + 1))
  else
    echo "PASS: docs/test-results/ has evidence"
  fi
fi

if [ "$ERRORS" -gt 0 ]; then
  echo ""
  echo "Phase gate check FAILED with $ERRORS error(s)"
  exit 1
fi

echo ""
echo "Phase gate check PASSED"
exit 0
```

- [ ] **Step 3: Create validate.sh**

Write to `scripts/validate.sh`:

```bash
#!/usr/bin/env bash
# validate.sh — General compliance checking for solo-orchestrator framework.
set -euo pipefail

ERRORS=0
WARNINGS=0

check() {
  if ! eval "$1" > /dev/null 2>&1; then
    echo "FAIL: $2"
    ERRORS=$((ERRORS + 1))
  else
    echo "PASS: $2"
  fi
}

warn() {
  if ! eval "$1" > /dev/null 2>&1; then
    echo "WARN: $2"
    WARNINGS=$((WARNINGS + 1))
  else
    echo "PASS: $2"
  fi
}

echo "=== Solo Orchestrator Compliance Check ==="
echo ""

# Required framework files
check "test -f .claude/phase-state.json" "phase-state.json exists"
check "test -f .claude/framework-config.yml" "framework-config.yml exists"
check "test -f .claude/build-progress.json" "build-progress.json exists"
check "test -f .claude/process-state.json" "process-state.json exists"
check "test -f APPROVAL_LOG.md" "APPROVAL_LOG.md exists"
check "test -f PROJECT_INTAKE.md" "PROJECT_INTAKE.md exists"
check "test -f FEATURES.md" "FEATURES.md exists"
check "test -f BUGS.md" "BUGS.md exists"
check "test -f CHANGELOG.md" "CHANGELOG.md exists"

# Validate JSON files
check "python3 -c \"import json; json.load(open('.claude/phase-state.json'))\"" "phase-state.json is valid JSON"
check "python3 -c \"import json; json.load(open('.claude/build-progress.json'))\"" "build-progress.json is valid JSON"
check "python3 -c \"import json; json.load(open('.claude/process-state.json'))\"" "process-state.json is valid JSON"

# Validate phase-state has required fields
check "python3 -c \"
import json
d = json.load(open('.claude/phase-state.json'))
assert 'current_phase' in d
assert 'track' in d
assert 'gates' in d
\"" "phase-state.json has required fields"

# Check APPROVAL_LOG format (must have at least one dated entry)
check "grep -q '## Phase.*→.*Phase' APPROVAL_LOG.md" "APPROVAL_LOG.md has phase gate entries"

# Check for secrets in tracked files (if gitleaks is available)
if command -v gitleaks > /dev/null 2>&1; then
  warn "gitleaks detect --no-git --source . --config .gitleaks.toml 2>/dev/null || gitleaks detect --no-git --source . 2>/dev/null" "No secrets detected in tracked files"
else
  echo "SKIP: gitleaks not installed (install for secret detection)"
fi

echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "Validation FAILED with $ERRORS error(s) and $WARNINGS warning(s)"
  exit 1
fi

echo "Validation PASSED ($WARNINGS warning(s))"
exit 0
```

- [ ] **Step 4: Create check-updates.sh**

Write to `scripts/check-updates.sh`:

```bash
#!/usr/bin/env bash
# check-updates.sh — Check if the solo-orchestrator submodule has upstream updates.
set -euo pipefail

SUBMODULE_PATH=".claude/framework"

if [ ! -d "$SUBMODULE_PATH/.git" ] && [ ! -f "$SUBMODULE_PATH/.git" ]; then
  echo "ERROR: Submodule not found at $SUBMODULE_PATH"
  echo "Run: git submodule update --init --recursive"
  exit 1
fi

LOCAL_SHA=$(cd "$SUBMODULE_PATH" && git rev-parse HEAD)
echo "Local:  $LOCAL_SHA"

# Fetch latest from remote
cd "$SUBMODULE_PATH"
git fetch origin main --quiet 2>/dev/null || git fetch origin --quiet 2>/dev/null
REMOTE_SHA=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/HEAD 2>/dev/null)
cd - > /dev/null

echo "Remote: $REMOTE_SHA"

if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
  echo ""
  echo "Framework is up to date."
else
  BEHIND=$(cd "$SUBMODULE_PATH" && git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
  echo ""
  echo "Framework is $BEHIND commit(s) behind."
  echo ""
  echo "To update:"
  echo "  cd $SUBMODULE_PATH"
  echo "  git pull origin main"
  echo "  cd ../.."
  echo "  git add $SUBMODULE_PATH"
  echo "  git commit -m \"chore: update solo-orchestrator framework\""
fi
```

- [ ] **Step 5: Make scripts executable**

```bash
chmod +x scripts/check-phase-gate.sh scripts/validate.sh scripts/check-updates.sh
```

- [ ] **Step 6: Test the scripts locally**

Run: `bash scripts/check-phase-gate.sh`
Expected: All checks PASS, exit code 0.

Run: `bash scripts/validate.sh`
Expected: All checks PASS (gitleaks may SKIP if not installed), exit code 0.

- [ ] **Step 7: Commit**

```bash
git add scripts/
git commit -m "feat: add solo-orchestrator validation scripts (phase-gate, validate, check-updates)"
```

---

### Task 6: Create pre-commit hook

**Files:**
- Create: `.git/hooks/pre-commit`

- [ ] **Step 1: Write the pre-commit hook**

Write to `.git/hooks/pre-commit`:

```bash
#!/usr/bin/env bash
# pre-commit hook — gitleaks secret detection + TDD ordering warning
# Part of solo-orchestrator framework adoption.

set -euo pipefail

# --- Secret Detection ---
if command -v gitleaks > /dev/null 2>&1; then
  echo "Running gitleaks on staged files..."
  # Get staged files
  STAGED=$(git diff --cached --name-only --diff-filter=ACM)
  if [ -n "$STAGED" ]; then
    if ! gitleaks protect --staged --no-banner 2>/dev/null; then
      echo ""
      echo "BLOCKED: gitleaks found potential secrets in staged files."
      echo "Remove secrets before committing, or use 'git commit --no-verify' to bypass (not recommended)."
      exit 1
    fi
    echo "gitleaks: clean"
  fi
else
  echo "SKIP: gitleaks not installed. Install with: brew install gitleaks"
fi

# --- TDD Ordering Warning ---
# Check if src/ files are staged without corresponding test files
SRC_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '^src/.*\.py$' | grep -v '__init__' || true)
TEST_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '^tests/.*\.py$' || true)

if [ -n "$SRC_FILES" ] && [ -z "$TEST_FILES" ]; then
  echo ""
  echo "WARNING: Source files staged without test files."
  echo "  Staged src files:"
  echo "$SRC_FILES" | sed 's/^/    /'
  echo "  Consider writing tests first (TDD)."
  echo ""
  # Warning only — does not block commit
fi

exit 0
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x .git/hooks/pre-commit
```

- [ ] **Step 3: Test the hook**

Run: `echo "test" > /tmp/test-hook.txt && git add /tmp/test-hook.txt 2>/dev/null; .git/hooks/pre-commit; echo "Exit code: $?"`
Expected: Hook runs without error, exit code 0. gitleaks may show SKIP if not installed.

Note: The pre-commit hook lives in `.git/hooks/` which is not tracked by git. It must be installed manually or via a setup script. It is NOT committed — document this in CLAUDE.md.

---

### Task 7: Create GitHub Actions CI pipeline

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create the workflows directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create ci.yml**

Write to `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          submodules: recursive
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install ruff pytest pytest-cov pip-audit pip-licenses

      - name: Lint
        run: ruff check .

      - name: Test
        run: pytest --cov=src --cov-branch --cov-fail-under=95

      - name: SAST - Semgrep
        uses: semgrep/semgrep-action@713efdd80949ae7906dd2b0df5a0daa78ab367c7 # v1
        with:
          config: >-
            p/owasp-top-ten
            p/security-audit

      - name: Secret Detection - gitleaks
        uses: gitleaks/gitleaks-action@44c470ffc35caa8b1eb3e8012ca53c2f0a413e84 # v2.3.7
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Dependency Audit
        run: pip-audit

      - name: License Check
        run: |
          pip-licenses --format=csv --with-license-file --no-license-path > /dev/null
          pip-licenses --fail-on="GNU General Public License v2 (GPLv2);GNU General Public License v3 (GPLv3);GNU Affero General Public License v3 (AGPLv3);GNU Lesser General Public License v2 (LGPLv2);GNU Lesser General Public License v2.1 (LGPLv2.1);GNU Lesser General Public License v3 (LGPLv3)"

      - name: Phase Gate Check
        run: bash scripts/check-phase-gate.sh

      - name: Approval Log Integrity
        if: github.event_name == 'pull_request'
        run: |
          # Check APPROVAL_LOG.md is append-only (no deleted lines)
          DELETED=$(git diff origin/main...HEAD -- APPROVAL_LOG.md | grep '^-[^-]' | wc -l || echo "0")
          if [ "$DELETED" -gt 0 ]; then
            echo "FAIL: APPROVAL_LOG.md has $DELETED deleted line(s). This file is append-only."
            exit 1
          fi
          echo "PASS: APPROVAL_LOG.md is append-only"
```

- [ ] **Step 3: Create release.yml**

Write to `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - "v*"

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          submodules: recursive

      - name: Setup Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.11"

      - name: Install build tools
        run: pip install build

      - name: Build package
        run: python -m build

      - name: Upload artifacts
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: dist
          path: dist/
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml
git commit -m "ci: add GitHub Actions CI pipeline and release workflow"
```

---

### Task 8: Create evaluation prompts

**Files:**
- Create: `evaluation-prompts/Projects/security-reviewer.md`
- Create: `evaluation-prompts/Projects/architecture-reviewer.md`
- Create: `evaluation-prompts/Projects/ux-operations-reviewer.md`
- Create: `evaluation-prompts/Projects/data-quality-reviewer.md`
- Create: `evaluation-prompts/Projects/compliance-reviewer.md`
- Create: `evaluation-prompts/Projects/performance-reviewer.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p evaluation-prompts/Projects
```

- [ ] **Step 2: Create security-reviewer.md**

Write to `evaluation-prompts/Projects/security-reviewer.md`:

```markdown
# Security Reviewer — biz-prospector

You are a security reviewer examining biz-prospector, a CLI pipeline that scrapes business data, enriches it via multiple APIs, and sends cold outreach emails.

## Review Focus Areas

### API Key Management
- Are API keys stored securely (config file, not in code)?
- Is `config/settings.yaml` gitignored?
- Could API keys leak through error messages, logs, or debug output?
- Are keys passed to functions or stored in objects that could be serialized?

### Data Privacy & PII
- The pipeline scrapes business names, addresses, phone numbers, email addresses, and review content. How is this PII handled?
- Is scraped data stored securely? Could it be accidentally committed?
- Is the `data/` directory gitignored?
- Are there data retention or cleanup mechanisms?

### Secret Detection
- Review the pre-commit hook and CI pipeline for gitleaks coverage
- Are there any hardcoded values that look like test keys but could be real?
- Check `config/settings.example.yaml` for placeholder values that could be mistaken for real keys

### Network Security
- Are all API calls made over HTTPS?
- Is SSL verification enabled for all HTTP clients?
- Are there any URLs constructed from user input that could be manipulated?

### Dependency Security
- Review `requirements.txt` for known vulnerable packages
- Are dependencies pinned to specific versions?
- Check for any packages with known supply chain concerns

Provide specific file paths and line numbers for any findings. Rate each finding as Critical, High, Medium, or Low.
```

- [ ] **Step 3: Create architecture-reviewer.md**

Write to `evaluation-prompts/Projects/architecture-reviewer.md`:

```markdown
# Architecture Reviewer — biz-prospector

You are an architecture reviewer examining biz-prospector, a 4-stage CLI pipeline (scrape → enrich → score → outreach) that processes business leads.

## Review Focus Areas

### Pipeline Stage Coupling
- How tightly coupled are the pipeline stages?
- Can each stage run independently with just a JSON input file?
- What happens if one stage fails mid-batch? Is there recovery?
- Is there any shared mutable state between stages?

### Data Model
- The `Lead` Pydantic model accumulates fields across stages. Is this sustainable?
- Are there fields that should be separated into stage-specific models?
- How does the model handle missing/partial data from earlier stages?

### JSON File Scalability
- All data flows through JSON files in `data/`. What happens at 10K leads? 100K?
- Are files read fully into memory? Could this be a problem for large datasets?
- Is there any indexing or random access needed that JSON can't support?

### Error Recovery
- If enrichment fails for one lead, does it block others?
- Are partial results saved? Can the pipeline resume from where it stopped?
- How are API rate limits and transient failures handled?

### Async Patterns
- Review the async enrichment processor for correctness
- Is the semaphore-based concurrency appropriate?
- Are there potential deadlocks or resource leaks?

### Configuration
- How are vertical configs loaded and merged with defaults?
- Is the config schema validated? What happens with malformed YAML?
- Could config changes break existing scored data?

Provide specific file paths and line numbers for any findings. Rate each as Critical, High, Medium, or Low.
```

- [ ] **Step 4: Create ux-operations-reviewer.md**

Write to `evaluation-prompts/Projects/ux-operations-reviewer.md`:

```markdown
# UX/Operations Reviewer — biz-prospector

You are a UX/operations reviewer examining biz-prospector, a CLI tool for solo consultants to find and reach out to businesses.

## Review Focus Areas

### CLI Usability
- Are command names and flags intuitive?
- Is help text clear and complete for all commands?
- Are error messages actionable (do they tell the user what to do next)?
- Is the output readable (colors, tables, progress indicators)?

### Rate Limit Feedback
- When the tool hits API rate limits, does the user know what's happening?
- Is there a progress indicator during long enrichment runs?
- Can the user estimate how long a pipeline run will take?

### Error Experience
- What does the user see when an API key is missing?
- What happens when the network is down?
- Are partial failures communicated clearly?
- Can the user recover from a failed run without re-processing everything?

### Configuration Experience
- Is it clear how to set up `config/settings.yaml`?
- What happens if the user forgets a required field?
- Are default values sensible for a first run?

### Output Quality
- Are HTML reports useful and readable?
- Is the score distribution meaningful to someone choosing who to contact?
- Does the outreach email quality justify the pipeline complexity?

Provide specific examples and suggestions. Rate each as Critical, High, Medium, or Low.
```

- [ ] **Step 5: Create data-quality-reviewer.md**

Write to `evaluation-prompts/Projects/data-quality-reviewer.md`:

```markdown
# Data Quality Reviewer — biz-prospector

You are a data quality reviewer examining biz-prospector, a tool that scrapes, enriches, and scores business leads.

## Review Focus Areas

### Scraping Accuracy
- How are duplicate businesses detected and handled?
- Could the same business appear with slightly different names/addresses?
- Are Google Maps results representative of actual businesses in the area?
- How fresh is the scraped data?

### Deduplication Reliability
- Review the dedup logic — what's the matching key?
- Could legitimate different businesses be falsely deduped?
- Could the same business slip through dedup with minor variations?

### Scoring Calibration
- Are the default weights meaningful? Would a high-scoring lead actually be a good prospect?
- Do per-vertical weight overrides make sense for each industry?
- Is the 0-100 scale well-distributed or do most leads cluster in a narrow range?
- Are keyword lists for manual process detection and complaint detection comprehensive?

### Enrichment Data Quality
- How reliable is HTML-based tech stack detection?
- When BuiltWith and HTML detection disagree, which wins?
- Are review complaint keywords specific enough to avoid false positives?
- Could job posting keywords match irrelevant postings?

### Contact Data Quality
- How accurate is the Apollo/Hunter enrichment?
- Is email verification reliable enough to prevent bounces?
- Could the title-priority ranking miss the actual decision maker?

Provide specific examples and data quality metrics where possible. Rate each as Critical, High, Medium, or Low.
```

- [ ] **Step 6: Create compliance-reviewer.md**

Write to `evaluation-prompts/Projects/compliance-reviewer.md`:

```markdown
# Compliance Reviewer — biz-prospector

You are a compliance reviewer examining biz-prospector, a tool that scrapes business data and sends cold outreach emails.

## Review Focus Areas

### Email Outreach Legality
- Does the outreach comply with CAN-SPAM Act requirements?
  - Physical postal address included?
  - Unsubscribe mechanism?
  - Accurate subject lines?
  - Identified as advertisement?
- Does the outreach comply with GDPR (if targeting EU businesses)?
  - Lawful basis for processing?
  - Right to erasure capability?
  - Data subject access requests?

### Scraping Terms of Service
- Does Google Maps scraping comply with Google's Terms of Service?
- What are the ToS implications of using SerpAPI vs Apify as intermediaries?
- Does Outscraper review scraping comply with Google's review policies?
- Are there rate limits or usage quotas that could be exceeded?

### Data Retention
- How long is scraped data retained?
- Is there a mechanism to delete individual leads on request?
- Are there data minimization practices (only scraping what's needed)?
- Is contact information stored longer than necessary?

### Third-Party API Compliance
- Are all API usages within their respective terms of service?
- Are API rate limits respected and enforced?
- Is data from one API being shared with or fed into another in ways that violate ToS?

### Liability
- Could the tool be used for spam or harassment?
- Are there safeguards against mass-sending to inappropriate recipients?
- Is there audit trail for what was sent and to whom?

Provide specific regulatory references where applicable. Rate each as Critical, High, Medium, or Low.
```

- [ ] **Step 7: Create performance-reviewer.md**

Write to `evaluation-prompts/Projects/performance-reviewer.md`:

```markdown
# Performance Reviewer — biz-prospector

You are a performance reviewer examining biz-prospector, a CLI pipeline processing business leads through scraping, enrichment, scoring, and outreach.

## Review Focus Areas

### Async Enrichment Throughput
- What is the effective throughput of the async enrichment processor?
- Are the concurrency limits (semaphore size) well-tuned?
- Could the rate limiters be bottlenecking overall throughput?
- Is the token bucket pattern the right choice for rate limiting?

### Rate Limit Efficiency
- Are per-service rate limits configured appropriately?
- Is there unnecessary waiting when limits aren't being hit?
- Could rate limit sleep times be more precise?
- Are rate limiters shared across concurrent tasks correctly?

### Large Batch Handling
- How does the pipeline perform with 500+ leads?
- Is memory usage proportional to batch size?
- Are JSON files loaded fully into memory?
- Could streaming or chunked processing improve large batches?

### Network Efficiency
- Are HTTP connections reused (connection pooling)?
- Are timeouts configured appropriately for each API?
- Is retry logic efficient (exponential backoff without excessive delay)?
- Could any API calls be parallelized that currently aren't?

### Scoring Performance
- Is the scoring engine efficient for large lead sets?
- Could scoring be vectorized or batched?
- Is the sorting step a bottleneck?

### Report Generation
- How fast is HTML report generation for 500+ leads?
- Is the report size reasonable? Could it be slow to open in a browser?

Provide specific measurements or estimates where possible. Rate each as Critical, High, Medium, or Low.
```

- [ ] **Step 8: Commit**

```bash
git add evaluation-prompts/
git commit -m "docs: add 6 adversarial evaluation prompts for Phase 3 review"
```

---

### Task 9: Update CLAUDE.md with framework methodology

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read current CLAUDE.md**

Read the file to understand current content before modifying.

- [ ] **Step 2: Add framework section to CLAUDE.md**

Append the following after the existing `## Constraints` section at the end of `CLAUDE.md`:

```markdown

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
```

- [ ] **Step 3: Update the APIs section to reflect current state**

In CLAUDE.md, replace:
```markdown
- BuiltWith: Tech stack lookups (not yet wired in, currently using HTML detection)
- Apollo/Hunter: Contact enrichment (not yet implemented)
```

With:
```markdown
- BuiltWith: Tech stack lookups (integrated via BuiltWith Domain API v22)
- Apollo/Hunter: Contact enrichment (Apollo primary, Hunter fallback, email verification)
```

And replace:
```markdown
- Instantly.ai: Email delivery (not yet implemented)
```

With:
```markdown
- Instantly.ai: Email delivery (campaign creation, lead push, sequence setup)
```

- [ ] **Step 4: Update the TODO section**

In CLAUDE.md, replace the TODO section with:
```markdown
### TODO — priority order:
1. ~~BuiltWith API integration~~ ✓
2. ~~Tests~~ ✓ (375 tests, 99% coverage)
3. ~~HTML report generator~~ ✓
4. ~~More verticals~~ ✓ (construction, insurance, accounting, auto repair)
5. LinkedIn enrichment for employee title analysis
6. Scheduled/cron pipeline runs
7. SQLite or Postgres backend instead of JSON files (for larger scale)
8. Web dashboard (optional — Flask/FastAPI for non-CLI users)
```

- [ ] **Step 5: Update the vertical configs line**

In CLAUDE.md, replace:
```markdown
- Vertical configs: HVAC, dental, legal, property management
```

With:
```markdown
- Vertical configs: HVAC, dental, legal, property management, construction, insurance, accounting, auto repair
```

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with solo-orchestrator framework methodology"
```

---

### Task 10: Create pre-commit hook reference copy and update .gitignore

**Files:**
- Create: `docs/reference/pre-commit-hook.sh` (tracked copy of the hook for easy install)
- Modify: `.gitignore` (if it exists) or create it

- [ ] **Step 1: Copy hook to docs for tracking**

The `.git/hooks/pre-commit` file is not tracked by git. Create a reference copy:

```bash
cp .git/hooks/pre-commit docs/reference/pre-commit-hook.sh
```

- [ ] **Step 2: Ensure .gitignore covers framework needs**

Read the current `.gitignore` if it exists. Then ensure these entries are present (add them if missing):

```
# API keys and local config
config/settings.yaml

# Data directory (scraped/enriched data)
data/

# Python
__pycache__/
*.pyc
*.egg-info/
dist/
build/
*.egg

# Virtual environment
venv/
.venv/

# Coverage
.coverage
htmlcov/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
```

- [ ] **Step 3: Commit**

```bash
git add docs/reference/pre-commit-hook.sh .gitignore
git commit -m "chore: add tracked pre-commit hook copy and update .gitignore"
```

---

### Task 11: Final validation

- [ ] **Step 1: Run the validation script**

Run: `bash scripts/validate.sh`
Expected: All checks PASS, exit code 0.

- [ ] **Step 2: Run the phase gate check**

Run: `bash scripts/check-phase-gate.sh`
Expected: All checks PASS for Phase 2, exit code 0.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest --cov=src --cov-branch -q`
Expected: 375 passed, 99% coverage (unchanged from before framework adoption).

- [ ] **Step 4: Verify the directory structure**

Run: `find . -name "*.md" -path "./docs/*" -o -name "*.md" -maxdepth 1 -o -name "*.sh" -path "./scripts/*" -o -name "*.yml" -path "./.github/*" -o -name "*.json" -path "./.claude/*" -o -name "*.yml" -path "./.claude/*" | sort`
Expected: All files from the spec's repository structure are present.

- [ ] **Step 5: Verify submodule**

Run: `git submodule status`
Expected: Shows `.claude/framework` with a commit SHA (no `-` prefix indicating uninitialized).

- [ ] **Step 6: Final commit (if any unstaged changes)**

```bash
git status
# If clean, no commit needed. If changes found, stage and commit with appropriate message.
```
