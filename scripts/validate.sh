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
