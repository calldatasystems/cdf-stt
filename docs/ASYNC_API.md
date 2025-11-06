# Async Transcription API

The STT service now supports async job-based transcription to handle long audio files without timeout issues.

## Architecture

```
┌─────────────┐         ┌──────────────┐         ┌────────────┐
│   Client    │ ──POST──> │  FastAPI     │ ──Push──>│   Redis    │
│             │ <─job_id─ │   (API)      │         │   Queue    │
└─────────────┘         └──────────────┘         └────────────┘
       │                                                   │
       │                                                   │ Pop
       │                ┌──────────────┐                  │
       └────GET────────>│   Get Job    │<─────────────────┘
                        │   Status     │
                        └──────────────┘
                               │
                               │ (When completed)
                               ▼
                        ┌──────────────┐
                        │  Background  │
                        │   Worker     │──Transcribe──> WhisperX
                        └──────────────┘
```

## Why Async?

**Problem**: Long audio files (60+ minutes) can take 6+ minutes to transcribe, causing HTTP timeouts.

**Solution**: Job queue pattern
- Client uploads audio → gets job_id immediately
- Worker processes in background
- Client polls for status/result

## API Endpoints

### 1. Submit Async Job

**POST** `/transcribe/async`

Submit audio for transcription - returns immediately with job_id.

```bash
curl -X POST http://localhost:8000/transcribe/async \
  -F "file=@call_recording.wav" \
  -F "enable_diarization=true" \
  -F "language=en"
```

**Response**:
```json
{
  "job_id": "abc123-def456-789",
  "status": "queued",
  "message": "Job created successfully. Use GET /jobs/{job_id} to check status."
}
```

### 2. Check Job Status

**GET** `/jobs/{job_id}`

Get current status and result (if completed).

```bash
curl http://localhost:8000/jobs/abc123-def456-789
```

**Response (Queued)**:
```json
{
  "job_id": "abc123-def456-789",
  "status": "queued",
  "progress": 0,
  "created_at": "2025-01-06T10:30:00",
  "started_at": null,
  "completed_at": null
}
```

**Response (Processing)**:
```json
{
  "job_id": "abc123-def456-789",
  "status": "processing",
  "progress": 10,
  "created_at": "2025-01-06T10:30:00",
  "started_at": "2025-01-06T10:30:05",
  "completed_at": null
}
```

**Response (Completed)**:
```json
{
  "job_id": "abc123-def456-789",
  "status": "completed",
  "progress": 100,
  "created_at": "2025-01-06T10:30:00",
  "started_at": "2025-01-06T10:30:05",
  "completed_at": "2025-01-06T10:35:20",
  "result": {
    "text": "Full transcription...",
    "language": "en",
    "duration": 320.5,
    "segments": [...],
    "processing_time": 32.1
  }
}
```

**Response (Failed)**:
```json
{
  "job_id": "abc123-def456-789",
  "status": "failed",
  "created_at": "2025-01-06T10:30:00",
  "started_at": "2025-01-06T10:30:05",
  "completed_at": "2025-01-06T10:30:10",
  "error": "Failed to load audio: Invalid file format"
}
```

### 3. List Jobs

**GET** `/jobs?status=completed&limit=10`

List recent jobs with optional status filter.

```bash
curl "http://localhost:8000/jobs?status=completed&limit=10"
```

### 4. Queue Stats

**GET** `/queue/stats`

Get queue health and length.

```bash
curl http://localhost:8000/queue/stats
```

**Response**:
```json
{
  "queue_length": 3,
  "redis_healthy": true
}
```

## Job Statuses

| Status | Description |
|--------|-------------|
| `queued` | Job waiting to be processed |
| `processing` | Worker is currently transcribing |
| `completed` | Transcription finished successfully |
| `failed` | Transcription failed (see error field) |

## Integration Pattern

### Python Example

