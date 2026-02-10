#!/bin/bash

# Copilot Ralph Mode (Wrapper)
# Delegates to cross-platform Python implementation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_DIR/ralph_mode.py" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$SCRIPT_DIR/ralph_mode.py" "$@"
else
  echo "❌ Python is required. Please install Python 3.9+." >&2
  exit 1
fi
