#!/bin/bash
# Docker entrypoint for CDF STT Service
# Starts the FastAPI application

set -e

echo "Starting CDF STT Service..."
echo "Model: ${WHISPER_MODEL_SIZE:-large-v3}"
echo "Device: ${WHISPER_DEVICE:-cuda}"
echo "Compute Type: ${WHISPER_COMPUTE_TYPE:-float16}"

# Start uvicorn
cd /app
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
