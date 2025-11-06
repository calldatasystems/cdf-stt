"""
Redis-based Job Queue System for Async Transcription
Provides consistent behavior across dev and production
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
import redis

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobQueue:
    """Redis-based job queue for transcription jobs"""

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None
    ):
        """
        Initialize job queue with Redis connection

        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Optional Redis password
        """
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True
        )

        # Test connection
        try:
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

        # Queue name for pending jobs
        self.queue_name = "transcription_queue"

    def create_job(
        self,
        audio_path: str,
        params: Dict[str, Any]
    ) -> str:
        """
        Create a new transcription job and add to queue

        Args:
            audio_path: Path to audio file
            params: Transcription parameters

        Returns:
            job_id: Unique job identifier
        """
        job_id = str(uuid.uuid4())

        job_data = {
            "job_id": job_id,
            "status": JobStatus.QUEUED,
            "audio_path": audio_path,
            "params": params,
            "progress": 0,
            "created_at": datetime.utcnow().isoformat()
        }

        # Store job data as hash
        self.redis_client.hset(
            f"job:{job_id}",
            mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in job_data.items()}
        )

        # Add job to queue (LPUSH for FIFO with BRPOP)
        self.redis_client.lpush(self.queue_name, job_id)

        # Set expiration for job data (7 days)
        self.redis_client.expire(f"job:{job_id}", 7 * 24 * 60 * 60)

        logger.info(f"Created job {job_id} and added to queue")
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job details by ID

        Args:
            job_id: Job identifier

        Returns:
            Job details or None if not found
        """
        job_data = self.redis_client.hgetall(f"job:{job_id}")

        if not job_data:
            return None

        # Parse JSON fields
        job = {}
        for key, value in job_data.items():
            try:
                job[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                job[key] = value

        return job

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Update job status and optional fields

        Args:
            job_id: Job identifier
            status: New job status
            progress: Optional progress percentage (0-100)
            result: Optional result data for completed jobs
            error: Optional error message for failed jobs
        """
        updates = {"status": status}

        if progress is not None:
            updates["progress"] = progress

        if result is not None:
            updates["result"] = json.dumps(result)

        if error is not None:
            updates["error"] = error

        # Set timestamps
        if status == JobStatus.PROCESSING:
            updates["started_at"] = datetime.utcnow().isoformat()
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            updates["completed_at"] = datetime.utcnow().isoformat()

        # Update hash
        self.redis_client.hset(
            f"job:{job_id}",
            mapping={k: str(v) for k, v in updates.items()}
        )

        logger.info(f"Updated job {job_id} status to {status}")

        # Publish status update for real-time notifications (optional)
        self.redis_client.publish(
            f"job:{job_id}:status",
            json.dumps({"job_id": job_id, "status": status, "progress": progress})
        )

    def get_next_job(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """
        Get the next queued job (blocking)

        Args:
            timeout: Timeout in seconds (0 = wait forever)

        Returns:
            Job data or None if timeout
        """
        result = self.redis_client.brpop(self.queue_name, timeout=timeout)

        if not result:
            return None

        _, job_id = result
        return self.get_job(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional status filter

        Note: This scans Redis keys, use sparingly in production

        Args:
            status: Optional status filter
            limit: Maximum number of jobs to return

        Returns:
            List of job details
        """
        jobs = []

        # Scan for job keys
        for key in self.redis_client.scan_iter("job:*", count=1000):
            if len(jobs) >= limit:
                break

            job = self.get_job(key.split(":", 1)[1])

            if job:
                if status is None or job.get("status") == status:
                    jobs.append(job)

        # Sort by created_at descending
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jobs[:limit]

    def get_queue_length(self) -> int:
        """Get number of jobs in queue"""
        return self.redis_client.llen(self.queue_name)

    def cleanup_old_jobs(self, days: int = 7) -> int:
        """
        Delete completed/failed jobs older than N days

        Args:
            days: Age threshold in days

        Returns:
            Number of jobs deleted
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = 0

        for key in self.redis_client.scan_iter("job:*", count=1000):
            job = self.get_job(key.split(":", 1)[1])

            if job and job.get("status") in [JobStatus.COMPLETED, JobStatus.FAILED]:
                completed_at = job.get("completed_at")

                if completed_at:
                    completed_date = datetime.fromisoformat(completed_at)

                    if completed_date < cutoff:
                        self.redis_client.delete(key)
                        deleted += 1

        logger.info(f"Cleaned up {deleted} old jobs")
        return deleted

    def subscribe_to_job_updates(self, job_id: str):
        """
        Subscribe to real-time job status updates

        Args:
            job_id: Job identifier

        Returns:
            Redis PubSub object
        """
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(f"job:{job_id}:status")
        return pubsub

    def health_check(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            self.redis_client.ping()
            return True
        except redis.ConnectionError:
            return False
