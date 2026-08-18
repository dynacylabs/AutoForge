#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${WEBUI_HOST:-0.0.0.0}"
PORT="${WEBUI_PORT:-8000}"
BUILD_FRONTEND="${BUILD_FRONTEND:-true}"

# ---------------------------------------------------------------------------
# Build the frontend if the dist folder is missing (or forced)
# ---------------------------------------------------------------------------
FRONTEND_DIST="$SCRIPT_DIR/webui/frontend/dist"

should_build=false
if [ "$BUILD_FRONTEND" = "true" ]; then
    should_build=true
elif [ "$BUILD_FRONTEND" = "auto" ] && [ ! -d "$FRONTEND_DIST" ]; then
    should_build=true
fi

if [ "$should_build" = true ]; then
    echo "[webui] Building frontend..."
    if ! command -v npm &>/dev/null; then
        echo "[webui] ERROR: npm not found. Install Node.js or set BUILD_FRONTEND=false."
        exit 1
    fi
    cd "$SCRIPT_DIR/webui/frontend"
    npm install
    npm run build
    cd "$SCRIPT_DIR"
    echo "[webui] Frontend built."
fi

# ---------------------------------------------------------------------------
# Start the FastAPI server
# ---------------------------------------------------------------------------
echo "[webui] Starting server on http://${HOST}:${PORT}"
exec uv run uvicorn autoforge.webui.server:app \
    --host "$HOST" \
    --port "$PORT" \
    "${EXTRA_UVICORN_ARGS[@]}"
