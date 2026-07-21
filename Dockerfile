# Use official Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    ffmpeg \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml README.md ./
COPY src ./src

# Install the package.
# We install torch CPU-only first so the ~3.5 GB CUDA libraries are not pulled in
# by default. GPU users can build with: --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN pip install --upgrade pip --no-cache-dir && \
    pip install --no-cache-dir \
        torch>=2.6.0 \
        torchvision>=0.21.0 \
        --extra-index-url ${TORCH_INDEX} && \
    pip install --no-cache-dir .

# Expose the web UI port
EXPOSE 7860

# Default: start the web UI.
# To run the CLI instead: docker run --entrypoint autoforge <image> [args]
ENTRYPOINT ["autoforge-webui"]
