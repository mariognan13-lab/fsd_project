#!/bin/bash
# ==============================================================================
# Traffic IQ - Local Development Runner
# ==============================================================================
# Runs the FastAPI backend (http://localhost:5050) and the Next.js frontend
# (http://localhost:3000) locally with automatic setup and dependency management.
#
# Usage:
#   ./run-local.sh              # Run both backend and frontend (default)
#   ./run-local.sh --backend    # Run only backend
#   ./run-local.sh --frontend   # Run only frontend
#   ./run-local.sh --help       # Show this help message
# ==============================================================================

set -e

# Terminal colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""

# Help documentation
show_help() {
    echo -e "${CYAN}Traffic IQ - Local Development Runner${NC}"
    echo ""
    echo "Usage: ./run-local.sh [options]"
    echo ""
    echo "Options:"
    echo "  --all, -a       Start both FastAPI backend and Next.js frontend (default)"
    echo "  --backend, -b   Start only the FastAPI backend (port 5050)"
    echo "  --frontend, -f  Start only the Next.js frontend (port 3000)"
    echo "  --help, -h      Display this help dialog"
    echo ""
}

# Trap cleanup to stop background processes on exit
cleanup() {
    if [ -n "$BACKEND_PID" ]; then
        echo ""
        echo -e "${YELLOW}Shutting down background backend process (PID $BACKEND_PID)...${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# Ensure .env file exists
check_env() {
    if [ ! -f "$ROOT_DIR/.env" ]; then
        if [ -f "$ROOT_DIR/.env.example" ]; then
            echo -e "${YELLOW}[Notice] .env not found. Creating from .env.example ...${NC}"
            cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
            echo -e "${GREEN}[OK] Created .env successfully.${NC}"
        else
            echo -e "${RED}[Warning] Neither .env nor .env.example found in root.${NC}"
        fi
    fi
}

# Check Python environment
find_python() {
    # Prefer Python 3.11 or 3.12 (has binary wheels for all dependencies on Windows)
    if [ -f "/c/Users/mario/AppData/Local/Programs/Python/Python311/python.exe" ]; then
        echo "/c/Users/mario/AppData/Local/Programs/Python/Python311/python.exe"
    elif command -v python3.11 &> /dev/null; then
        echo "python3.11"
    elif command -v python3.12 &> /dev/null; then
        echo "python3.12"
    elif command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        echo ""
    fi
}

# Setup and activate backend virtualenv
setup_backend() {
    echo -e "${BLUE}==> Setting up FastAPI Backend...${NC}"

    cd "$ROOT_DIR/api"

    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        local pycmd
        pycmd="$(find_python)"
        if [ -z "$pycmd" ]; then
            echo -e "${RED}[ERROR] Python is not installed or not in PATH. Please install Python 3.10-3.12.${NC}"
            exit 1
        fi
        echo -e "${YELLOW}Creating virtual environment in api/.venv using $pycmd ...${NC}"
        $pycmd -m venv .venv
    fi

    # Activate virtual environment (Linux/macOS vs Windows Git Bash)
    if [ -f ".venv/Scripts/activate" ]; then
        # Strip Windows CRLF if present
        sed -i 's/\r$//' .venv/Scripts/activate 2>/dev/null || true
        source .venv/Scripts/activate
    elif [ -f ".venv/bin/activate" ]; then
        sed -i 's/\r$//' .venv/bin/activate 2>/dev/null || true
        source .venv/bin/activate
    else
        echo -e "${RED}[ERROR] Virtual environment activation script not found in api/.venv.${NC}"
        exit 1
    fi

    # Determine exact Python executable inside .venv
    if [ -f ".venv/Scripts/python.exe" ]; then
        VENV_PY="$ROOT_DIR/api/.venv/Scripts/python.exe"
    elif [ -f ".venv/Scripts/python" ]; then
        VENV_PY="$ROOT_DIR/api/.venv/Scripts/python"
    elif [ -f ".venv/bin/python3" ]; then
        VENV_PY="$ROOT_DIR/api/.venv/bin/python3"
    elif [ -f ".venv/bin/python" ]; then
        VENV_PY="$ROOT_DIR/api/.venv/bin/python"
    else
        VENV_PY="python"
    fi

    # Ensure both Scripts and bin are in PATH to prevent pip location warnings
    [ -d "$PWD/.venv/Scripts" ] && export PATH="$PWD/.venv/Scripts:$PATH"
    [ -d "$PWD/.venv/bin" ] && export PATH="$PWD/.venv/bin:$PATH"

    # Fast check: only install if fastapi/uvicorn are not already present
    if "$VENV_PY" -c "import fastapi, uvicorn" 2>/dev/null; then
        echo -e "${GREEN}[OK] Backend dependencies are ready.${NC}"
    else
        echo -e "${CYAN}Installing backend dependencies (this may take a minute on first setup)...${NC}"
        "$VENV_PY" -m pip install -r requirements.txt --no-warn-script-location
        echo -e "${GREEN}[OK] Backend dependencies installed.${NC}"
    fi
}

# Setup frontend dependencies
setup_frontend() {
    echo -e "${BLUE}==> Setting up Next.js Frontend...${NC}"
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}[ERROR] npm is not installed or not in PATH. Please install Node.js 18+.${NC}"
        exit 1
    fi

    cd "$ROOT_DIR/frontend"
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies (npm install)...${NC}"
        npm install
    fi
    echo -e "${GREEN}[OK] Frontend dependencies ready.${NC}"
}