```python
import requests
import time

# Submit job
response = requests.post(
    "http://localhost:8000/transcribe/async",
    files={"file": open("call.wav", "rb")},
    data={"enable_diarization": "true", "language": "en"}
)

job_id = response.json()["job_id"]
print(f"Job created: {job_id}")

# Poll for completion
while True:
    status_response = requests.get(f"http://localhost:8000/jobs/{job_id}")
    job = status_response.json()

    print(f"Status: {job['status']} | Progress: {job['progress']}%")

    if job["status"] == "completed":
        print("Transcription:", job["result"]["text"])
        break
    elif job["status"] == "failed":
        print("Error:", job["error"])
        break

    time.sleep(5)  # Poll every 5 seconds
```

### Node.js Example

```javascript
const FormData = require('form-data');
const axios = require('axios');
const fs = require('fs');

async function transcribeAsync() {
  // Submit job
  const form = new FormData();
  form.append('file', fs.createReadStream('call.wav'));
  form.append('enable_diarization', 'true');
  form.append('language', 'en');

  const response = await axios.post('http://localhost:8000/transcribe/async', form);
  const jobId = response.data.job_id;
  console.log(`Job created: ${jobId}`);

  // Poll for completion
  while (true) {
    const statusResponse = await axios.get(`http://localhost:8000/jobs/${jobId}`);
    const job = statusResponse.data;

    console.log(`Status: ${job.status} | Progress: ${job.progress}%`);

    if (job.status === 'completed') {
      console.log('Transcription:', job.result.text);
      break;
    } else if (job.status === 'failed') {
      console.error('Error:', job.error);
      break;
    }

    await new Promise(resolve => setTimeout(resolve, 5000)); // Poll every 5 seconds
  }
}

transcribeAsync();
```

## Deployment

### With Docker Compose

```bash
# Start all services (Redis + API + Worker)
docker-compose up -d

# View logs
docker-compose logs -f stt-worker
docker-compose logs -f stt-api

# Scale workers
docker-compose up -d --scale stt-worker=3
```

### On Vast.ai

The service is designed to run on Vast.ai with a single GPU instance:

1. **Redis** runs in the same instance (lightweight)
2. **API** handles HTTP requests
3. **Worker** processes transcription jobs using the GPU

Both API and worker can share the same GPU safely since:
- Worker only processes one job at a time
- API is idle during transcription

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_HOST` | Redis server hostname | `localhost` |
| `REDIS_PORT` | Redis server port | `6379` |
| `REDIS_PASSWORD` | Redis password (optional) | None |
| `WHISPER_MODEL_SIZE` | Model size | `large-v3` |
| `WHISPER_DEVICE` | Device (cuda/cpu) | `cuda` |
| `HF_TOKEN` | HuggingFace token for diarization | Required for diarization |

## Sync vs Async

Both endpoints are available:

- **POST `/transcribe`** - Synchronous (blocks until complete)
  - Use for: Short audio (<5 min), real-time requirements
  - Pros: Simple, immediate result
  - Cons: Can timeout on long audio

- **POST `/transcribe/async`** - Asynchronous (returns job_id)
  - Use for: Long audio, batch processing, call recordings
  - Pros: No timeouts, scalable
  - Cons: Requires polling

## Performance

| Audio Duration | Transcription Time | Recommended |
|----------------|-------------------|-------------|
| < 5 minutes | ~30 seconds | Sync or Async |
| 5-30 minutes | 30s - 3 minutes | Async |
| 30-60 minutes | 3-6 minutes | Async |
| 60+ minutes | 6+ minutes | Async |

*Times based on WhisperX large-v3 on RTX 4090 (~0.1x realtime)*

## Monitoring

Check queue health:
```bash
curl http://localhost:8000/queue/stats
```

View Prometheus metrics:
```bash
curl http://localhost:8000/metrics
```

Worker logs:
```bash
# Docker
docker logs -f cdf-stt-worker

# Direct
tail -f /tmp/worker.log
```
