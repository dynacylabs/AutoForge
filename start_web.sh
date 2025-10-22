#!/bin/bash
# AutoForge Web Interface Launch Script

echo "🔥 AutoForge Web Interface"
echo "=========================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if required dependencies are installed
echo "Checking dependencies..."
python3 -c "import flask" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Flask not found. Installing web dependencies..."
    pip install flask flask-socketio python-socketio werkzeug
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
fi

# Default values
HOST="127.0.0.1"
PORT="5000"
DEBUG=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            DEBUG="--debug"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --host HOST    Host to bind to (default: 127.0.0.1)"
            echo "  --port PORT    Port to bind to (default: 5000)"
            echo "  --debug        Enable debug mode"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0"
            echo "  $0 --host 0.0.0.0 --port 8080"
            echo "  $0 --debug"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo ""
echo "Starting AutoForge Web Interface..."
echo "Host: $HOST"
echo "Port: $PORT"
echo ""
echo "📱 Open your browser to: http://$HOST:$PORT"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the web server
python3 -m autoforge.web_app --host "$HOST" --port "$PORT" $DEBUG
