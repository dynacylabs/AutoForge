# AutoForge Web Interface - Quick Start Guide

## Installation

```bash
# Install web dependencies
pip install flask flask-socketio python-socketio werkzeug

# Or install all dependencies
pip install -r requirements.txt
```

## Starting the Server

### Option 1: Command-line script (recommended)
```bash
autoforge-web
```

### Option 2: Python module
```bash
python -m autoforge.web_app
```

### Option 3: Custom host/port
```bash
autoforge-web --host 0.0.0.0 --port 8080
```

### Option 4: Debug mode
```bash
autoforge-web --debug
```

## Accessing the Interface

Open your browser and go to:
```
http://localhost:5000
```

## Quick Workflow

1. **Upload Files**
   - Select your input image (PNG, JPG, etc.)
   - Select your filament data (CSV or JSON from HueForge)
   - Click "Upload Files"

2. **Configure Parameters**
   - Adjust settings in Basic, Advanced, or Output tabs
   - Common adjustments:
     - Iterations: 2000 (default) or higher for better quality
     - Max Layers: 75 (default) or adjust as needed
     - Enable Pruning if you want to limit colors/swaps

3. **Start Optimization**
   - Click "Start Optimization"
   - Watch progress in real-time
   - See live preview updates

4. **Download Results**
   - Download discretized image (PNG)
   - Download 3D model (STL)
   - Download swap instructions (TXT)
   - Download HueForge project (JSON)

## Tips

### Best Quality
- Iterations: 4000+
- Max Layers: 100+
- Disable pruning

### Fastest Processing
- Iterations: 1000-2000
- Max Layers: 50
- Enable pruning
- Processing Reduction: 4

### Limited Filaments
- Enable pruning
- Set Max Colors to number of filaments you have
- Adjust Max Swaps based on preference

## Troubleshooting

### Port in use?
```bash
autoforge-web --port 8080
```

### Can't connect?
- Check if server is running
- Try http://127.0.0.1:5000
- Check firewall settings

### Upload fails?
- Check file format (images: PNG/JPG/etc., materials: CSV/JSON)
- Ensure files < 50MB
- Verify material file is valid HueForge export

## Need Help?

See full documentation in `web/README.md`
