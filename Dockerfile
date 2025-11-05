# CDF Speech-to-Text Service Dockerfile
# Multi-stage build for WhisperX with CUDA support and Diarization

FROM nvidia/cuda:12.8.0-cudnn9-runtime-ubuntu22.04 as base

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-dev \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libavdevice-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN python -m pip install --upgrade pip

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/ ./api/
COPY app/ ./app/

# Create directory for model cache
RUN mkdir -p /root/.cache/huggingface

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV WHISPER_MODEL_SIZE=large-v3
ENV WHISPER_DEVICE=cuda
ENV WHISPER_COMPUTE_TYPE=float16
# Set HF_TOKEN via docker run -e HF_TOKEN=your_token or docker-compose
ENV HF_TOKEN=""

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the FastAPI application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

