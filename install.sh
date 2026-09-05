#!/usr/bin/env bash
# One-shot setup for AutoForge on Linux/macOS: installs `uv` (a fast Python
# package manager) if it's missing, installs all Python dependencies, and
# builds the web UI frontend. After this finishes, run ./run_webui.sh to
# start AutoForge.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== AutoForge installer ==="

if ! command -v uv &>/dev/null; then
    echo "[install] 'uv' not found - installing it now..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v uv &>/dev/null; then
    echo "[install] ERROR: uv installed but isn't on PATH yet."
    echo "  Close and reopen your terminal and re-run ./install.sh, or see https://docs.astral.sh/uv/ for manual install steps."
    exit 1
fi

echo "[install] Installing Python dependencies with uv..."
uv sync

if command -v npm &>/dev/null; then
    echo "[install] Building the web UI frontend (this can take a minute)..."
    (cd webui/frontend && npm install && npm run build)
else
    echo "[install] WARNING: npm not found - skipping the web UI frontend build."
    echo "  Install Node.js (https://nodejs.org/) if you want to use the web UI, then re-run ./install.sh."
fi

echo
echo "=== Install complete ==="
echo "Start AutoForge with:   ./run_webui.sh"
echo "Check for updates with: ./update.sh"
