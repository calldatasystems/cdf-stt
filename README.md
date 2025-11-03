# CDF Speech-to-Text Service

High-performance STT service for CallData Foundation Platform using **WhisperX** with **speaker diarization** on Vast.ai RTX 4090.

## Features

- **WhisperX Large-v3** - State-of-the-art transcription accuracy
- **Speaker Diarization** - Automatic speaker identification using pyannote.audio
- **Word-level Timestamps** - Precise alignment for each word
- **GPU Acceleration** - RTX 4090 on Vast.ai (~$0.30-0.50/hour)
- **REST API** - Simple HTTP endpoints for transcription
- **Multi-language** - Supports 99+ languages with auto-detection
- **Docker Ready** - Easy deployment

## Architecture

```
Call Recording → HTTP POST → WhisperX API (Vast.ai) → Transcription + Speakers
```

## Setup

### 1. Get HuggingFace Token

Diarization requires a HuggingFace token:

1. Create account at https://huggingface.co/
2. Get token from https://huggingface.co/settings/tokens
3. Accept pyannote terms: https://huggingface.co/pyannote/speaker-diarization-3.1

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your HF_TOKEN
```

### 3. Run Service

```bash
# Local development
export HF_TOKEN=your_token_here
cd api
uvicorn main:app --host 0.0.0.0 --port 8000

# Docker
docker run -e HF_TOKEN=your_token_here -p 8000:8000 cdf-stt
```

## API Endpoints

### POST /transcribe

**Basic transcription:**
```bash
curl -X POST http://your-vastai-instance:8000/transcribe \
  -F "file=@audio.wav"
```

**With speaker diarization:**
```bash
curl -X POST http://your-vastai-instance:8000/transcribe \
  -F "file=@call_recording.wav" \
  -F "enable_diarization=true" \
  -F "min_speakers=2" \
  -F "max_speakers=2"
```

**Response with diarization:**
```json
{
  "text": "Full transcription text",
  "language": "en",
  "duration": 45.3,
  "segments": [
    {
      "start": 0.5,
      "end": 3.2,
      "text": "Hello, how can I help you?",
      "speaker": "SPEAKER_00",
      "words": [
        {"word": "Hello", "start": 0.5, "end": 0.8, "speaker": "SPEAKER_00"}
      ]
    },
    {
      "start": 3.5,
      "end": 5.8,
      "text": "I need help with my account.",
      "speaker": "SPEAKER_01"
    }
  ],
  "diarization": {
    "enabled": true,
    "num_speakers": 2
  }
}
```

### Other Endpoints

- `GET /health` - Health check
- `GET /languages` - List supported languages
- `GET /metrics` - Prometheus metrics

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| file | File | Required | Audio file (wav, mp3, flac, etc.) |
| language | str | auto | Language code (e.g., 'en', 'es') |
| enable_diarization | bool | false | Enable speaker identification |
| min_speakers | int | None | Minimum number of speakers |
| max_speakers | int | None | Maximum number of speakers |

## Cost

- RTX 4090: ~$0.30-0.50/hour on Vast.ai
- ~0.1x realtime transcription speed
- Diarization adds ~10-20% processing time

## Notes

- **HF_TOKEN required** for diarization to work
- Without HF_TOKEN, service runs in transcription-only mode
- Word-level timestamps always enabled (WhisperX feature)
- For call centers: typically use min_speakers=2, max_speakers=2

## License

MIT
