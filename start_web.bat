@echo off
REM AutoForge Web Interface Launch Script for Windows

echo.
echo 🔥 AutoForge Web Interface
echo ==========================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if required dependencies are installed
echo Checking dependencies...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Flask not found. Installing web dependencies...
    pip install flask flask-socketio python-socketio werkzeug
    if errorlevel 1 (
        echo ❌ Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Default values
set HOST=127.0.0.1
set PORT=5000
set DEBUG=

REM Parse command line arguments
:parse_args
if "%1"=="" goto start_server
if "%1"=="--host" (
    set HOST=%2
    shift
    shift
    goto parse_args
)
if "%1"=="--port" (
    set PORT=%2
    shift
    shift
    goto parse_args
)
if "%1"=="--debug" (
    set DEBUG=--debug
    shift
    goto parse_args
)
if "%1"=="--help" (
    echo Usage: start_web.bat [options]
    echo.
    echo Options:
    echo   --host HOST    Host to bind to (default: 127.0.0.1^)
    echo   --port PORT    Port to bind to (default: 5000^)
    echo   --debug        Enable debug mode
    echo   --help         Show this help message
    echo.
    echo Examples:
    echo   start_web.bat
    echo   start_web.bat --host 0.0.0.0 --port 8080
    echo   start_web.bat --debug
    pause
    exit /b 0
)
echo Unknown option: %1
echo Use --help for usage information
pause
exit /b 1

:start_server
echo.
echo Starting AutoForge Web Interface...
echo Host: %HOST%
echo Port: %PORT%
echo.
echo 📱 Open your browser to: http://%HOST%:%PORT%
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the web server
python -m autoforge.web_app --host %HOST% --port %PORT% %DEBUG%
