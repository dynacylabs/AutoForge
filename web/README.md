# AutoForge Web Interface

A modern, user-friendly web interface for AutoForge that allows you to convert images to 3D-printable multi-layer models directly from your browser.

## Features

- 🖼️ **Easy File Upload**: Drag-and-drop or click to upload images and filament data
- ⚙️ **Parameter Configuration**: Fine-tune optimization settings with an intuitive interface
- 📊 **Real-time Progress**: Watch your optimization progress with live updates and preview images
- 📦 **Multiple Output Formats**: Download discretized images, STL files, swap instructions, and HueForge projects
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile devices
- 🔄 **Background Processing**: Optimization runs asynchronously so you can monitor progress without blocking

## Screenshots

### Step 1: Upload Files
Upload your input image and filament data (CSV or JSON from HueForge).

### Step 2: Configure Parameters
Adjust optimization parameters with organized tabs for Basic, Advanced, and Output settings.

### Step 3: Monitor Progress
Watch real-time progress updates with live preview images and loss metrics.

### Step 4: Download Results
Get your discretized image, STL model, swap instructions, and HueForge project file.

## Installation

### Prerequisites

- Python 3.9 or higher
- AutoForge dependencies (see main README.md)

### Install Web Dependencies

From the AutoForge root directory:

```bash
pip install flask flask-socketio python-socketio werkzeug
```

Or install all dependencies including web support:

```bash
pip install -r requirements.txt
```

## Usage

### Starting the Web Server

There are several ways to start the web interface:

#### Method 1: Using the command-line script (if installed)

```bash
autoforge-web
```

#### Method 2: Direct Python execution

```bash
python -m autoforge.web_app
```

#### Method 3: From the source directory

```bash
cd src/autoforge
python web_app.py
```

### Command-line Options

```bash
autoforge-web --help
```

Available options:
- `--host HOST`: Host to bind to (default: 127.0.0.1)
- `--port PORT`: Port to bind to (default: 5000)
- `--debug`: Enable debug mode with auto-reload

Examples:

```bash
# Start on default host and port (localhost:5000)
autoforge-web

# Allow external connections
autoforge-web --host 0.0.0.0 --port 8080

# Enable debug mode for development
autoforge-web --debug
```

### Accessing the Web Interface

Once the server is running, open your web browser and navigate to:

```
http://localhost:5000
```

Or if you specified a different host/port:

```
http://your-host:your-port
```

## Using the Web Interface

### 1. Upload Files

1. Click on the **Input Image** box and select your image file (PNG, JPG, JPEG, BMP, or WEBP)
2. Click on the **Filament Data** box and select your materials file (CSV or JSON)
3. Click **Upload Files** to send them to the server

**Note**: To get your filament CSV or JSON file, export it from HueForge:
- Open HueForge
- Go to the "Filaments" menu
- Click the export button
- Select your desired filaments
- Export as CSV or JSON

### 2. Configure Parameters

The configuration is organized into three tabs:

#### Basic Tab
- **Iterations**: Number of optimization steps (higher = better quality, longer time)
- **Max Layers**: Maximum number of filament layers
- **Layer Height**: Height of each layer in mm
- **Background Height**: Height of the solid background base
- **Background Color**: Color of the background layer (hex format)
- **STL Output Size**: Size of the longest dimension in mm

#### Advanced Tab
- **Learning Rate**: Optimization learning rate
- **Initial/Final Tau**: Temperature parameters for Gumbel-Softmax
- **Warmup Fraction**: Portion of iterations for warmup
- **Init Rounds**: Number of initialization rounds for height map
- **Early Stopping**: Stop after N iterations without improvement

#### Output Tab
- **Nozzle Diameter**: Your 3D printer's nozzle diameter
- **Processing Reduction**: Factor to reduce processing resolution
- **Min Layers**: Minimum number of layers
- **Enable Pruning**: Limit the number of colors and swaps
  - **Max Colors**: Maximum number of different filaments
  - **Max Swaps**: Maximum number of filament changes

### 3. Start Optimization

Click **Start Optimization** to begin processing. You'll see:
- A progress bar showing completion percentage
- Current iteration number
- Loss value (lower is better)
- Live preview images updating during optimization

You can cancel the job at any time using the **Cancel** button.

### 4. Download Results

