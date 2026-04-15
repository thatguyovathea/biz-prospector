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
    SEV1_OPEN=$(grep -ci "SEV-1.*open" BUGS.md 2>/dev/null || true)
    SEV1_OPEN=${SEV1_OPEN:-0}
    SEV2_OPEN=$(grep -ci "SEV-2.*open" BUGS.md 2>/dev/null || true)
    SEV2_OPEN=${SEV2_OPEN:-0}
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
