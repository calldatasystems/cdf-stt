#!/bin/bash
#
# CDF STT Service Startup Script
# Run this after SSH'ing into Vast.ai instance
#

set -e

echo "======================================"
echo "CDF STT Service Startup"
echo "======================================"

# Environment variables
# HF_TOKEN is embedded in the Docker image during build
# If not set, check for argument or exit with error
if [ -z "$HF_TOKEN" ]; then
    if [ -n "$1" ]; then
        export HF_TOKEN="$1"
        echo "⚠ Using HF_TOKEN from command line argument"
    else
        echo "ERROR: HF_TOKEN not set!"
        echo "This should be embedded in the Docker image."
        echo "If running manually, use: $0 <hf_token>"
        exit 1
    fi
else
    echo "✓ Using HF_TOKEN from Docker image"
fi

export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
export PYTHONPATH=/app:$PYTHONPATH

# Whisper model configuration
export WHISPER_MODEL_SIZE=large-v3
export WHISPER_DEVICE=cuda
export WHISPER_COMPUTE_TYPE=float16

# Redis configuration
export REDIS_HOST=localhost
export REDIS_PORT=6379

echo ""
echo "Step 1: Stopping existing processes..."
pkill -f uvicorn || true
pkill -f "python -m app.worker" || true
pkill -f redis-server || true
sleep 2

echo ""
echo "Step 2: Starting Redis server..."
redis-server --daemonize yes --bind 0.0.0.0 --protected-mode no
sleep 2

# Verify Redis is running
if redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis started successfully"
else
    echo "✗ Redis failed to start"
    exit 1
fi

echo ""
echo "Step 3: Starting API server on port 8000..."
cd /app
nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
sleep 3

# Check API process
if ps aux | grep -v grep | grep "uvicorn api.main:app" > /dev/null; then
    echo "✓ API server started successfully"
else
    echo "✗ API server failed to start"
    echo "Last 20 lines of API log:"
    tail -20 /tmp/api.log
    exit 1
fi

echo ""
echo "Step 4: Starting worker process..."
nohup python -m app.worker > /tmp/worker.log 2>&1 &
sleep 3

# Check worker process
if ps aux | grep -v grep | grep "python -m app.worker" > /dev/null; then
    echo "✓ Worker started successfully"
else
    echo "✗ Worker failed to start"
    echo "Last 20 lines of worker log:"
    tail -20 /tmp/worker.log
    exit 1
fi

echo ""
echo "======================================"
echo "Service Status"
echo "======================================"

echo ""
echo "Running Processes:"
ps aux | grep -E "(redis-server|uvicorn|worker)" | grep -v grep

echo ""
echo "======================================"
echo "Service Endpoints"
echo "======================================"

# Get external IP and port from Vast.ai
EXTERNAL_IP=$(curl -s ifconfig.me)
echo ""
echo "External API URL: http://$EXTERNAL_IP:34360"
echo ""
echo "Available endpoints:"
echo "  - Health:        GET  http://$EXTERNAL_IP:34360/health"
echo "  - Languages:     GET  http://$EXTERNAL_IP:34360/languages"
echo "  - Transcribe:    POST http://$EXTERNAL_IP:34360/transcribe"
echo "  - Async Submit:  POST http://$EXTERNAL_IP:34360/transcribe/async"
echo "  - Job Status:    GET  http://$EXTERNAL_IP:34360/jobs/{job_id}"
echo "  - Queue Stats:   GET  http://$EXTERNAL_IP:34360/queue/stats"
echo "  - Metrics:       GET  http://$EXTERNAL_IP:34360/metrics"

echo ""
echo "======================================"
echo "Testing Service"
echo "======================================"

echo ""
echo "Testing health endpoint..."
sleep 5
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if [ -n "$HEALTH_RESPONSE" ]; then
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo "⚠ API not responding yet. Check logs with: tail -f /tmp/api.log"
fi

echo ""
echo ""
echo "Testing queue stats..."
QUEUE_RESPONSE=$(curl -s http://localhost:8000/queue/stats)
if [ -n "$QUEUE_RESPONSE" ]; then
    echo "$QUEUE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$QUEUE_RESPONSE"
else
    echo "⚠ Queue stats not available yet"
fi

echo ""
echo "======================================"
echo "Recent Logs"
echo "======================================"

echo ""
echo "=== API Log (last 15 lines) ==="
tail -15 /tmp/api.log

echo ""
echo "=== Worker Log (last 15 lines) ==="
tail -15 /tmp/worker.log

echo ""
echo "======================================"
echo "✓ All services started successfully!"
echo "======================================"
echo ""
echo "To view logs in real-time:"
echo "  API:    tail -f /tmp/api.log"
echo "  Worker: tail -f /tmp/worker.log"
echo "  Redis:  redis-cli monitor"
echo ""
