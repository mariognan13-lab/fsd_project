#!/bin/bash
# ------------------------------------------------------------------
# Traffic IQ - Run the Next.js frontend in dev mode
# Installs dependencies on first run, then serves the UI.
# The frontend proxies to the backend at http://localhost:5050 by
# default, so start run-backend.sh first (or use ./run-local.sh).
# Usage: ./scripts/run-frontend.sh
# ------------------------------------------------------------------

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Ensure .env exists in project root
if [ ! -f "$PROJECT_ROOT/.env" ] && [ -f "$PROJECT_ROOT/.env.example" ]; then
    echo "Creating .env from .env.example ..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

cd "$PROJECT_ROOT/frontend"

# Check for npm
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Install Node.js from https://nodejs.org and try again."
    exit 1
fi

echo "Using Node: $(node --version 2>/dev/null || echo 'available') (npm $(npm --version))"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies ..."
    npm install
fi

echo ""
echo "Starting frontend at http://localhost:3000 (Ctrl+C to stop)"
npm run dev