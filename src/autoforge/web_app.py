#!/usr/bin/env python3
"""
Web interface for AutoForge using Flask and SocketIO for real-time updates.
"""

import argparse
import json
import os
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
import torch
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

# Import AutoForge modules
from autoforge.Helper.FilamentHelper import load_materials
from autoforge.Helper.ImageHelper import resize_image, imread
from autoforge.Helper.OutputHelper import (
    generate_stl,
    generate_swap_instructions,
    generate_project_file,
)
from autoforge.Modules.Optimizer import FilamentOptimizer
from autoforge.Helper.Heightmaps.ChristofidesHeightMap import run_init_threads
from autoforge.Loss.PerceptionLoss import PerceptionLoss

# Initialize Flask app
app = Flask(__name__, 
            static_folder='../../web/static',
            template_folder='../../web/templates')
app.config['SECRET_KEY'] = 'autoforge-secret-key-' + str(uuid.uuid4())
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp(prefix='autoforge_uploads_')
app.config['OUTPUT_FOLDER'] = tempfile.mkdtemp(prefix='autoforge_outputs_')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Job tracking
active_jobs: Dict[str, dict] = {}

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'webp'}
ALLOWED_MATERIAL_EXTENSIONS = {'csv', 'json'}


def allowed_file(filename: str, allowed_exts) -> bool:
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_exts


