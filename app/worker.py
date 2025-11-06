#!/usr/bin/env python3
"""
Background Worker for Async Transcription Jobs
Processes jobs from Redis queue using WhisperX
"""

import os
import sys
import logging
import time
import signal
from pathlib import Path

from app.job_queue import JobQueue, JobStatus
from app.whisper_service import WhisperSTTService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_requested = True


class TranscriptionWorker:
    """Background worker that processes transcription jobs"""

    def __init__(self):
        """Initialize worker with STT service and job queue"""
        # Initialize STT service
        model_size = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
        device = os.getenv("WHISPER_DEVICE", "cuda")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

        logger.info(f"Initializing STT service: model={model_size}, device={device}, compute_type={compute_type}")

        try:
            self.stt_service = WhisperSTTService(
                model_size=model_size,
                device=device,
                compute_type=compute_type
            )
            logger.info("STT service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize STT service: {e}")
            raise

        # Initialize job queue
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD")

        try:
            self.job_queue = JobQueue(
                redis_host=redis_host,
                redis_port=redis_port,
                redis_password=redis_password
            )
            logger.info("Job queue initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize job queue: {e}")
            raise

    def process_job(self, job: dict):
        """
        Process a single transcription job

        Args:
            job: Job data from queue
        """
        job_id = job["job_id"]
        audio_path = job["audio_path"]
        params = job["params"]

        logger.info(f"Processing job {job_id}: {params.get('original_filename')}")

        try:
            # Update status to processing
            self.job_queue.update_status(job_id, JobStatus.PROCESSING, progress=10)

            # Check if audio file exists
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Transcribe
            start_time = time.time()

            result = self.stt_service.transcribe(
                audio_path=audio_path,
                language=params.get("language"),
                task=params.get("task", "transcribe"),
                beam_size=params.get("beam_size", 5),
                vad_filter=params.get("vad_filter", True),
                word_timestamps=params.get("word_timestamps", False),
                enable_diarization=params.get("enable_diarization", False),
                min_speakers=params.get("min_speakers"),
                max_speakers=params.get("max_speakers")
            )

            processing_time = time.time() - start_time
            result["processing_time"] = processing_time

            # Update status to completed
            self.job_queue.update_status(
                job_id,
                JobStatus.COMPLETED,
                progress=100,
                result=result
            )

            logger.info(
                f"Job {job_id} completed successfully | "
                f"Duration: {result['duration']:.2f}s | "
                f"Processing: {processing_time:.2f}s"
            )

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")

            # Update status to failed
            self.job_queue.update_status(
                job_id,
                JobStatus.FAILED,
                error=str(e)
            )

        finally:
            # Clean up audio file
            try:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
                    logger.debug(f"Deleted temp file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to delete audio file {audio_path}: {e}")

    def run(self):
        """Main worker loop"""
        logger.info("Worker started, waiting for jobs...")

        while not shutdown_requested:
            try:
                # Block for up to 5 seconds waiting for a job
                job = self.job_queue.get_next_job(timeout=5)

                if job:
                    self.process_job(job)
                else:
                    # Timeout, check if shutdown requested
                    continue

            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break

            except Exception as e:
                logger.error(f"Worker error: {e}")
                # Sleep briefly before retrying
                time.sleep(5)

        logger.info("Worker shutting down...")


def main():
    """Main entry point"""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        worker = TranscriptionWorker()
        worker.run()
    except Exception as e:
        logger.error(f"Worker failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
