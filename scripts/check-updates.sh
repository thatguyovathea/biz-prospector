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