class ProgressCallback:
    """Callback class to send progress updates via SocketIO."""
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.last_update = 0
        self.update_interval = 0.5  # seconds
    
    def update(self, iteration: int, total_iterations: int, loss: float, 
               preview_image: Optional[np.ndarray] = None):
        """Send progress update."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval and iteration < total_iterations - 1:
            return
        
        self.last_update = current_time
        progress_data = {
            'job_id': self.job_id,
            'iteration': iteration,
            'total_iterations': total_iterations,
            'progress': int((iteration / total_iterations) * 100),
            'loss': float(loss)
        }
        
        # Send preview image if available
        if preview_image is not None:
            # Convert to base64 for web display
            import base64
            _, buffer = cv2.imencode('.jpg', preview_image)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            progress_data['preview'] = f'data:image/jpeg;base64,{img_base64}'
        
        socketio.emit('progress', progress_data, namespace='/autoforge')
        
        # Update job status
        if self.job_id in active_jobs:
            active_jobs[self.job_id]['progress'] = progress_data['progress']
            active_jobs[self.job_id]['iteration'] = iteration


def run_autoforge_optimization(job_id: str, image_path: str, material_file: str, params: dict):
    """Run AutoForge optimization in a background thread."""
    try:
        # Update job status
        active_jobs[job_id]['status'] = 'running'
        socketio.emit('job_started', {'job_id': job_id}, namespace='/autoforge')
        
        # Set up device
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load materials
        if material_file.endswith('.csv'):
            materials = load_materials(csv_file=material_file)
        else:
            materials = load_materials(json_file=material_file)
        
        material_colors = torch.tensor(materials['colors'], dtype=torch.float32, device=device) / 255.0
        material_TDs = torch.tensor(materials['TDs'], dtype=torch.float32, device=device)
        
        # Load and resize image
        target_image = imread(image_path)
        processing_size = params.get('stl_output_size', 150) // params.get('processing_reduction_factor', 2)
        target_image = resize_image(target_image, processing_size, processing_size)
        target_tensor = torch.tensor(target_image, dtype=torch.float32, device=device) / 255.0
        
        # Background color
        from autoforge.Helper.FilamentHelper import hex_to_rgb
        background_rgb = hex_to_rgb(params.get('background_color', '#000000'))
        background_tensor = torch.tensor(background_rgb, dtype=torch.float32, device=device) / 255.0
        
        # Initialize height map
        socketio.emit('status', {
            'job_id': job_id,
            'message': 'Initializing height map...'
        }, namespace='/autoforge')
        
        pixel_height_logits_init, pixel_height_labels, global_logits_init = run_init_threads(
            target_image,
            material_colors.cpu().numpy() * 255,
            material_TDs.cpu().numpy(),
            background_rgb,
            params.get('max_layers', 75),
            params.get('layer_height', 0.04),
            params.get('background_height', 0.24),
            params.get('num_init_rounds', 8),
            params.get('num_init_cluster_layers', -1)
        )
        
        # Initialize perception loss
        perception_loss_module = PerceptionLoss(device=device)
        
        # Create namespace for arguments
        args_ns = argparse.Namespace(**params)
        args_ns.visualize = False  # Disable matplotlib visualization for web
        
        # Initialize optimizer
        socketio.emit('status', {
            'job_id': job_id,
            'message': 'Starting optimization...'
        }, namespace='/autoforge')
        
        optimizer = FilamentOptimizer(
            args=args_ns,
            target=target_tensor,
            pixel_height_logits_init=pixel_height_logits_init,
            pixel_height_labels=pixel_height_labels,
            global_logits_init=global_logits_init,
            material_colors=material_colors,
            material_TDs=material_TDs,
            background=background_tensor,
            device=device,
            perception_loss_module=perception_loss_module
        )
        
        # Create progress callback
        progress_callback = ProgressCallback(job_id)
        
        # Run optimization
        iterations = params.get('iterations', 2000)
        for i in range(iterations):
            if active_jobs[job_id].get('cancelled', False):
                raise Exception('Job cancelled by user')
            
            loss = optimizer.step()
            
            # Get preview every N iterations
            if i % 50 == 0 or i == iterations - 1:
                with torch.no_grad():
                    preview = optimizer.get_composite_image_disc()
                    preview_np = (preview.cpu().numpy() * 255).astype(np.uint8)
                    progress_callback.update(i + 1, iterations, loss, preview_np)
            else:
                progress_callback.update(i + 1, iterations, loss)
        
        # Get final results
        socketio.emit('status', {
            'job_id': job_id,
            'message': 'Generating outputs...'
        }, namespace='/autoforge')
        
        with torch.no_grad():
            final_image = optimizer.get_composite_image_disc()
            final_image_np = (final_image.cpu().numpy() * 255).astype(np.uint8)
            height_map = optimizer.get_height_map()
        
        # Save outputs
        output_dir = Path(app.config['OUTPUT_FOLDER']) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save discretized image
        discrete_path = output_dir / 'discretized.png'
        cv2.imwrite(str(discrete_path), cv2.cvtColor(final_image_np, cv2.COLOR_RGB2BGR))
        
        # Generate STL
        socketio.emit('status', {
            'job_id': job_id,
            'message': 'Generating STL file...'
        }, namespace='/autoforge')
        
        stl_path = output_dir / 'model.stl'
        generate_stl(
            height_map,
            str(stl_path),
            params.get('stl_output_size', 150),
            params.get('nozzle_diameter', 0.4)
        )
        
        # Generate swap instructions
        swap_instructions = generate_swap_instructions(
            optimizer.get_best_discrete_solution(),
            materials['names'],
            params.get('layer_height', 0.04),
            params.get('background_height', 0.24)
        )
        
        swap_path = output_dir / 'swap_instructions.txt'
        with open(swap_path, 'w') as f:
            f.write(swap_instructions)
        
        # Generate project file
        try:
            project_path = output_dir / 'project.json'
            generate_project_file(
                optimizer.get_best_discrete_solution(),
                materials,
                str(project_path),
                params.get('layer_height', 0.04),
                params.get('background_height', 0.24),
                params.get('stl_output_size', 150)
            )
        except Exception as e:
            print(f"Warning: Could not generate project file: {e}")
        
        # Update job status
        active_jobs[job_id]['status'] = 'completed'
        active_jobs[job_id]['progress'] = 100
        active_jobs[job_id]['outputs'] = {
            'discretized_image': str(discrete_path.name),
            'stl_file': str(stl_path.name),
            'swap_instructions': str(swap_path.name),
            'project_file': str(project_path.name) if project_path.exists() else None
        }
        
        socketio.emit('job_completed', {
            'job_id': job_id,
            'outputs': active_jobs[job_id]['outputs']
        }, namespace='/autoforge')
        
    except Exception as e:
        # Handle errors
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"Error in job {job_id}: {error_msg}\n{error_trace}")
        
        active_jobs[job_id]['status'] = 'failed'
        active_jobs[job_id]['error'] = error_msg
        
        socketio.emit('job_failed', {
            'job_id': job_id,
            'error': error_msg
        }, namespace='/autoforge')


@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Handle file uploads."""
    if 'image' not in request.files or 'materials' not in request.files:
        return jsonify({'error': 'Missing required files'}), 400
    
    image_file = request.files['image']
    material_file = request.files['materials']
    
    if image_file.filename == '' or material_file.filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    if not allowed_file(image_file.filename, ALLOWED_EXTENSIONS):
        return jsonify({'error': 'Invalid image file type'}), 400
    
    if not allowed_file(material_file.filename, ALLOWED_MATERIAL_EXTENSIONS):
        return jsonify({'error': 'Invalid material file type'}), 400
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded files
    image_filename = secure_filename(image_file.filename)
    material_filename = secure_filename(material_file.filename)
    
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{image_filename}")
    material_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{material_filename}")
    
    image_file.save(image_path)
    material_file.save(material_path)
    
    # Store job info
    active_jobs[job_id] = {
        'id': job_id,
        'status': 'uploaded',
        'progress': 0,
        'image_path': image_path,
        'material_path': material_path,
        'created_at': time.time()
    }
    
    return jsonify({
        'job_id': job_id,
        'message': 'Files uploaded successfully'
    })


