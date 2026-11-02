#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# All webui data (checkpoints, uploads, filament library) is isolated to a
# throwaway temp directory so test runs never touch your real dev data at
# checkpoints/, uploads/, filament_library/ — those accumulate real project
# history and must not be mutated or deleted by an automated test run.
TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/autoforge_e2e_XXXXXX")"
mkdir -p "$TEST_DIR"/{checkpoints,uploads,library}

cleanup() {
    echo ""
    echo "Shutting down backend..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    rm -rf "$TEST_DIR"
    echo "Done."
}
trap cleanup EXIT

echo "=== AutoForge WebUI E2E Test Suite ==="
echo "(isolated test data dir: $TEST_DIR)"
echo ""

# ------------------------------------------------------------------
# 1. Build the frontend
# ------------------------------------------------------------------
echo "[1/6] Building frontend..."
cd "$PROJECT_ROOT/webui/frontend"
if [ ! -d node_modules ]; then
    npm install
fi
npm run build
cd "$PROJECT_ROOT"
echo "  [OK]"

# ------------------------------------------------------------------
# 2. Start the backend against isolated data
# ------------------------------------------------------------------
echo ""
echo "[2/6] Starting backend..."

# Seed the isolated library from the real one (if present) so filament type
# tabs (PLA/PETG/...) exist — a bare fresh library only has 3 untyped
# "Generic" defaults, which several UI tests don't expect.
if [ -f "$PROJECT_ROOT/filament_library/library.json" ]; then
    cp "$PROJECT_ROOT/filament_library/library.json" "$TEST_DIR/library/library.json"
fi
if [ -f "$PROJECT_ROOT/filament_library/active.json" ]; then
    cp "$PROJECT_ROOT/filament_library/active.json" "$TEST_DIR/library/active.json"
fi
if [ -f "$PROJECT_ROOT/filament_library/user_imported.marker" ]; then
    cp "$PROJECT_ROOT/filament_library/user_imported.marker" "$TEST_DIR/library/user_imported.marker"
fi

export AUTOFORGE_WEBUI_CHECKPOINTS_DIR="$TEST_DIR/checkpoints"
export AUTOFORGE_WEBUI_UPLOADS_DIR="$TEST_DIR/uploads"
export AUTOFORGE_WEBUI_LIBRARY_DIR="$TEST_DIR/library"

uv run uvicorn autoforge.webui.server:app \
    --host 127.0.0.1 --port 8000 --log-level warning &
BACKEND_PID=$!

for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/api/system/health >/dev/null 2>&1; then
        echo "  [OK] Backend ready"; break
    fi
    if [ "$i" -eq 30 ]; then echo "  [FAIL] Backend not ready"; exit 1; fi
    sleep 1
done

# ------------------------------------------------------------------
# 3. Pipeline smoke test (Python via requests)
# ------------------------------------------------------------------
echo ""
echo "[3/6] Pipeline smoke test..."
PYTHONPATH="$PROJECT_ROOT/src" python3 "$PROJECT_ROOT/tests/test_pipeline_smoke.py"
echo "  [OK]"

# ------------------------------------------------------------------
# 4. TypeScript compilation
# ------------------------------------------------------------------
echo ""
echo "[4/6] TypeScript check..."
cd "$PROJECT_ROOT/webui/frontend"
npx tsc --noEmit && echo "  [OK]"

# ------------------------------------------------------------------
# 5. Playwright tests — UI, pipeline/pruning E2E, and slider regression
# ------------------------------------------------------------------
echo ""
echo "[5/6] Playwright tests..."
npx playwright test "$@"

# ------------------------------------------------------------------
# 6. PLY parser unit tests
# ------------------------------------------------------------------
echo ""
echo "[6/6] PLY parser unit tests..."
node --test tests/plyParser.test.mjs

cd "$PROJECT_ROOT"
echo ""
echo "=== ALL TESTS PASSED ==="
