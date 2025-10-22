// AutoForge Web Interface - Client-side JavaScript

// Global state
let currentJobId = null;
let socket = null;
let uploadedFiles = {
    image: null,
    materials: null
};

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function initializeApp() {
    // Set up file inputs
    setupFileInputs();
    
    // Set up configuration tabs
    setupConfigTabs();
    
    // Set up buttons
    setupButtons();
    
    // Set up color picker sync
    setupColorPicker();
    
    // Set up pruning toggle
    setupPruningToggle();
    
    // Initialize SocketIO connection
    initializeSocket();
}

// File input handlers
function setupFileInputs() {
    const imageInput = document.getElementById('image-input');
    const materialInput = document.getElementById('material-input');
    
    imageInput.addEventListener('change', (e) => handleFileSelect(e, 'image'));
    materialInput.addEventListener('change', (e) => handleFileSelect(e, 'materials'));
}

function handleFileSelect(event, type) {
    const file = event.target.files[0];
    if (!file) return;
    
    uploadedFiles[type] = file;
    
    // Update file name display
    const nameElement = document.getElementById(`${type}-name`);
    nameElement.textContent = file.name;
    nameElement.style.color = 'var(--success-color)';
    
    // Show image preview
    if (type === 'image') {
        const reader = new FileReader();
        reader.onload = (e) => {
            const preview = document.getElementById('image-preview');
            preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
        };
        reader.readAsDataURL(file);
    }
    
    // Enable upload button if both files are selected
    checkUploadReady();
}

function checkUploadReady() {
    const uploadBtn = document.getElementById('upload-btn');
    if (uploadedFiles.image && uploadedFiles.materials) {
        uploadBtn.disabled = false;
    }
}

// Configuration tabs
function setupConfigTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all tabs
            tabButtons.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active class to clicked tab
            btn.classList.add('active');
            const tabId = btn.dataset.tab + '-tab';
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// Button handlers
function setupButtons() {
    document.getElementById('upload-btn').addEventListener('click', uploadFiles);
    document.getElementById('start-btn').addEventListener('click', startOptimization);
    document.getElementById('cancel-btn').addEventListener('click', cancelJob);
    document.getElementById('new-project-btn').addEventListener('click', resetApp);
}

// Color picker sync
function setupColorPicker() {
    const colorPicker = document.getElementById('background_color');
    const colorHex = document.getElementById('background_color_hex');
    
    colorPicker.addEventListener('change', (e) => {
        colorHex.value = e.target.value;
    });
    
    colorHex.addEventListener('change', (e) => {
        if (/^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
            colorPicker.value = e.target.value;
        }
    });
}

// Pruning toggle
function setupPruningToggle() {
    const pruningCheckbox = document.getElementById('perform_pruning');
    const colorsGroup = document.getElementById('pruning_colors_group');
    const swapsGroup = document.getElementById('pruning_swaps_group');
    
    pruningCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            colorsGroup.style.display = 'flex';
            swapsGroup.style.display = 'flex';
        } else {
            colorsGroup.style.display = 'none';
            swapsGroup.style.display = 'none';
        }
    });
}

// Upload files to server
async function uploadFiles() {
    const uploadBtn = document.getElementById('upload-btn');
    const statusDiv = document.getElementById('upload-status');
    
    uploadBtn.disabled = true;
    statusDiv.textContent = 'Uploading files...';
    statusDiv.className = 'status-message';
    statusDiv.style.display = 'block';
    
    const formData = new FormData();
    formData.append('image', uploadedFiles.image);
    formData.append('materials', uploadedFiles.materials);
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentJobId = data.job_id;
            statusDiv.textContent = 'Files uploaded successfully!';
            statusDiv.className = 'status-message success';
            
            // Show configuration section
            setTimeout(() => {
                document.getElementById('config-section').style.display = 'block';
                document.getElementById('config-section').scrollIntoView({ behavior: 'smooth' });
            }, 1000);
        } else {
            throw new Error(data.error || 'Upload failed');
        }
    } catch (error) {
        statusDiv.textContent = `Error: ${error.message}`;
        statusDiv.className = 'status-message error';
        uploadBtn.disabled = false;
    }
}

