#!/bin/bash
# ------------------------------------------------------------------
# Traffic IQ - Run the FastAPI backend
# Creates a virtual environment on first run, installs dependencies,
# then serves the API at http://localhost:5050
# Usage: ./scripts/run-backend.sh
# ------------------------------------------------------------------

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Ensure .env exists in project root
if [ ! -f "$PROJECT_ROOT/.env" ] && [ -f "$PROJECT_ROOT/.env.example" ]; then
    echo "Creating .env from .env.example ..."
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

cd "$PROJECT_ROOT/api"

# Prefer python3, fall back to python
if command -v python3 &> /dev/null; then
    PYCMD="python3"
elif command -v python &> /dev/null; then
    PYCMD="python"
else
    echo "ERROR: Python not found. Install Python 3 and try again."
    exit 1
fi

echo "Using Python: $($PYCMD --version)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in api/.venv ..."
    $PYCMD -m venv .venv
fi

# Activate virtual environment (Linux/macOS vs Windows Git Bash)
if [ -f ".venv/Scripts/activate" ]; then
    sed -i 's/\r$//' .venv/Scripts/activate 2>/dev/null || true
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    sed -i 's/\r$//' .venv/bin/activate 2>/dev/null || true
    source .venv/bin/activate
else
    echo "ERROR: Virtual environment activation script not found in .venv"
    exit 1
fi

# Determine exact Python executable inside .venv
if [ -f ".venv/Scripts/python.exe" ]; then
    VENV_PY="$PROJECT_ROOT/api/.venv/Scripts/python.exe"
elif [ -f ".venv/Scripts/python" ]; then
    VENV_PY="$PROJECT_ROOT/api/.venv/Scripts/python"
elif [ -f ".venv/bin/python3" ]; then
    VENV_PY="$PROJECT_ROOT/api/.venv/bin/python3"
elif [ -f ".venv/bin/python" ]; then
    VENV_PY="$PROJECT_ROOT/api/.venv/bin/python"
else
    VENV_PY="python"
fi

# Ensure both Scripts and bin are in PATH
[ -d "$PWD/.venv/Scripts" ] && export PATH="$PWD/.venv/Scripts:$PATH"
[ -d "$PWD/.venv/bin" ] && export PATH="$PWD/.venv/bin:$PATH"

# Install dependencies if not already present
if "$VENV_PY" -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "Backend dependencies are ready."
else
    echo "Installing backend dependencies..."
    "$VENV_PY" -m pip install -r requirements.txt --no-warn-script-location
    echo "Backend dependencies installed."
fi

echo ""
echo "Starting backend at http://localhost:5050 (Ctrl+C to stop)"
echo "API docs available at: http://localhost:5050/docs"
"$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 5050 --reload