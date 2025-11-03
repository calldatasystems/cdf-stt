# CDF STT Testing Scripts

Helper scripts to get connection info and test the deployed STT service.

## Prerequisites

- **GitHub CLI (`gh`)** for `get_connection_info.sh`
  - Install: https://cli.github.com/
  - Ubuntu/Debian: `sudo apt install gh`
  - macOS: `brew install gh`
  - Windows: `winget install --id GitHub.cli`
  - Authenticate: `gh auth login`

- **curl** for `test_stt.sh` (usually pre-installed)
- **jq** for JSON parsing (optional but recommended)
  - Ubuntu/Debian: `sudo apt install jq`
  - macOS: `brew install jq`

## Usage

### 1. Get Connection Info

After deployment succeeds, extract connection details from GitHub Actions:

```bash
cd scripts
chmod +x get_connection_info.sh
./get_connection_info.sh
```

This will show:
- Instance ID
- Public IP (if available)
- SSH host and port
- Instructions for accessing the service

**Alternative:** Check the Vast.ai web console directly at https://vast.ai/console/instances/

### 2. Test the Service

Once you have the HOST and PORT from step 1 or Vast.ai console:

```bash
chmod +x test_stt.sh
./test_stt.sh HOST PORT
```

**Examples:**

```bash
# Using Vast.ai forwarded port
./test_stt.sh ssh6.vast.ai 12345

# Using SSH tunnel to localhost
ssh -p SSH_PORT -L 8000:localhost:8000 root@SSH_HOST
./test_stt.sh localhost 8000
```

## What the Test Script Checks

1. **Basic Connectivity** - Can reach the service
2. **Root Endpoint** - Service responds correctly
3. **Health Check** - Service is healthy, model loaded
4. **Language Support** - 99+ languages available
5. **Metrics Endpoint** - Prometheus metrics working
6. **Transcription** - Can transcribe audio (if test.wav exists)

## Creating a Test Audio File

If you don't have a test audio file:

```bash
# Option 1: Download sample
wget https://www2.cs.uic.edu/~i101/SoundFiles/BabyElephantWalk60.wav -O test.wav

# Option 2: Generate test tone (requires sox)
sox -n -r 16000 -c 1 test.wav synth 3 sine 440

# Option 3: Record your voice (requires sox)
sox -d -r 16000 -c 1 test.wav trim 0 5
```

## Troubleshooting

### Cannot Connect to Service

1. **Check instance status** at https://vast.ai/console/instances/
2. **Verify port mapping** - look for `8000 -> XXXXX` in console
3. **Check instance logs** - click "Logs" button, look for "Uvicorn running"
4. **Try SSH tunnel method** if direct connection fails

### Connection Refused

- Instance may still be starting (wait 2-3 minutes after deployment)
- Model downloading on first run (can take 5-10 minutes)
- Check logs for errors

### Wrong PORT

The PORT is **not** 8000 - it's the **forwarded port** shown in Vast.ai console.

Example: If console shows `8000 -> 54321`, use port `54321`

## SSH Tunnel Method (Most Reliable)

If direct connection doesn't work:

```bash
# Get SSH info from Vast.ai console
# Then create tunnel:
ssh -p SSH_PORT -L 8000:localhost:8000 root@SSH_HOST

# In another terminal:
./test_stt.sh localhost 8000
```

## Expected Test Output

```
==========================================
CDF STT Service Test Suite
==========================================
Testing: http://ssh6.vast.ai:12345

1. Connection Tests
-------------------
Testing Basic connectivity... ✓ PASS
Testing Root endpoint... ✓ PASS

2. Health Check
---------------
Testing Health endpoint... ✓ PASS

Health details:
{
  "status": "healthy",
  "model_info": {
    "model_size": "large-v3",
    "device": "cuda",
    "cuda_device_name": "NVIDIA GeForce RTX 4090"
  }
}

3. Language Support
-------------------
Testing Languages endpoint... ✓ PASS
Supported languages: 99

4. Metrics
----------
Testing Metrics endpoint... ✓ PASS

5. Transcription Test
---------------------
Testing Transcribe audio file... ✓ PASS

Transcription result:
{
  "text": "Hello, this is a test.",
  "language": "en",
  "duration": 3.5,
  "processing_time": 0.8
}

Performance:
  Audio duration: 3.5s
  Processing time: 0.8s
  Speed: 0.23x realtime

==========================================
Test Summary
==========================================
Passed: 6
Failed: 0

✓ All tests passed!

API Documentation: http://ssh6.vast.ai:12345/docs
```

## Quick Reference

### Get instance connection info:
```bash
./get_connection_info.sh
```

### Test deployed service:
```bash
./test_stt.sh HOST PORT
```

### View API docs (browser):
```
http://HOST:PORT/docs
```

### Manual health check:
```bash
curl http://HOST:PORT/health | jq .
```

### Manual transcription test:
```bash
curl -X POST http://HOST:PORT/transcribe \
  -F "file=@test.wav" \
  | jq .
```
