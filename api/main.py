"""
CDF Speech-to-Text API
FastAPI service for audio transcription using Faster-Whisper
"""

import os
import logging
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

from app.whisper_service import WhisperSTTService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="CDF Speech-to-Text API",
    description="High-performance STT service using Faster-Whisper",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
transcription_counter = Counter('transcriptions_total', 'Total number of transcriptions')
transcription_errors = Counter('transcription_errors_total', 'Total transcription errors')
transcription_duration = Histogram('transcription_duration_seconds', 'Transcription processing time')
audio_duration = Histogram('audio_duration_seconds', 'Duration of audio files processed')

# Global STT service instance
stt_service: Optional[WhisperSTTService] = None


class TranscriptionResponse(BaseModel):
    """Response model for transcription"""
    text: str
    language: str
    language_probability: float
    duration: float
    segments: list
    model: str
    processing_time: float
    word_timestamps: bool
    diarization: Optional[dict] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    model_info: dict


@app.on_event("startup")
async def startup_event():
    """Initialize STT service on startup"""
    global stt_service

    model_size = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
    device = os.getenv("WHISPER_DEVICE", "cuda")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

    logger.info(f"Initializing STT service: model={model_size}, device={device}, compute_type={compute_type}")

    try:
        stt_service = WhisperSTTService(
            model_size=model_size,
            device=device,
            compute_type=compute_type
        )
        logger.info("STT service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize STT service: {e}")
        raise


@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "service": "CDF Speech-to-Text API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    if stt_service is None:
        raise HTTPException(status_code=503, detail="STT service not initialized")

    return {
        "status": "healthy",
        "model_info": stt_service.get_model_info()
    }


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/languages", tags=["General"])
async def get_supported_languages():
    """Get list of supported language codes"""
    if stt_service is None:
        raise HTTPException(status_code=503, detail="STT service not initialized")

    return {
        "languages": stt_service.get_supported_languages(),
        "count": len(stt_service.get_supported_languages())
    }


@app.post("/transcribe", response_model=TranscriptionResponse, tags=["Transcription"])
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file (wav, mp3, flac, etc.)"),
    language: Optional[str] = Form(None, description="Language code (e.g., 'en', 'es'). Auto-detect if not provided"),
    task: str = Form("transcribe", description="Task: 'transcribe' or 'translate' (to English)"),
    beam_size: int = Form(5, description="Beam size for decoding (1-10)"),
    vad_filter: bool = Form(True, description="Use voice activity detection to filter silence"),
    word_timestamps: bool = Form(False, description="Include word-level timestamps"),
    enable_diarization: bool = Form(False, description="Enable speaker diarization (requires HF_TOKEN)"),
    min_speakers: Optional[int] = Form(None, description="Minimum number of speakers for diarization"),
    max_speakers: Optional[int] = Form(None, description="Maximum number of speakers for diarization")
):
    """
    Transcribe audio file to text with optional speaker diarization

    Upload an audio file and receive transcription with metadata.
    Supports 99+ languages and automatic language detection.

    Speaker Diarization:
    - Set enable_diarization=true to identify different speakers
    - Requires HF_TOKEN environment variable (get from https://huggingface.co/settings/tokens)
    - Returns speaker labels (SPEAKER_00, SPEAKER_01, etc.) for each segment
    - Optional: Set min_speakers/max_speakers to constrain detection
    """
    if stt_service is None:
        transcription_errors.inc()
        raise HTTPException(status_code=503, detail="STT service not initialized")

    # Validate task
    if task not in ["transcribe", "translate"]:
        raise HTTPException(status_code=400, detail="Task must be 'transcribe' or 'translate'")

    # Validate beam size
    if not 1 <= beam_size <= 10:
        raise HTTPException(status_code=400, detail="Beam size must be between 1 and 10")

    temp_file = None
    start_time = time.time()

    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        logger.info(f"Processing file: {file.filename} ({len(content)} bytes)")

        # Transcribe with optional diarization
        with transcription_duration.time():
            result = stt_service.transcribe(
                audio_path=temp_file_path,
                language=language,
                task=task,
                beam_size=beam_size,
                vad_filter=vad_filter,
                word_timestamps=word_timestamps,
                enable_diarization=enable_diarization,
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )

        processing_time = time.time() - start_time

        # Update metrics
        transcription_counter.inc()
        audio_duration.observe(result["duration"])

        # Add processing time to response
        result["processing_time"] = processing_time

        logger.info(
            f"Transcription complete: {file.filename} | "
            f"Duration: {result['duration']:.2f}s | "
            f"Processing: {processing_time:.2f}s | "
            f"Language: {result['language']}"
        )

        return result

    except Exception as e:
        transcription_errors.inc()
        logger.error(f"Transcription failed for {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