// Start optimization
async function startOptimization() {
    if (!currentJobId) {
        alert('Please upload files first');
        return;
    }
    
    // Gather parameters
    const params = {
        job_id: currentJobId,
        iterations: parseInt(document.getElementById('iterations').value),
        learning_rate: parseFloat(document.getElementById('learning_rate').value),
        layer_height: parseFloat(document.getElementById('layer_height').value),
        max_layers: parseInt(document.getElementById('max_layers').value),
        min_layers: parseInt(document.getElementById('min_layers').value),
        background_height: parseFloat(document.getElementById('background_height').value),
        background_color: document.getElementById('background_color').value,
        stl_output_size: parseInt(document.getElementById('stl_output_size').value),
        processing_reduction_factor: parseInt(document.getElementById('processing_reduction_factor').value),
        nozzle_diameter: parseFloat(document.getElementById('nozzle_diameter').value),
        init_tau: parseFloat(document.getElementById('init_tau').value),
        final_tau: parseFloat(document.getElementById('final_tau').value),
        warmup_fraction: parseFloat(document.getElementById('warmup_fraction').value),
        num_init_rounds: parseInt(document.getElementById('num_init_rounds').value),
        early_stopping: parseInt(document.getElementById('early_stopping').value),
        perform_pruning: document.getElementById('perform_pruning').checked,
        pruning_max_colors: parseInt(document.getElementById('pruning_max_colors').value),
        pruning_max_swaps: parseInt(document.getElementById('pruning_max_swaps').value)
    };
    
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Hide config section and show processing section
            document.getElementById('config-section').style.display = 'none';
            document.getElementById('processing-section').style.display = 'block';
            document.getElementById('processing-section').scrollIntoView({ behavior: 'smooth' });
        } else {
            throw new Error(data.error || 'Failed to start optimization');
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

// Cancel job
async function cancelJob() {
    if (!currentJobId || !confirm('Are you sure you want to cancel this job?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/cancel/${currentJobId}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            document.getElementById('status-message').textContent = 'Job cancelled';
            setTimeout(() => {
                resetApp();
            }, 2000);
        }
    } catch (error) {
        console.error('Error cancelling job:', error);
    }
}

// Reset app for new project
function resetApp() {
    // Reset state
    currentJobId = null;
    uploadedFiles = { image: null, materials: null };
    
    // Reset UI
    document.getElementById('image-input').value = '';
    document.getElementById('material-input').value = '';
    document.getElementById('image-name').textContent = 'No file selected';
    document.getElementById('material-name').textContent = 'No file selected';
    document.getElementById('image-preview').innerHTML = '';
    
    // Hide all sections except upload
    document.getElementById('config-section').style.display = 'none';
    document.getElementById('processing-section').style.display = 'none';
    document.getElementById('results-section').style.display = 'none';
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// SocketIO handlers
function initializeSocket() {
    socket = io('/autoforge');
    
    socket.on('connect', () => {
        console.log('Connected to server');
    });
    
    socket.on('connected', (data) => {
        console.log('Server message:', data.message);
    });
    
    socket.on('progress', (data) => {
        updateProgress(data);
    });
    
    socket.on('status', (data) => {
        document.getElementById('status-message').textContent = data.message;
    });
    
    socket.on('job_started', (data) => {
        console.log('Job started:', data.job_id);
    });
    
    socket.on('job_completed', (data) => {
        handleJobCompleted(data);
    });
    
    socket.on('job_failed', (data) => {
        handleJobFailed(data);
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });
}

// Update progress display
function updateProgress(data) {
    const progressFill = document.getElementById('progress-fill');
    const progressPercentage = document.getElementById('progress-percentage');
    const progressIteration = document.getElementById('progress-iteration');
    const lossDisplay = document.getElementById('loss-display');
    const previewImage = document.getElementById('preview-image');
    
    progressFill.style.width = data.progress + '%';
    progressPercentage.textContent = data.progress + '%';
    progressIteration.textContent = `Iteration ${data.iteration} / ${data.total_iterations}`;
    lossDisplay.textContent = `Loss: ${data.loss.toFixed(6)}`;
    
    // Update preview if available
    if (data.preview) {
        previewImage.src = data.preview;
        previewImage.style.display = 'block';
    }
}

// Handle job completion
function handleJobCompleted(data) {
    // Hide processing section
    document.getElementById('processing-section').style.display = 'none';
    
    // Show results section
    const resultsSection = document.getElementById('results-section');
    resultsSection.style.display = 'block';
    
    // Load result image
    const resultImage = document.getElementById('result-image');
    resultImage.src = `/api/download/${data.job_id}/${data.outputs.discretized_image}`;
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// Handle job failure
function handleJobFailed(data) {
    const statusMessage = document.getElementById('status-message');
    statusMessage.textContent = `Error: ${data.error}`;
    statusMessage.style.color = 'var(--error-color)';
    
    document.getElementById('cancel-btn').textContent = 'Back';
    document.getElementById('cancel-btn').onclick = resetApp;
}

// Download file
function downloadFile(filename) {
    if (!currentJobId) return;
    
    const url = `/api/download/${currentJobId}/${filename}`;
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Tooltips
document.addEventListener('DOMContentLoaded', () => {
    const tooltips = document.querySelectorAll('.tooltip');
    
    tooltips.forEach(tooltip => {
        const text = tooltip.dataset.tooltip;
        if (text) {
            tooltip.title = text;
        }
    });
});
