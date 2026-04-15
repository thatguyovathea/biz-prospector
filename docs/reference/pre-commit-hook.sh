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