Once optimization is complete, you can download:
- **Discretized Image** (PNG): The final layered image
- **3D Model** (STL): Ready for 3D printing
- **Swap Instructions** (TXT): When to change filaments
- **HueForge Project** (JSON): Import into HueForge for manual adjustments

Click **Start New Project** to process another image.

## Configuration Tips

### For Best Quality
- Increase **Iterations** to 4000-6000
- Increase **Max Layers** to 100+
- Disable **Pruning** or increase limits
- Set **Processing Reduction** to 1

### For Faster Results
- Decrease **Iterations** to 1000-2000
- Decrease **Max Layers** to 50
- Enable **Pruning** with stricter limits
- Increase **Processing Reduction** to 4

### For Limited Filament Collection
- Enable **Pruning**
- Set **Max Colors** to the number of filaments you have
- Adjust **Max Swaps** based on your patience

## Technical Details

### Architecture

The web interface uses:
- **Backend**: Flask web framework with Flask-SocketIO for real-time communication
- **Frontend**: Vanilla JavaScript with WebSocket support for live updates
- **Styling**: Modern CSS with responsive design
- **Communication**: REST API for file uploads and job management, WebSocket for progress updates

### File Storage

- Uploaded files are stored in temporary directories
- Output files are stored per-job for easy retrieval
- Files are kept until the server is restarted or manually cleaned

### Performance

- Optimization runs in background threads
- Multiple jobs can be processed sequentially
- Preview images are sent periodically to avoid overwhelming the connection
- GPU acceleration is used if available (CUDA, ROCm, or MPS)

## Troubleshooting

### Port Already in Use

If port 5000 is already in use:

```bash
autoforge-web --port 8080
```

### Cannot Connect to Server

- Ensure the server is running
- Check firewall settings
- Verify the host and port are correct

### Upload Fails

- Check file formats (images: PNG/JPG/etc., materials: CSV/JSON)
- Ensure files are not corrupted
- Check file size (max 50MB per file)

### Optimization Fails

- Check console/logs for error messages
- Verify material file has correct format
- Ensure sufficient system memory
- Try reducing image size or max layers

### Preview Not Updating

- Check browser console for WebSocket errors
- Refresh the page and try again
- Ensure browser supports WebSocket

## Development

### Running in Debug Mode

```bash
autoforge-web --debug
```

Debug mode enables:
- Auto-reload on code changes
- Detailed error messages
- Flask debugging tools

### File Structure

```
AutoForge/
├── src/autoforge/
│   └── web_app.py          # Flask application
├── web/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css   # Styling
│   │   └── js/
│   │       └── app.js      # Client-side logic
│   └── templates/
│       └── index.html      # Main HTML page
└── requirements.txt        # Dependencies
```

### API Endpoints

- `GET /`: Serve main page
- `POST /api/upload`: Upload files
- `POST /api/start`: Start optimization job
- `GET /api/status/<job_id>`: Get job status
- `POST /api/cancel/<job_id>`: Cancel job
- `GET /api/download/<job_id>/<filename>`: Download output file

### WebSocket Events

- `connect`: Client connected
- `progress`: Optimization progress update
- `status`: Status message
- `job_started`: Job started
- `job_completed`: Job finished successfully
- `job_failed`: Job failed with error

## Security Considerations

### For Production Use

If deploying for production:

1. **Use a production WSGI server** (e.g., Gunicorn):
   ```bash
   pip install gunicorn eventlet
   gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:5000 autoforge.web_app:app
   ```

2. **Set up proper authentication**: Add user authentication if needed

3. **Configure HTTPS**: Use a reverse proxy (nginx, Apache) with SSL

4. **Limit file uploads**: Adjust `MAX_CONTENT_LENGTH` in web_app.py

5. **Set resource limits**: Limit concurrent jobs and processing time

6. **Use environment variables**: For secret keys and configuration

## Contributing

Contributions to improve the web interface are welcome! Please:

1. Test your changes thoroughly
2. Maintain the existing code style
3. Update documentation as needed
4. Submit a pull request with a clear description

## License

Same as AutoForge main project: CC BY-NC-SA 4.0

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues and documentation
- Join the community discussions

## Acknowledgments

Built on top of the excellent AutoForge project by Hendric Voss.

---

**Happy 3D printing! 🎨🖨️**
