@echo off
setlocal enabledelayedexpansion
rem Starts the AutoForge web UI on Windows. Run install.bat first if you
rem haven't already. Mirrors run_webui.sh - see that file for the
rem Linux/macOS equivalent.
cd /d "%~dp0"

if "%WEBUI_HOST%"=="" set "WEBUI_HOST=0.0.0.0"
if "%WEBUI_PORT%"=="" set "WEBUI_PORT=8000"
if "%BUILD_FRONTEND%"=="" set "BUILD_FRONTEND=true"

set "SHOULD_BUILD=false"
if "%BUILD_FRONTEND%"=="true" set "SHOULD_BUILD=true"
if "%BUILD_FRONTEND%"=="auto" if not exist "webui\frontend\dist" set "SHOULD_BUILD=true"

if "%SHOULD_BUILD%"=="true" (
    echo [webui] Building frontend...
    where npm >nul 2>nul
    if errorlevel 1 (
        echo [webui] ERROR: npm not found. Install Node.js or set BUILD_FRONTEND=false.
        exit /b 1
    )
    pushd webui\frontend
    call npm install
    call npm run build
    popd
    echo [webui] Frontend built.
)

echo [webui] Starting server on http://%WEBUI_HOST%:%WEBUI_PORT%

if not "%NO_BROWSER%"=="true" (
    start "" cmd /c "timeout /t 2 >nul & start "" http://localhost:%WEBUI_PORT%"
)

uv run uvicorn autoforge.webui.server:app --host %WEBUI_HOST% --port %WEBUI_PORT%
