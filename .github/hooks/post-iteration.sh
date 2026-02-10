#!/usr/bin/env bash
# Post-iteration hook for Ralph Mode
# This hook runs AFTER each Copilot CLI iteration completes
#
# Environment variables available:
#   RALPH_ITERATION - Current iteration number
#   RALPH_MAX_ITERATIONS - Maximum iterations allowed
#   RALPH_TASK_ID - Current task ID (in batch mode)
#   RALPH_MODE - "single" or "batch"
#   RALPH_EXIT_CODE - Exit code from Copilot CLI

# Example: Log iteration completion
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Completed iteration $RALPH_ITERATION (exit: $RALPH_EXIT_CODE)" >> .ralph-mode/hooks.log

# Example: Run tests after changes
# npm test --silent 2>/dev/null || echo "Tests failed"

# Example: Security scan (npm)
# npm audit --audit-level=high 2>/dev/null || true

# Example: CodeQL security scan (opt-in, non-blocking)
# Uncomment the block below to enable CodeQL scanning after each iteration.
# Requires: CodeQL CLI installed (`codeql` on PATH)
# Set RALPH_CODEQL_SCAN=1 to enable, or uncomment the lines below.
#
# if [[ "${RALPH_CODEQL_SCAN:-0}" == "1" ]] && command -v codeql >/dev/null 2>&1; then
#     CHANGED_FILES=$(git diff --name-only HEAD~1 2>/dev/null | grep -v '.ralph-mode/' || true)
#     if [[ -n "$CHANGED_FILES" ]]; then
#         echo "[CodeQL] Scanning changed files..."
#         python3 ralph_mode.py scan --changed-only --quiet 2>/dev/null || true
#     fi
# fi

# Example: Auto-commit progress
# git add -A && git commit -m "Ralph iteration $RALPH_ITERATION" --no-verify 2>/dev/null || true

exit 0