# Run only backend
start_backend_foreground() {
    setup_backend
    cd "$ROOT_DIR/api"
    echo ""
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN} Starting FastAPI backend on http://localhost:5050 ${NC}"
    echo -e "${GREEN} API documentation: http://localhost:5050/docs      ${NC}"
    echo -e "${GREEN} Press Ctrl+C to stop                               ${NC}"
    echo -e "${GREEN}====================================================${NC}"
    echo ""
    "$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 5050 --reload
}

# Run only frontend
start_frontend_foreground() {
    setup_frontend
    cd "$ROOT_DIR/frontend"
    echo ""
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN} Starting Next.js frontend on http://localhost:3000 ${NC}"
    echo -e "${GREEN} Press Ctrl+C to stop                               ${NC}"
    echo -e "${GREEN}====================================================${NC}"
    echo ""
    npm run dev
}

# Run both services concurrently
start_all() {
    setup_backend
    setup_frontend

    echo ""
    echo -e "${CYAN}Starting FastAPI backend in background...${NC}"
    cd "$ROOT_DIR/api"
    "$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 5050 --reload &
    BACKEND_PID=$!

    # Wait for backend health check
    echo -e "${CYAN}Waiting for backend to become ready...${NC}"
    local count=0
    local max_wait=30
    local backend_ready=0

    while [ $count -lt $max_wait ]; do
        if command -v curl &> /dev/null; then
            if curl -s http://127.0.0.1:5050/api/health >/dev/null 2>&1; then
                backend_ready=1
                break
            fi
        else
            # Fallback using python if curl is not available
            if "$VENV_PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5050/api/health')" >/dev/null 2>&1; then
                backend_ready=1
                break
            fi
        fi
        sleep 1
        count=$((count + 1))
    done

    if [ $backend_ready -eq 1 ]; then
        echo -e "${GREEN}[OK] Backend is healthy at http://localhost:5050${NC}"
    else
        echo -e "${YELLOW}[Notice] Backend starting; proceeding with frontend...${NC}"
    fi

    echo ""
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN}  Traffic IQ is running locally!                    ${NC}"
    echo -e "${GREEN}  Frontend UI:  http://localhost:3000               ${NC}"
    echo -e "${GREEN}  Backend API:  http://localhost:5050               ${NC}"
    echo -e "${GREEN}  API Docs:     http://localhost:5050/docs          ${NC}"
    echo -e "${GREEN}  Press Ctrl+C to stop all services                 ${NC}"
    echo -e "${GREEN}====================================================${NC}"
    echo ""

    cd "$ROOT_DIR/frontend"
    npm run dev
}

# Main routing based on CLI arguments
check_env

MODE="all"
while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h)
            show_help
            exit 0
            ;;
        --backend|-b)
            MODE="backend"
            shift
            ;;
        --frontend|-f)
            MODE="frontend"
            shift
            ;;
        --all|-a)
            MODE="all"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

case "$MODE" in
    backend)
        start_backend_foreground
        ;;
    frontend)
        start_frontend_foreground
        ;;
    all)
        start_all
        ;;
esac