@app.route('/api/start', methods=['POST'])
def start_optimization():
    """Start an optimization job."""
    data = request.json
    job_id = data.get('job_id')
    
    if not job_id or job_id not in active_jobs:
        return jsonify({'error': 'Invalid job ID'}), 400
    
    if active_jobs[job_id]['status'] != 'uploaded':
        return jsonify({'error': 'Job already started or completed'}), 400
    
    # Get parameters
    params = {
        'iterations': data.get('iterations', 2000),
        'learning_rate': data.get('learning_rate', 0.015),
        'layer_height': data.get('layer_height', 0.04),
        'max_layers': data.get('max_layers', 75),
        'min_layers': data.get('min_layers', 0),
        'background_height': data.get('background_height', 0.24),
        'background_color': data.get('background_color', '#000000'),
        'stl_output_size': data.get('stl_output_size', 150),
        'processing_reduction_factor': data.get('processing_reduction_factor', 2),
        'nozzle_diameter': data.get('nozzle_diameter', 0.4),
        'init_tau': data.get('init_tau', 1.0),
        'final_tau': data.get('final_tau', 0.01),
        'warmup_fraction': data.get('warmup_fraction', 1.0),
        'learning_rate_warmup_fraction': data.get('learning_rate_warmup_fraction', 0.01),
        'num_init_rounds': data.get('num_init_rounds', 8),
        'num_init_cluster_layers': data.get('num_init_cluster_layers', -1),
        'early_stopping': data.get('early_stopping', 2000),
        'perform_pruning': data.get('perform_pruning', False),
        'pruning_max_colors': data.get('pruning_max_colors', 8),
        'pruning_max_swaps': data.get('pruning_max_swaps', 20),
        'visualize': False,
        'tensorboard': False
    }
    
    active_jobs[job_id]['params'] = params
    
    # Start optimization in background thread
    thread = threading.Thread(
        target=run_autoforge_optimization,
        args=(job_id, active_jobs[job_id]['image_path'], 
              active_jobs[job_id]['material_path'], params)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'message': 'Optimization started'
    })


@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get job status."""
    if job_id not in active_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = active_jobs[job_id]
    return jsonify({
        'job_id': job_id,
        'status': job['status'],
        'progress': job.get('progress', 0),
        'outputs': job.get('outputs', None),
        'error': job.get('error', None)
    })


@app.route('/api/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running job."""
    if job_id not in active_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    active_jobs[job_id]['cancelled'] = True
    active_jobs[job_id]['status'] = 'cancelled'
    
    return jsonify({'message': 'Job cancelled'})


@app.route('/api/download/<job_id>/<filename>')
def download_file(job_id, filename):
    """Download an output file."""
    if job_id not in active_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    output_dir = Path(app.config['OUTPUT_FOLDER']) / job_id
    file_path = output_dir / filename
    
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(file_path, as_attachment=True)


@socketio.on('connect', namespace='/autoforge')
def handle_connect():
    """Handle client connection."""
    print('Client connected')
    emit('connected', {'message': 'Connected to AutoForge server'})


@socketio.on('disconnect', namespace='/autoforge')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')


def main():
    """Main entry point for web interface."""
    parser = argparse.ArgumentParser(description='AutoForge Web Interface')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print(f"Starting AutoForge Web Interface on http://{args.host}:{args.port}")
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Output folder: {app.config['OUTPUT_FOLDER']}")
    
    socketio.run(app, host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
