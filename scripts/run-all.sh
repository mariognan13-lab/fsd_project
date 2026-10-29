#!/bin/bash
# ------------------------------------------------------------------
# Traffic IQ - Run both backend and frontend together
# Usage: ./scripts/run-all.sh
# ------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

exec "$PROJECT_ROOT/run-local.sh" "$@"
